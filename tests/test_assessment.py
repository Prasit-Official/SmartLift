import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
from config import load_criteria, FEATURE_COLUMNS
from pose.angles import AngleCalculator
from assessment.features import FeatureExtractor
from assessment.rules import RuleEngine
from assessment.smoothing import Smoother
from assessment.lift_cycle import LiftCycle
from assessment.standing import StandingAssessment
from session.recorder import Recorder


def joints():
    result=[dict(x=0.,y=0.,confidence=0.) for _ in range(17)]
    for i,x,y in [(5,100,100),(7,100,150),(9,100,190),(11,100,200),(13,100,300),(15,100,400)]:
        result[i]=dict(x=float(x),y=float(y),confidence=.95)
    return result

def f(knee=175,trunk=10):
    return dict(side='left',trunk_inclination=trunk,knee_angle=knee,hip_angle=160,elbow_angle=150,hand_distance_ratio=.5)

class GeometryTests(unittest.TestCase):
    def test_known_angle(self):
        self.assertAlmostEqual(AngleCalculator.calculate_angle((0,1),(0,0),(1,0)),90)
    def test_zero_segment_unknown(self):
        self.assertIsNone(AngleCalculator.calculate_angle((0,0),(0,0),(1,0)))
    def test_nonfinite_unknown(self):
        self.assertIsNone(AngleCalculator.trunk_inclination((0,0),(math.nan,0)))
    def test_upright(self):
        self.assertAlmostEqual(FeatureExtractor().extract(joints())['trunk_inclination'],0)
    def test_missing_required_joint(self):
        js=joints();js[15]['confidence']=.1
        self.assertIsNone(FeatureExtractor().extract(js))
    def test_missing_wrist_not_invented(self):
        js=joints();js[9]['confidence']=.1
        out=FeatureExtractor().extract(js)
        self.assertIsNone(out['hand_distance_ratio']); self.assertIsNone(out['elbow_angle'])
    def test_side_lock(self):
        ext=FeatureExtractor(); ext.extract(joints()); js=joints();js[15]['confidence']=0
        for a,b in [(5,6),(7,8),(9,10),(11,12),(13,14),(15,16)]:
            js[b]=dict(x=100.,y=100.+b,confidence=.99)
        self.assertIsNone(ext.extract(js))
    def test_smoothing_does_not_fill_missing(self):
        sm=Smoother();sm.update(f(),0)
        data=f();data['hand_distance_ratio']=None
        self.assertIsNone(sm.update(data,.1)['hand_distance_ratio'])

class CycleTests(unittest.TestCase):
    def setUp(self):
        self.c=load_criteria();self.cycle=LiftCycle(self.c);self.engine=RuleEngine(self.c);self.t=0
    def ticks(self,feature,n=4):
        events=[]
        for _ in range(n):
            event=self.cycle.update(feature,self.engine.assess(feature),self.t)
            self.t+=.1
            if event: events.append(event)
        return events
    def begin(self):
        self.ticks(f(),5);self.ticks(f(150),1);self.ticks(f(130),5)
    def test_no_count_without_ready(self):
        self.ticks(f(130),5);self.ticks(f(),5)
        self.assertEqual(self.cycle.total,0)
    def test_one_complete_cycle(self):
        self.begin();events=self.ticks(f(),5)
        self.assertEqual(len(events),1);self.assertEqual(events[0]['outcome'],'OBSERVED')
    def test_one_warning_is_retained(self):
        self.begin();self.ticks(f(130,50),1);events=self.ticks(f(),5)
        self.assertEqual(events[0]['outcome'],'REVIEW')
    def test_missing_frame_marks_incomplete(self):
        self.begin();self.ticks(None,1);events=self.ticks(f(),5)
        self.assertEqual(events[0]['outcome'],'INCOMPLETE')
    def test_long_gap_aborts(self):
        self.begin();events=self.ticks(None,9)
        self.assertEqual(len(events),1);self.assertEqual(events[0]['outcome'],'INCOMPLETE')
    def test_silent_time_gap_aborts(self):
        self.begin();self.t+=2;events=self.ticks(f(),1)
        self.assertEqual(events[0]['outcome'],'INCOMPLETE')
    def test_partial_descent_is_not_complete(self):
        self.ticks(f(),5);self.ticks(f(155),2);events=self.ticks(f(),5)
        self.assertEqual(events[0]['outcome'],'INCOMPLETE')
    def test_pause_aborts(self):
        self.begin();self.assertEqual(self.cycle.abort(self.t)['outcome'],'INCOMPLETE')
    def test_jitter_does_not_count(self):
        self.ticks(f(),5)
        for _ in range(10): self.ticks(f(150),1);self.ticks(f(145),1)
        self.assertEqual(self.cycle.total,0)
    def test_unknown_is_not_observed(self):
        self.assertEqual(self.engine.assess(None).status,'UNKNOWN')

class StandingTests(unittest.TestCase):
    def test_reminder_and_reset(self):
        c=load_criteria();standing=StandingAssessment(c)
        standing.update(f(),0)
        self.assertEqual(standing.update(f(),61).status,'REMINDER')
        self.assertEqual(standing.update(None,62).status,'UNKNOWN')
        self.assertEqual(standing.update(f(),63).status,'OBSERVED')

class RecordingTests(unittest.TestCase):
    def test_summary_and_blank_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec=Recorder(Path(tmp),'P001','lifting',load_criteria())
            rec.record(0,None,'WAIT_READY',RuleEngine(load_criteria()).assess(None))
            rec.close()
            with (rec.folder/'features.csv').open(encoding='utf-8-sig') as handle:
                rows=list(csv.DictReader(handle))
            self.assertEqual(rows[0]['label'],'');self.assertEqual(rows[0]['knee_angle'],'')
            report=json.loads((rec.folder/'summary.json').read_text())
            self.assertEqual(report['sample_counts']['UNKNOWN'],1)

if __name__=='__main__': unittest.main()
