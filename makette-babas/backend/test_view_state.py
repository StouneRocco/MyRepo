import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
from view_state import SharedView, register_shared_view


class SharedViewTests(unittest.TestCase):
    def setUp(self):
        self.store=MagicMock()
        self.store.find_one.return_value=None
        self.http=MagicMock()
        self.view=SharedView(self.store,MagicMock(),'http://receiver',self.http)

    def test_two_clients_share_date_and_selection_without_reset_on_get(self):
        app=Flask(__name__)
        register_shared_view(app,self.view,lambda f:f)
        pc,tablet=app.test_client(),app.test_client()
        room=self.view.plans[3]['rooms'][0]['id']
        edited=tablet.post('/api/view-state',json={'day':'2026-06-30','minute':840,'roomId':room}).json
        self.assertEqual(pc.get('/api/view-state').json,edited)
        pc.post('/api/view-state',json={'minute':900})
        self.assertEqual(tablet.get('/api/view-state').json['day'],'2026-06-30')
        self.assertEqual(tablet.get('/api/view-state').json['minute'],900)
        self.assertEqual(tablet.get('/api/view-state').json['roomId'],room)

    def test_only_server_advances_playback_and_wraps(self):
        self.view.update({'minute':1425,'playing':True})
        self.view.tick(self.view.last_tick+.51)
        self.assertEqual(self.view.snapshot()['minute'],0)
        self.view.update({'minute':1435,'playing':True})
        self.view.tick(self.view.last_tick+.51)
        self.assertEqual(self.view.snapshot()['minute'],0)
        self.view.update({'playing':False})
        self.view.tick(self.view.last_tick+10)
        self.assertEqual(self.view.snapshot()['minute'],0)

    def test_invalid_patches_do_not_change_shared_view(self):
        original=self.view.snapshot()
        for patch in ({'minute':3},{'floor':2},{'day':'bad'},{'playing':1},{'roomId':'unknown'},{'revision':100}):
            with self.assertRaises((ValueError,TypeError)):
                self.view.update(patch)
            self.assertEqual(self.view.snapshot(),original)

    def test_project_date_selection_and_colors_are_sent_atomically(self):
        plan=self.view.plans[3]
        room=plan['rooms'][0]
        series={r['id']:[None]*288 for r in plan['rooms']}
        series[room['id']][168]=24.5
        self.view.frame=lambda floor,day:{'series':series,'interpolated_series':series,
                            'estimated':{r['id']:[False]*288 for r in plan['rooms']}}
        state=self.view.update({'day':'2026-06-30','minute':840,'roomId':room['id']})
        self.view.project(state)
        payload=self.http.post.call_args.kwargs['json']
        self.assertEqual(payload['context']['day'],'2026-06-30')
        self.assertEqual(payload['temperatures'][room['code']],24.5)
        self.assertEqual(payload['roomId'],room['id'])
        self.assertEqual(payload['context']['roomStats']['mean'],24.5)

    def test_presence_projects_hourly_counts_and_selection_without_loading_temperatures(self):
        room=self.view.plans[3]['rooms'][0]
        rooms={r['code']:{'hours':[0]*24} for r in self.view.plans[3]['rooms']}
        rooms[room['code']]['hours'][14]=7
        self.view.badgeages.day=MagicMock(return_value={'rooms':rooms})
        self.view.frame=MagicMock(side_effect=AssertionError('Temperature frame must not be loaded'))
        state=self.view.update({'metric':'presence','day':'2026-01-05','minute':840,'roomId':room['id']})
        self.view.project(state)
        payload=self.http.post.call_args.kwargs['json']
        self.assertEqual(payload['temperatures'][room['code']],7)
        self.assertEqual(payload['context']['metric'],'presence')
        self.assertEqual(payload['context']['scaleMax'],15)
        self.assertTrue(payload['context']['dataAvailable'])
        self.assertEqual(payload['context']['minute'],840)
        self.assertEqual(payload['roomId'],room['id'])
        self.assertEqual(len(payload['temperatures']),len(rooms))

    def test_electricity_projects_only_available_hourly_values(self):
        room = self.view.plans[3]['rooms'][0]
        values = [None]*24
        values[14] = 0.0
        with patch('view_state.electrical_frame', return_value={'rooms':{room['code']:{'hours':values}}}):
            state = self.view.update({'metric':'electricity','day':'2026-01-05','minute':840,'roomId':room['id']})
            self.view.project(state)
        payload = self.http.post.call_args.kwargs['json']
        self.assertEqual(payload['temperatures'],{room['code']:0.0})
        self.assertEqual(payload['context']['metric'],'electricity')
        self.assertEqual(payload['context']['scaleMax'],0.5)
        self.assertTrue(payload['context']['dataAvailable'])

    def test_missing_presence_day_clears_previous_map(self):
        self.view.badgeages.day=MagicMock(return_value=None)
        state=self.view.update({'metric':'presence'})
        self.view.project(state)
        payload=self.http.post.call_args.kwargs['json']
        self.assertEqual(payload['temperatures'],{})
        self.assertFalse(payload['context']['dataAvailable'])

    def test_metric_switch_pauses_and_presence_playback_uses_whole_hours(self):
        self.view.update({'minute':845,'playing':True})
        state=self.view.update({'metric':'presence'})
        self.assertEqual(state['minute'],840)
        self.assertFalse(state['playing'])
        self.view.update({'playing':True,'minute':1380})
        self.view.tick(self.view.last_tick+1.01)
        self.assertEqual(self.view.state['minute'],0)
        self.view.update({'metric':'temperatures'})
        self.view.update({'playing':True})
        self.view.tick(self.view.last_tick+.51)
        self.assertEqual(self.view.state['minute'],15)

    def test_delayed_electricity_playback_does_not_skip_hours(self):
        self.view.update({'metric':'electricity','minute':0})
        self.view.update({'playing':True})
        start = self.view.last_tick
        self.view.tick(start+3.5)
        self.assertEqual(self.view.state['minute'],60)
        self.view.tick(start+4)
        self.assertEqual(self.view.state['minute'],60)
        self.view.tick(start+4.6)
        self.assertEqual(self.view.state['minute'],120)

    def test_invalid_metric_and_fractional_presence_hour_are_rejected(self):
        for patch in ({'metric':'unknown'},{'metric':[]},{'metric':'presence','minute':'bad'}):
            with self.assertRaises(ValueError):self.view.update(patch)
        self.view.update({'metric':'presence'})
        with self.assertRaises(ValueError):self.view.update({'minute':5})

    def test_two_clients_share_presence_mode_date_hour_and_room(self):
        app=Flask(__name__)
        register_shared_view(app,self.view,lambda f:f)
        pc,tablet=app.test_client(),app.test_client()
        room=self.view.plans[3]['rooms'][0]['id']
        data=tablet.post('/api/view-state',json={'metric':'presence','day':'2026-01-05','minute':840,'roomId':room}).json
        self.assertEqual(pc.get('/api/view-state').json,data)
        self.assertEqual(data['metric'],'presence')
        tablet.post('/api/view-state',json={'metric':'temperatures'})
        self.assertEqual(pc.get('/api/view-state').json['metric'],'temperatures')


class RecoveryTests(unittest.TestCase):
    setUp=SharedViewTests.setUp
    def test_database_failure_does_not_publish_failed_change(self):
        from pymongo.errors import AutoReconnect
        before=self.view.snapshot()
        self.store.replace_one.side_effect=AutoReconnect('offline')
        with self.assertRaises(AutoReconnect):self.view.update({'minute':60})
        self.assertEqual(self.view.snapshot(),before)

    def test_driver_survives_a_failed_cycle(self):
        from pymongo.errors import AutoReconnect
        def send(state):
            self.view.stop_event.set()
        self.view.active=True
        self.view.tick=MagicMock(side_effect=[AutoReconnect('offline'),None])
        self.view.project=MagicMock(side_effect=send)
        self.view.stop_event.wait=MagicMock()
        with self.assertLogs(level='ERROR'):self.view.run()
        self.assertTrue(self.view.available)
        self.assertIsNone(self.view.error)
        self.assertEqual(self.view.tick.call_count,2)

    def test_periodic_send_restores_unchanged_view(self):
        self.view.active=True;self.view.rendered=self.view.state['revision'];self.view.last_send=0
        self.view.project=MagicMock(side_effect=lambda state:self.view.stop_event.set())
        self.view.run()
        self.view.project.assert_called_once()

    def test_heatmap_toggle_preserves_measurements(self):
        SharedViewTests.test_project_date_selection_and_colors_are_sent_atomically(self)
        self.view.project({**self.view.state,'heatmap':False})
        payload=self.http.post.call_args.kwargs['json']
        self.assertFalse(payload['heatmap'])
        self.assertIn(24.5,payload['temperatures'].values())

    def test_saved_animation_is_paused_on_restart(self):
        self.store.find_one.return_value={'floor':3,'day':'2026-06-30','playing':True,'revision':4}
        restored=SharedView(self.store,MagicMock(),'http://receiver',self.http)
        self.assertFalse(restored.state['playing'])

    def test_playback_persistence_is_throttled_and_failed_tick_is_atomic(self):
        from pymongo.errors import AutoReconnect
        self.view.update({'playing':True})
        self.store.replace_one.reset_mock()
        now=self.view.last_tick
        self.view.tick(now+.51)
        self.view.tick(now+1.01)
        self.assertEqual(self.store.replace_one.call_count,1)
        before=self.view.snapshot()
        self.store.replace_one.side_effect=AutoReconnect('offline')
        with self.assertRaises(AutoReconnect):self.view.tick(now+6)
        self.assertEqual(self.view.snapshot(),before)

    def test_retry_endpoint_forces_a_new_send(self):
        app=Flask(__name__);register_shared_view(app,self.view,lambda f:f)
        self.view.rendered=42
        response=app.test_client().post('/api/projection-retry')
        self.assertEqual(response.status_code,202)
        self.assertEqual(self.view.rendered,-1)
