import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

class TrainingTests(unittest.TestCase):
    def test_grouped_training_roundtrip(self):
        try:
            import pandas as pd
            import sklearn
            import joblib
        except ImportError:
            self.skipTest('Optional training dependencies not installed')
        from train_classifier import train
        from assessment.classifier import ExperimentalClassifier
        from config import load_criteria
        version=load_criteria()['version']
        rows=[]
        for subject in range(10):
            for frame in range(20):
                label='REVIEW' if frame%2 else 'OBSERVED'
                rows.append(dict(subject_id=f'P{subject:03}',criteria_version=version,mode='lifting',label=label,
                                 trunk_inclination=50 if frame%2 else 10,knee_angle=170,hip_angle=130,
                                 elbow_angle=150,hand_distance_ratio=.5))
        with tempfile.TemporaryDirectory() as tmp:
            csv=Path(tmp)/'labelled.csv';model=Path(tmp)/'model.pkl'
            pd.DataFrame(rows).to_csv(csv,index=False)
            with contextlib.redirect_stdout(io.StringIO()): report=train(csv,model)
            self.assertFalse(set(report['train_subjects'])&set(report['test_subjects']))
            predictor=ExperimentalClassifier(model,version)
            self.assertIn(predictor.predict(rows[0]),['OBSERVED','REVIEW'])
            row=rows[0].copy();row['hand_distance_ratio']=None
            self.assertEqual(predictor.predict(row),'UNAVAILABLE')
            with self.assertRaises(ValueError): ExperimentalClassifier(model,'different-version')
            # This synthetic roundtrip tests plumbing, NOT model accuracy on people.

if __name__=='__main__': unittest.main()
