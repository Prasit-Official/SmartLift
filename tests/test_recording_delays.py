import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import load_criteria
from monitoring.rules import SafetyEngine,validate_settings
from monitoring.unified import UnifiedEngine
from monitoring.events import EventRecorder
from monitoring.preferences import load_settings,save_settings

def obs(inside=True,leg=False,side='left'):
    return dict(head=None,inside=inside,distance=0 if inside else .5,leg=leg,raised_sides=[side] if leg else [])

class DelayTests(unittest.TestCase):
    def test_forbidden_waits_full_duration(self):
        e=SafetyEngine();e.zone_type='forbidden'
        for t in [0,.5,1,1.9]:self.assertNotIn('เข้าเขตห้ามเข้า',e.update(1,obs(),t)['danger_reasons'])
        self.assertIn('เข้าเขตห้ามเข้า',e.update(1,obs(),2)['danger_reasons'])
    def test_exit_before_duration_resets(self):
        e=SafetyEngine();e.zone_type='forbidden'
        e.update(1,obs(),0);e.update(1,obs(),1);e.update(1,obs(False),1.1)
        for t in [1.2,2,3]:self.assertFalse(e.update(1,obs(),t)['danger_reasons'])
        self.assertTrue(e.update(1,obs(),3.2)['danger_reasons'])
    def test_unknown_position_resets_entry_timer(self):
        e=SafetyEngine();e.zone_type='forbidden';e.update(1,obs(),0);e.update(1,obs(),1)
        e.update(1,{'head':None,'leg':None},1.1)
        self.assertEqual(e.update(1,obs(),1.2)['inside_seconds'],0)
    def test_brief_walking_steps_do_not_capture(self):
        e=SafetyEngine()
        with tempfile.TemporaryDirectory() as tmp:
            r=EventRecorder(Path(tmp))
            for i in range(80):
                t=i*.1;phase=i%10
                p=e.update(1,obs(leg=phase<6,side='left' if (i//10)%2==0 else 'right'),t)
                r.record([p],b'jpeg',t,now=t)
            self.assertEqual(r.events,[])
    def test_alternating_legs_without_neutral_do_not_accumulate(self):
        e=SafetyEngine()
        for i in range(60):
            p=e.update(1,obs(leg=True,side='left' if (i//6)%2==0 else 'right'),i*.1)
            self.assertFalse(p['danger_reasons'])
    def test_same_leg_sustained_captures(self):
        e=SafetyEngine()
        for i in range(21):p=e.update(1,obs(leg=True),i*.1)
        self.assertTrue(p['danger_reasons']);self.assertEqual(p['leg_seconds'],2)
    def test_different_people_do_not_accumulate_time(self):
        e=SafetyEngine();e.zone_type='forbidden'
        e.update(1,obs(),0);e.update(1,obs(),1)
        self.assertEqual(e.update(2,obs(),1.5)['inside_seconds'],0)
    def test_zero_preserves_immediate_option(self):
        e=SafetyEngine({'forbidden_dwell':0,'leg_dwell':0});e.zone_type='forbidden'
        self.assertTrue(e.update(1,obs(),0)['danger_reasons'])
        e.zone_type='hazard';self.assertTrue(e.update(2,obs(leg=True),0)['danger_reasons'])
    def test_posture_alert_has_own_delay(self):
        e=UnifiedEngine(load_criteria())
        feature=dict(side='left',trunk_inclination=60,knee_angle=175,hip_angle=160,elbow_angle=None,hand_distance_ratio=None)
        with patch('monitoring.unified.FeatureExtractor.extract',return_value=feature):
            for i in range(20):self.assertFalse(e.update(1,obs(False),i*.1,[])['danger_reasons'])
            self.assertTrue(e.update(1,obs(False),2,[])['danger_reasons'])
    def test_save_reload_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'prefs.json'
            save_settings(path,{'forbidden_dwell':3,'leg_dwell':2.5,'snapshot_cooldown':20})
            values,error=load_settings(path)
            self.assertIsNone(error);self.assertEqual(values['leg_dwell'],2.5)
            self.assertEqual(values['forbidden_dwell'],3);self.assertEqual(values['snapshot_cooldown'],20)
    def test_invalid_delay_and_corrupt_file(self):
        for key in ['forbidden_dwell','leg_dwell','posture_dwell']:
            with self.assertRaises(ValueError):validate_settings({key:-1})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'prefs.json';path.write_text('broken')
            values,error=load_settings(path)
            self.assertTrue(error);self.assertEqual(values['leg_dwell'],2)
    def test_reentry_must_wait_again(self):
        e=SafetyEngine({'forbidden_dwell':1});e.zone_type='forbidden'
        e.update(1,obs(),0);first=e.update(1,obs(),1)
        e.update(1,obs(False),1.1);p=e.update(1,obs(),1.2)
        self.assertFalse(p['danger_reasons'])
        second=e.update(1,obs(),2.2)
        self.assertTrue(second['danger_reasons']);self.assertNotEqual(first['zone_episode'],second['zone_episode'])
    def test_switch_leg_starts_new_episode_after_new_delay(self):
        e=SafetyEngine({'leg_dwell':1})
        e.update(1,obs(leg=True,side='left'),0)
        first=e.update(1,obs(leg=True,side='left'),1)
        pending=e.update(1,obs(leg=True,side='right'),1.1)
        self.assertFalse(pending['danger_reasons'])
        second=e.update(1,obs(leg=True,side='right'),2.2)
        self.assertTrue(second['danger_reasons'])
        self.assertNotEqual(first['zone_episode'],second['zone_episode'])
