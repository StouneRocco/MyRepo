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
