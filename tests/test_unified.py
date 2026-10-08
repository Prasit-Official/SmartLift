import json
import tempfile
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from config import load_criteria
from monitoring.unified import UnifiedEngine
from monitoring.events import EventRecorder
from monitoring.archive import EventArchive
from monitoring.server import Dashboard


def feature(knee=175,trunk=10):
    return dict(side='left',trunk_inclination=trunk,knee_angle=knee,hip_angle=160,elbow_angle=150,hand_distance_ratio=.5)
def observation(near=False,leg=False):
    return dict(head=None,head_side=None,distance=0 if near else 1,leg=leg)

class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.criteria=load_criteria();self.criteria['quality']['smoothing_seconds']=.001
        self.criteria['standing']['reminder_seconds']=.5
        self.engine=UnifiedEngine(self.criteria,{"posture_dwell":0,"leg_dwell":0})
        self.mock=patch('monitoring.unified.FeatureExtractor.extract',lambda self,joints:joints)
        self.mock.start();self.addCleanup(self.mock.stop)
    def test_danger_and_normal_person_do_not_share_angles(self):
        a=self.engine.update(1,observation(),0,feature(trunk=60))
        b=self.engine.update(2,observation(),0,feature())
        self.assertEqual(a['level'],'DANGER');self.assertNotEqual(b['level'],'DANGER')
        self.assertEqual(b['angles']['trunk_inclination'],10)
        self.assertIsNot(self.engine.postures[1].smoother,self.engine.postures[2].smoother)
    def test_multiple_danger_reasons_same_person(self):
        for i in range(12):p=self.engine.update(1,observation(True,True),i*.1,feature(trunk=60))
        self.assertEqual(len(p['danger_reasons']),2)
        self.assertTrue(any('ยกขา' in reason for reason in p['danger_reasons']))
        self.assertTrue(any('ก้มลำตัว' in reason for reason in p['danger_reasons']))
    def test_standing_reminder_parallel_to_other_person_lifting(self):
        for i in range(10):
            a=self.engine.update(1,observation(),i*.1,feature())
            b=self.engine.update(2,observation(),i*.1,feature(trunk=60))
        self.assertEqual(a['assessments']['standing'],'REMINDER')
        self.assertEqual(a['level'],'WARNING');self.assertEqual(b['level'],'DANGER')
        self.assertEqual(b['standing_seconds'],0)
    def test_lift_cycles_are_independent(self):
        t=0
        for posture,n in [(feature(),6),(feature(150),1),(feature(130),6),(feature(),8)]:
            for _ in range(n):
                a=self.engine.update(1,observation(),t,posture)
                b=self.engine.update(2,observation(),t,feature());t+=.1
        self.assertEqual(a['lift_reps'],1);self.assertEqual(b['lift_reps'],0)
    def test_missing_keypoints_do_not_inherit_other_person_values(self):
        self.engine.update(1,observation(),0,feature(trunk=60))
        p=self.engine.update(2,observation(),0,None)
        self.assertIsNone(p['angles']);self.assertEqual(p['assessments']['lifting'],'UNKNOWN')
    def test_lost_id_discards_only_that_person(self):
        for i in [1,2]:self.engine.update(i,observation(),0,feature())
        survivor=self.engine.postures[2];self.engine.finish_frame({2})
        self.assertNotIn(1,self.engine.postures);self.assertIs(self.engine.postures[2],survivor)
    def test_gap_resets_posture_state(self):
        self.engine.update(1,observation(),0,feature());old=self.engine.postures[1]
        self.engine.update(1,observation(),2,feature())
        self.assertIsNot(self.engine.postures[1],old)
    def test_20_independent_people(self):
        for i in range(20):self.engine.update(i,observation(),0,feature(trunk=60 if i%2 else 10))
        self.assertEqual(len({id(p.cycle) for p in self.engine.postures.values()}),20)
    def test_pause_clears_all_assessments(self):
        self.engine.update(1,observation(),0,feature());self.engine.reset()
        self.assertFalse(self.engine.tracks);self.assertFalse(self.engine.postures)

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'monitor-20261003-010000-123'
        self.rec=EventRecorder(self.folder);self.archive=EventArchive(self.root)
        self.person=dict(id=7,danger_reasons=['ก้มลำตัวมาก'],angles=feature(trunk=60),box=[10,20,30,40],lift_reps=2)
        self.rec.record([self.person],b'full',1,now=0,crops={7:b'crop'})
    def test_crop_and_measurements_persist(self):
        row=self.archive.events(self.folder.name)[0]
        self.assertEqual(row['angles']['trunk_inclination'],60)
        self.assertEqual(self.archive.image(self.folder.name,row['crop']),b'crop')
        self.assertEqual(self.archive.image(self.folder.name,row['image']),b'full')
    def test_review_survives_new_archive_instance(self):
        row=self.rec.events[0]
        self.archive.review(self.folder.name,row['image'],'false_alarm','คนถูกบัง')
        saved=EventArchive(self.root).events(self.folder.name)[0]
        self.assertEqual(saved['review_status'],'false_alarm');self.assertEqual(saved['review_note'],'คนถูกบัง')
        original=json.loads((self.folder/'events.jsonl').read_text())
        self.assertEqual(original['review_status'],'pending')
    def test_review_rejects_unknown_event_and_status(self):
        for image,status in [('missing.jpg','confirmed'),(self.rec.events[0]['image'],'guilty')]:
            with self.assertRaises(ValueError):self.archive.review(self.folder.name,image,status,'')
    def test_reject_path_traversal(self):
        with self.assertRaises(ValueError):self.archive.events('../outside')
        with self.assertRaises(ValueError):self.archive.image(self.folder.name,'../other.jpg')
    def test_sessions_separate_reused_ids(self):
        second=self.root/'monitor-20261003-020000-123';r=EventRecorder(second)
        r.record([self.person],b'other',2,now=0)
        self.assertEqual(len(self.archive.sessions()),2)
        self.assertNotEqual(self.archive.events(second.name)[0]['session'],self.archive.events(self.folder.name)[0]['session'])
    def test_http_review_only_and_history(self):
        dashboard=Dashboard(self.folder,review_only=True)
        try:
            with urllib.request.urlopen(dashboard.url+'/api/history?session='+self.folder.name) as r:
                self.assertEqual(json.load(r)['events'][0]['id'],7)
            headers={'X-LiftSave-Token':dashboard.token,'Origin':dashboard.url,'Content-Type':'application/json'}
            data=dict(action='review',session=self.folder.name,image=self.rec.events[0]['image'],status='confirmed',note='ตรวจภาพแล้ว')
            req=urllib.request.Request(dashboard.url+'/api/control',data=json.dumps(data).encode(),headers=headers)
            with urllib.request.urlopen(req) as r:self.assertEqual(r.status,202)
            self.assertEqual(self.archive.events(self.folder.name)[0]['review_status'],'confirmed')
            req=urllib.request.Request(dashboard.url+'/api/control',data=b'{"action":"start"}',headers=headers)
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(req)
        finally:dashboard.close()
