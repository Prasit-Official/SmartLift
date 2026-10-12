import unittest
import config
from monitoring.unified import UnifiedEngine
from monitoring.rules import observations
from monitoring.still_image import assess_image_person
from test_front_bend import skeleton

class GreenFeedbackTests(unittest.TestCase):
    def update(self,kp,engine=None,zone=None,person_id=1,t=0):
        engine=engine or UnifiedEngine(config.load_criteria())
        obs=observations(kp,(600,400,3),zone or [],.5)
        return engine.update(person_id,obs,t,kp)
    def test_body_green_without_face_or_zone(self):
        p=self.update(skeleton())
        self.assertEqual(p['level'],'NONE');self.assertEqual(p['posture_level'],'NONE')
        self.assertTrue(p['partial_assessment']);self.assertTrue(p['missing'])
    def test_side_view_one_visible_side_green(self):
        kp=skeleton()
        for i in (6,12,14,16):kp[i]['confidence']=0
        self.assertEqual(self.update(kp)['level'],'NONE')
    def test_missing_both_ankles_stays_gray(self):
        kp=skeleton()
        for i in (15,16):kp[i]['confidence']=0
        self.assertEqual(self.update(kp)['level'],'UNKNOWN')
    def test_ambiguous_front_bend_not_green(self):
        kp=skeleton(160);kp[16]['confidence']=0
        self.assertEqual(self.update(kp)['level'],'UNKNOWN')
    def test_warning_danger_and_recovery_per_person(self):
        engine=UnifiedEngine(config.load_criteria(),{'posture_dwell':1})
        self.assertEqual(self.update(skeleton(160),engine,t=0)['level'],'WARNING')
        self.assertEqual(self.update(skeleton(),engine,person_id=2,t=.5)['level'],'NONE')
        self.update(skeleton(160),engine,t=.5)
        self.assertEqual(self.update(skeleton(160),engine,t=1)['level'],'DANGER')
        self.assertEqual(self.update(skeleton(),engine,t=1.1)['level'],'NONE')
    def test_forbidden_zone_overrides_green_body(self):
        engine=UnifiedEngine(config.load_criteria(),{'forbidden_dwell':0});engine.safety.zone_type='forbidden'
        p=self.update(skeleton(),engine,zone=[(0,0),(1,0),(1,1),(0,1)])
        self.assertEqual(p['level'],'DANGER');self.assertEqual(p['posture_level'],'NONE')
    def test_still_image_uses_same_green_logic(self):
        engine=UnifiedEngine(config.load_criteria());kp=skeleton()
        p=assess_image_person(1,observations(kp,(600,400,3),[],.5),kp,engine.criteria,engine.settings,'hazard')
        self.assertEqual(p['level'],'NONE');self.assertFalse(p['temporal_assessed'])
