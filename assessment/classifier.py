from config import FEATURE_COLUMNS

class ExperimentalClassifier:
    def __init__(self,path,criteria_version):
        import joblib
        bundle=joblib.load(path)  # Load only a model you trained / trust.
        if bundle.get("feature_columns")!=FEATURE_COLUMNS:
            raise ValueError("Classifier feature schema mismatch")
        if bundle.get("criteria_version")!=criteria_version:
            raise ValueError("Classifier criteria version mismatch")
        self.model=bundle["model"]
    def predict(self,features):
        if features is None or any(features.get(k) is None for k in FEATURE_COLUMNS):
            return "UNAVAILABLE"
        import pandas as pd
        frame=pd.DataFrame([{k:features[k] for k in FEATURE_COLUMNS}])
        return str(self.model.predict(frame)[0])
