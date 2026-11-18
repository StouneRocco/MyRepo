"""Vue partagée PC/tablette : validation, lecture serveur, persistance et pilote de projection."""
import unittest
from unittest.mock import MagicMock
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
        self.view.tick(self.view.last_tick+.51)
        self.assertEqual(self.view.state['minute'],0)
        self.view.update({'metric':'temperatures'})
        self.view.update({'playing':True})
        self.view.tick(self.view.last_tick+.51)
        self.assertEqual(self.view.state['minute'],15)

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

class ValidationAndPlaybackTests(unittest.TestCase):
    setUp=SharedViewTests.setUp

    def frame_with(self,raw,interpolated,estimated_room=None):
        rooms=self.view.plans[3]['rooms']
        series={r['id']:[None]*288 for r in rooms};filled={r['id']:[None]*288 for r in rooms}
        estimated={r['id']:[False]*288 for r in rooms}
        for room_id,(bucket,value) in raw.items():series[room_id][bucket]=value
        for room_id,(bucket,value) in interpolated.items():filled[room_id][bucket]=value
        if estimated_room:estimated[estimated_room[0]][estimated_room[1]]=True
        self.view.frame=lambda floor,day:{'series':series,'interpolated_series':filled,'estimated':estimated}

    def test_selected_room_must_belong_to_the_floor(self):
        n3,n4=self.view.plans[3]['rooms'][0]['id'],self.view.plans[4]['rooms'][0]['id']
        with self.assertRaises(ValueError):self.view.update({'roomId':n4})
        self.view.update({'roomId':n3})
        # Changer d'étage sans retirer la sélection N3 serait incohérent.
        with self.assertRaises(ValueError):self.view.update({'floor':4})
        self.assertEqual(self.view.update({'floor':4,'roomId':n4})['roomId'],n4)

    def test_minute_must_be_a_five_minute_slot_of_the_day(self):
        for minute in (-5,1440,2,True,'60',60.0):
            with self.subTest(minute=minute),self.assertRaises((ValueError,TypeError)):
                self.view.update({'minute':minute})
        for minute in (0,5,1435):
            self.assertEqual(self.view.update({'minute':minute})['minute'],minute)

    def test_each_update_increments_revision_and_is_persisted(self):
        first=self.view.update({'minute':60})['revision']
        second=self.view.update({'heatmap':False})['revision']
        self.assertEqual(second,first+1)
        stored=self.store.replace_one.call_args.args[1]
        self.assertEqual((stored['_id'],stored['minute'],stored['heatmap'],stored['revision']),('shared',60,False,second))
        self.assertTrue(self.store.replace_one.call_args.kwargs['upsert'])

    def test_late_tick_advances_several_steps(self):
        self.view.update({'minute':0,'playing':True})
        self.view.tick(self.view.last_tick+2.0)
        self.assertEqual(self.view.snapshot()['minute'],60)

    def test_inactive_view_never_advances(self):
        self.view.state['playing']=True
        self.view.tick(self.view.last_tick+10)
        self.assertEqual(self.view.snapshot()['minute'],0)

    def test_restart_keeps_valid_stored_state_and_next_revision(self):
        room=self.view.plans[3]['rooms'][0]['id']
        self.store.find_one.return_value={'_id':'shared','floor':3,'day':'2026-06-30','minute':840,'roomId':room,'revision':7}
        restored=SharedView(self.store,MagicMock(),'http://receiver',self.http)
        self.assertEqual((restored.state['day'],restored.state['minute'],restored.state['roomId']),('2026-06-30',840,room))
        self.assertEqual(restored.state['revision'],8)
        self.assertFalse(restored.active)

    def test_corrupted_stored_state_falls_back_to_defaults(self):
        self.store.find_one.return_value={'floor':9,'day':'bad','minute':3,'revision':'x'}
        restored=SharedView(self.store,MagicMock(),'http://receiver',self.http)
        self.assertEqual((restored.state['floor'],restored.state['day'],restored.state['minute'],restored.state['revision']),(3,'2026-01-01',0,0))

    def test_n4_consultation_still_projects_n3_without_selection(self):
        room=self.view.plans[3]['rooms'][0]
        self.frame_with({room['id']:(0,20.0)},{room['id']:(0,20.0)})
        n4=self.view.plans[4]['rooms'][0]['id']
        self.view.project(self.view.update({'floor':4,'roomId':n4}))
        payload=self.http.post.call_args.kwargs['json']
        self.assertEqual(payload['temperatures'],{room['code']:20.0})
        self.assertIsNone(payload['roomId'])
        self.assertIsNone(payload['context']['roomCode'])
        self.assertEqual(self.http.post.call_args.args[0],'http://receiver/project-temperatures')

    def test_interpolation_option_selects_series_and_estimated_rooms(self):
        a,b=self.view.plans[3]['rooms'][:2]
        self.frame_with({a['id']:(0,20.0)},{a['id']:(0,20.0),b['id']:(0,21.5)},(b['id'],0))
        self.view.project(self.view.update({'interpolate':True}))
        payload=self.http.post.call_args.kwargs['json']
        self.assertEqual(payload['temperatures'],{a['code']:20.0,b['code']:21.5})
        self.assertEqual(payload['context']['estimated'],[b['code']])
        self.view.project(self.view.update({'interpolate':False}))
        payload=self.http.post.call_args.kwargs['json']
        self.assertEqual(payload['temperatures'],{a['code']:20.0})
        self.assertEqual(payload['context']['estimated'],[])

    def test_stopped_render_loop_is_reported_as_unavailable(self):
        self.view.active=True
        self.view.project=MagicMock()
        self.http.get.return_value.json.return_value={'renderAgeSeconds':None}
        self.view.stop_event.wait=MagicMock(side_effect=lambda delay:self.view.stop_event.set())
        with self.assertLogs(level='ERROR'):self.view.run()
        self.assertFalse(self.view.available)
        self.assertIn('Projection indisponible',self.view.error)

    def test_healthy_receiver_status_is_published(self):
        self.view.active=True
        self.view.project=MagicMock()
        self.http.get.return_value.json.return_value={'renderAgeSeconds':.1,'cameraAvailable':True}
        self.view.stop_event.wait=MagicMock(side_effect=lambda delay:self.view.stop_event.set())
        self.view.run()
        snapshot=self.view.snapshot()
        self.assertTrue(snapshot['available'])
        self.assertTrue(snapshot['receiverStatus']['cameraAvailable'])
        self.assertEqual(self.view.rendered,self.view.state['revision'])


class ViewStateRouteTests(unittest.TestCase):
    def setUp(self):
        SharedViewTests.setUp(self)
        app=Flask(__name__);register_shared_view(app,self.view,lambda f:f)
        self.client=app.test_client()

    def test_first_read_activates_the_shared_projection(self):
        self.assertFalse(self.view.active)
        state=self.client.get('/api/view-state').json
        self.assertTrue(self.view.active)
        for key in ('floor','day','minute','playing','heatmap','interpolate','roomId','revision','available','projectionError'):
            self.assertIn(key,state)

    def test_invalid_patch_is_400_and_database_outage_is_503(self):
        for body in (None,[],{},{'unknown':1},{'minute':3}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post('/api/view-state',json=body).status_code,400)
        from pymongo.errors import AutoReconnect
        self.store.replace_one.side_effect=AutoReconnect('offline')
        self.assertEqual(self.client.post('/api/view-state',json={'minute':60}).status_code,503)


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
