import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from realtime.audio_alert import AlertSchedule,AudioAlert,write_tone
from assessment.rules import RuleEngine
from config import load_criteria

class AudioTests(unittest.TestCase):
    def test_warning_dwell_and_repeat(self):
        s=AlertSchedule()
        self.assertEqual(s.tick('WARNING',0,0),['STOP'])
        self.assertEqual(s.tick('WARNING',.1,.1),[])
        self.assertEqual(s.tick('WARNING',.31,.31),['WARNING'])
        self.assertEqual(s.tick('WARNING',1,1),[])
        self.assertEqual(s.tick('WARNING',1.82,1.82),['WARNING'])
    def test_escalation_cancels_short_tone(self):
        s=AlertSchedule();s.tick('WARNING',0,0);s.tick('WARNING',.31,.31)
        self.assertEqual(s.tick('DANGER',.4,.4),['STOP'])
        self.assertEqual(s.tick('DANGER',.71,.71),['DANGER'])
    def test_unknown_immediately_stops(self):
        s=AlertSchedule();s.tick('DANGER',0,0);s.tick('DANGER',.31,.31)
        self.assertEqual(s.tick('UNKNOWN',.4,.4),['STOP'])
        self.assertEqual(s.tick('NONE',5,5),[])
    def test_stale_data_stops(self):
        s=AlertSchedule();s.tick('DANGER',0,0);s.tick('DANGER',.31,.31)
        self.assertEqual(s.tick('DANGER',.31,1.4),['STOP'])
    def test_brief_spike_never_beeps(self):
        s=AlertSchedule();s.tick('DANGER',0,0)
        self.assertEqual(s.tick('NONE',.1,.1),['STOP'])
        self.assertEqual(s.tick('NONE',1,1),[])
    def test_rules_provide_two_levels(self):
        rules=RuleEngine(load_criteria())
        self.assertEqual(rules.assess(dict(trunk_inclination=36,knee_angle=130)).alert_level,'WARNING')
        red=rules.assess(dict(trunk_inclination=46,knee_angle=150))
        self.assertEqual(red.alert_level,'DANGER');self.assertEqual(red.status,'REVIEW')
        self.assertEqual(rules.assess(None).alert_level,'NONE')
    def test_wav_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tone.wav';write_tone(path,.85,1100)
            with wave.open(str(path)) as wav:
                self.assertAlmostEqual(wav.getnframes()/wav.getframerate(),.85,places=3)
                self.assertEqual(wav.getnchannels(),1)
    def test_worker_plays_and_closes(self):
        class Player:
            def __init__(self):self.played=threading.Event();self.closed=False;self.calls=[]
            def play(self,level):self.calls.append(level);self.played.set()
            def stop(self):self.calls.append('STOP')
            def close(self):self.closed=True
        p=Player();a=AudioAlert(player=p)
        try:
            a.update('DANGER');self.assertTrue(p.played.wait(.9))
        finally:a.close()
        self.assertTrue(p.closed);self.assertFalse(a.thread.is_alive())
    def test_muted_does_not_create_thread(self):
        a=AudioAlert(enabled=False);a.update('DANGER');a.close()
        self.assertIsNone(a.thread)

if __name__=='__main__':unittest.main()
