import tempfile
import unittest
from pathlib import Path
from config import load_criteria
from monitoring.preferences import save_settings,load_settings
from monitoring.unified import UnifiedEngine
from monitoring.events import EventRecorder

class ZeroCaptureTests(unittest.TestCase):
    def test_saved_zero_captures_first_qualifying_frame(self):
        points=[dict(x=0.,y=0.,confidence=0.) for _ in range(17)]
        for i,x,y in [(5,230,140),(11,100,200),(13,100,300),(15,100,400)]:points[i]=dict(x=x,y=y,confidence=.95)
        with tempfile.TemporaryDirectory() as tmp:
            prefs=Path(tmp)/'settings.json';save_settings(prefs,{'posture_dwell':0})
            settings,error=load_settings(prefs);self.assertIsNone(error)
            engine=UnifiedEngine(load_criteria(),settings)
            person=engine.update(1,dict(head=None,inside=False,distance=1,leg=False),0,points)
            self.assertEqual(person['level'],'DANGER');self.assertEqual(person['posture_seconds'],0)
            recorder=EventRecorder(Path(tmp)/'monitor-1')
            events=recorder.record([person],b'first-frame',0,now=0)
            self.assertEqual(len(events),1);self.assertEqual(events[0]['source_seconds'],0)
            self.assertEqual((recorder.folder/events[0]['image']).read_bytes(),b'first-frame')
    def test_nonzero_still_waits(self):
        from unittest.mock import patch
        engine=UnifiedEngine(load_criteria(),{'posture_dwell':2})
        features=dict(trunk_inclination=60,knee_angle=175,hip_angle=160,side='left')
        with patch('monitoring.unified.FeatureExtractor.extract',return_value=features):
            p=engine.update(1,dict(head=None,distance=1,leg=False),0,[])
        self.assertFalse(p['danger_reasons'])
