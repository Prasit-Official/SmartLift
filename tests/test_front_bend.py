import math
import tempfile
import unittest
from pathlib import Path
from config import load_criteria
from assessment.front_bend import assess_front_bend
from assessment.features import FeatureExtractor
from monitoring.rules import validate_settings
from monitoring.unified import UnifiedEngine
from monitoring.events import EventRecorder


def skeleton(shoulder_y=100,back=False):
    points=[dict(x=0.,y=0.,confidence=0.) for _ in range(17)]
    # No face landmarks needed for either view. Back labels can swap in image.
    for i,x,y in [(5,100,shoulder_y),(6,220,shoulder_y),(11,100,200),(12,220,200),(13,100,300),(14,220,300),(15,100,400),(16,220,400)]:
        points[i]=dict(x=float(320-x if back else x),y=float(y),confidence=.95)
    return points

def obs():return dict(head=None,inside=False,distance=1,leg=False)

class FrontBendTests(unittest.TestCase):
    def setUp(self):self.settings=validate_settings({})
    def assess(self,points):return assess_front_bend(points,self.settings)
    def test_upright_not_flagged(self):
        p=self.assess(skeleton());self.assertEqual(p['level'],'NONE');self.assertFalse(p['candidate'])
    def test_compressed_front_with_zero_old_trunk_angle(self):
        points=skeleton(160)
        self.assertEqual(FeatureExtractor().extract(points)['trunk_inclination'],0)
        p=self.assess(points);self.assertEqual(p['level'],'DANGER')
        self.assertEqual(p['torso_ratio'],.4);self.assertEqual(p['shoulder_knee_ratio'],1.4)
    def test_back_without_face(self):
        p=self.assess(skeleton(160,back=True));self.assertEqual(p['level'],'DANGER')
    def test_scale_and_translation_invariant(self):
        points=skeleton(160)
        for p in points:p['x']=p['x']*2+100;p['y']=p['y']*2+50
        p=self.assess(points);self.assertEqual(p['level'],'DANGER');self.assertEqual(p['torso_ratio'],.4)
    def test_roll_invariant(self):
        points=skeleton(160);r=math.radians(20)
        for p in points:
            x,y=p['x'],p['y'];p['x']=x*math.cos(r)-y*math.sin(r);p['y']=x*math.sin(r)+y*math.cos(r)
        p=self.assess(points);self.assertEqual(p['level'],'DANGER');self.assertEqual(p['torso_ratio'],.4)
    def test_missing_shoulder_unknown(self):
        points=skeleton(160);points[6]['confidence']=0
        self.assertEqual(self.assess(points)['level'],'UNKNOWN')
    def test_missing_ankle_not_confirmed(self):
        points=skeleton(160);points[16]['confidence']=0
        p=self.assess(points);self.assertTrue(p['candidate']);self.assertEqual(p['level'],'UNKNOWN')
    def test_squat_knees_bent_not_front_stoop(self):
        points=skeleton(160);points[13].update(x=40.,y=280.);points[14].update(x=280.,y=280.)
        p=self.assess(points);self.assertTrue(p['candidate']);self.assertLess(p['knee_min'],150);self.assertEqual(p['level'],'NONE')
    def test_side_view_not_applicable(self):
        points=skeleton(160)
        for i in [6,12,14,16]:points[i]['x']=105.
        self.assertEqual(self.assess(points)['level'],'NOT_APPLICABLE')
    def test_one_shoulder_dropped_not_symmetric_bend(self):
        points=skeleton();points[5]['y']=170.
        self.assertFalse(self.assess(points)['candidate'])
    def test_tiny_person_unknown(self):
        points=skeleton(160)
        for p in points:p['x']*=.1;p['y']*=.1
        self.assertEqual(self.assess(points)['level'],'UNKNOWN')
    def test_nonfinite_unknown(self):
        points=skeleton(160);points[5]['y']=float('nan')
        self.assertEqual(self.assess(points)['level'],'UNKNOWN')
    def test_disabled_and_config_validation(self):
        settings=validate_settings({'front_bend_enabled':0})
        self.assertEqual(assess_front_bend(skeleton(160),settings)['level'],'DISABLED')
        for invalid in [{'front_bend_enabled':.5},{'front_torso_max':0},{'front_knee_min':181}]:
            with self.assertRaises(ValueError):validate_settings(invalid)
    def test_old_preferences_gain_new_defaults(self):
        settings=validate_settings({'posture_dwell':0})
        self.assertEqual(settings['front_bend_enabled'],1);self.assertEqual(settings['posture_dwell'],0)

class FrontBendIntegrationTests(unittest.TestCase):
    def test_zero_captures_first_frame_with_front_measurements(self):
        e=UnifiedEngine(load_criteria(),{'posture_dwell':0})
        p=e.update(1,obs(),0,skeleton(160))
        self.assertEqual(p['level'],'DANGER');self.assertEqual(len(p['danger_reasons']),1)
        self.assertIn('ไหล่ใกล้ขา',p['danger_reasons'][0]);self.assertEqual(p['standing_seconds'],0)
        with tempfile.TemporaryDirectory() as tmp:
            r=EventRecorder(Path(tmp));events=r.record([p],b'test',0,now=0)
            self.assertEqual(len(events),1);self.assertEqual(events[0]['front_bend']['torso_ratio'],.4)
    def test_sustained_dwell_and_independent_people(self):
        e=UnifiedEngine(load_criteria(),{'posture_dwell':1})
        for i in range(11):
            a=e.update(1,obs(),i*.1,skeleton(160));b=e.update(2,obs(),i*.1,skeleton())
            if i<10:self.assertFalse(a['danger_reasons'])
        self.assertTrue(a['danger_reasons']);self.assertFalse(b['danger_reasons'])
    def test_upright_resets_front_timer(self):
        e=UnifiedEngine(load_criteria(),{'posture_dwell':1})
        e.update(1,obs(),0,skeleton(160));e.update(1,obs(),.4,skeleton(160))
        e.update(1,obs(),.5,skeleton());p=e.update(1,obs(),.6,skeleton(160))
        self.assertEqual(p['front_bend_seconds'],0);self.assertFalse(p['danger_reasons'])
    def test_missing_points_reset_front_timer(self):
        e=UnifiedEngine(load_criteria(),{'posture_dwell':1})
        e.update(1,obs(),0,skeleton(160));e.update(1,obs(),.4,[])
        p=e.update(1,obs(),.5,skeleton(160));self.assertEqual(p['front_bend_seconds'],0)
    def test_side_rule_dwell_not_added_to_front_rule_dwell(self):
        e=UnifiedEngine(load_criteria(),{'posture_dwell':1})
        side=skeleton();side[5].update(x=260.,y=170.);side[6]['confidence']=0
        e.update(1,obs(),0,side);e.update(1,obs(),.4,side)
        p=e.update(1,obs(),.5,skeleton(160));self.assertEqual(p['front_bend_seconds'],0);self.assertFalse(p['danger_reasons'])
