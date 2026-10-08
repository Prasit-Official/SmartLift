import tempfile
import unittest
from pathlib import Path
from monitoring.rules import SafetyEngine, observations, validate_zone
from monitoring.events import EventRecorder

ZONE=validate_zone([[.1,.6],[.8,.6],[.8,.95],[.1,.95]])
def joints():
    result=[dict(x=0,y=0,confidence=0) for _ in range(17)]
    for i,(x,y) in {0:(150,70),1:(140,50),2:(160,50),3:(120,70),4:(180,70),5:(120,100),6:(180,100),11:(120,200),12:(180,200),13:(120,300),14:(180,300),15:(120,400),16:(180,400)}.items():
        result[i]=dict(x=x,y=y,confidence=.95)
    return result

def observe(kp,zone=ZONE,box=None):return observations(kp,(500,500,3),zone,.5,box)
def zone_obs(inside=True,leg=False):return dict(head=None,distance=0 if inside else .5,inside=inside,leg=leg)

class HeadFixTests(unittest.TestCase):
    def test_frontal_head_without_calibration(self):
        kp=joints();kp[0]['y']=40;e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0})
        for i in range(102):p=e.update(1,observe(kp),i*.1)
        self.assertEqual(p['head_method'],'front_ears');self.assertEqual(p['level'],'DANGER')
        self.assertTrue(any('แหงน' in x for x in p['danger_reasons']))
    def test_neutral_frontal_not_up(self):
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0})
        for i in range(110):p=e.update(1,observe(joints()),i*.1)
        self.assertEqual(p['neck_seconds'],0)
    def test_eyes_fallback_no_ears(self):
        kp=joints();kp[3]['confidence']=kp[4]['confidence']=0;kp[0]['y']=40
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0})
        for i in range(102):p=e.update(1,observe(kp),i*.1)
        self.assertEqual(p['head_method'],'front_eyes');self.assertEqual(p['level'],'DANGER')
    def test_head_without_hips_or_shoulders(self):
        kp=joints();kp[0]['y']=40
        for i in [5,6,11,12]:kp[i]['confidence']=0
        self.assertIsNotNone(observe(kp)['head'])
    def test_no_visible_face_unknown(self):
        kp=joints()
        for i in range(5):kp[i]['confidence']=0
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});p=e.update(1,observe(kp),0)
        self.assertIsNone(p['head_angle']);self.assertEqual(p['neck_seconds'],0)
    def test_calibrated_small_change_triggers(self):
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});kp=joints();e.update(1,observe(kp),0);e.calibrate()
        for i in range(1,25):e.update(1,observe(kp),i*.1)
        kp[0]['y']=62 # about 15 degrees, below the absolute 25-degree threshold
        for i in range(25,135):p=e.update(1,observe(kp),i*.1)
        self.assertEqual(p['head_mode'],'relative');self.assertGreater(p['neck_seconds'],10)

class ZoneLegTests(unittest.TestCase):
    def test_small_straight_leg_each_side(self):
        for index,side in [(15,'left'),(16,'right')]:
            kp=joints();kp[index]['y']-=10
            obs=observe(kp);self.assertTrue(obs['leg']);self.assertEqual(obs['raised_sides'],[side])
            p=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0}).update(1,obs,0)
            self.assertIn('ยกขาในหรือใกล้ขอบเขตอันตราย',p['danger_reasons'])
    def test_level_feet_are_not_leg_raise(self):
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});kp=joints();e.update(1,observe(kp),0)
        # Hip drops but both ankles stay on the floor: must not become a raised leg.
        kp[11]['y']+=30;kp[12]['y']+=30
        p=e.update(1,observe(kp),.1)
        self.assertEqual(p['raised_sides'],[]);self.assertFalse(p['danger_reasons'])
    def test_only_one_visible_foot_can_establish_entry(self):
        kp=joints();kp[16]['confidence']=0;e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});e.zone_type='forbidden'
        p=e.update(1,observe(kp),0);self.assertIn('เข้าเขตห้ามเข้า',p['danger_reasons'])
    def test_forbidden_first_frame_no_leg_no_dwell(self):
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});e.zone_type='forbidden';p=e.update(3,zone_obs(True),0)
        self.assertEqual(p['level'],'DANGER');self.assertIsNotNone(p['zone_episode'])
    def test_hazard_requires_raised_leg(self):
        p=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0}).update(3,zone_obs(True,False),0)
        self.assertNotEqual(p['level'],'DANGER')
    def test_holding_edge_with_feet_outside(self):
        kp=joints()
        for i in [11,12,13,14,15,16]:kp[i]['x']=480
        kp[9]=dict(x=390,y=350,confidence=.95);kp[15]['y']-=12
        p=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0}).update(1,observe(kp),0)
        # Long oblique torso means use explicit sensitivity appropriate to geometry.
        e=SafetyEngine({'leg_rise':.02,'leg_dwell':0});o=observations(kp,(500,500,3),ZONE,.5,leg_rise=.02)
        p=e.update(1,o,0);self.assertTrue(p['zone_near']);self.assertEqual(p['level'],'DANGER')
    def test_box_base_fallback(self):
        kp=joints();kp[15]['confidence']=kp[16]['confidence']=0
        o=observe(kp,box=[100,0,200,400]);self.assertTrue(o['inside']);self.assertEqual(o['zone_source'],'box_base')
    def test_box_top_overlap_not_entry(self):
        kp=[dict(x=0,y=0,confidence=0) for _ in range(17)]
        o=observe(kp,box=[100,300,200,499]);self.assertFalse(o['inside'])
    def test_reentry_bypasses_snapshot_cooldown(self):
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});e.zone_type='forbidden'
        with tempfile.TemporaryDirectory() as tmp:
            r=EventRecorder(Path(tmp))
            p=e.update(1,zone_obs(True),0);r.record([p],b'frame1',0,now=0)
            p=e.update(1,zone_obs(True),.1);r.record([p],b'frame2',.1,now=.1)
            self.assertEqual(len(r.events),1)
            e.update(1,zone_obs(False),.2)
            p=e.update(1,zone_obs(True),.3);r.record([p],b'frame3',.3,now=.3)
            self.assertEqual(len(r.events),2)
    def test_raised_then_lowered_then_raised_new_event(self):
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});a=e.update(1,zone_obs(True,True),0)['zone_episode']
        e.update(1,zone_obs(True,False),.1)
        b=e.update(1,zone_obs(True,True),.2)['zone_episode'];self.assertNotEqual(a,b)
    def test_single_visible_leg_temporal_rise(self):
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});kp=joints();e.update(1,observe(kp),0)
        kp[16]['confidence']=0;kp[15]['y']-=12
        p=e.update(1,observe(kp),.1);self.assertIn('left',p['raised_sides']);self.assertEqual(p['level'],'DANGER')

class QualityRegressions(unittest.TestCase):
    def test_face_confidence_independent_of_body(self):
        kp=joints();kp[0]['y']=40
        for i in range(5):kp[i]['confidence']=.4
        self.assertIsNotNone(observe(kp)['head'])
        self.assertIsNone(observations(kp,(500,500,3),ZONE,.5,head_confidence=.6)['head'])
    def test_old_hidden_leg_reference_cannot_raise_alert(self):
        kp=joints();e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});e.update(1,observe(kp),0)
        kp[16]['confidence']=0
        for i in range(1,31):e.update(1,observe(kp),i*.1)
        kp[15]['y']-=20
        p=e.update(1,observe(kp),3.1)
        self.assertEqual(p['raised_sides'],[])
    def test_hands_touching_forbidden_zone_are_not_foot_entry(self):
        kp=joints();kp[15]['x']=kp[16]['x']=480
        kp[9]=dict(x=200,y=350,confidence=.95)
        e=SafetyEngine({"leg_dwell":0,"forbidden_dwell":0});e.zone_type='forbidden';p=e.update(1,observe(kp),0)
        self.assertTrue(p['zone_near']);self.assertFalse(p['zone_inside'])
        self.assertNotIn('เข้าเขตห้ามเข้า',p['danger_reasons'])
