"""Train only from independently labelled data; split by participant."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import config

def train(csv_path,output,criteria_path=None):
    df=pd.read_csv(csv_path)
    required=set(config.FEATURE_COLUMNS+["subject_id","label","criteria_version","mode"])
    missing=required-set(df.columns)
    if missing: raise ValueError(f"Missing columns: {sorted(missing)}")
    if df[list(required)].isna().any().any():
        raise ValueError("Missing features/labels/IDs. Independently label usable rows; do not fill missing measurements.")
    if not (df["mode"]=="lifting").all():
        raise ValueError("This classifier supports lifting rows only; keep standing data separate")
    if df["subject_id"].astype(str).isin(["anonymous",""]).any():
        raise ValueError("Assign stable participant IDs before training")
    if df["label"].astype(str).str.strip().eq("").any(): raise ValueError("Empty labels")
    X=df[config.FEATURE_COLUMNS].apply(pd.to_numeric,errors="raise")
    if not np.isfinite(X.to_numpy()).all(): raise ValueError("Non-finite features")
    y=df["label"].astype(str); groups=df["subject_id"].astype(str)
    if y.nunique()<2: raise ValueError("At least two independently assigned classes required")
    if groups.nunique()<5: raise ValueError("At least 5 distinct participants required for this grouped split; more data is recommended")
    criteria=config.load_criteria(criteria_path)
    if set(df["criteria_version"])!={criteria["version"]}: raise ValueError("Dataset criteria version mismatch")
    train_idx,test_idx=next(GroupShuffleSplit(n_splits=1,test_size=0.2,random_state=42).split(X,y,groups))
    if set(y.iloc[train_idx])!=set(y) or set(y.iloc[test_idx])!=set(y):
        raise ValueError("Participant holdout lacks a class. Collect broader coverage; do not move individual frames between splits")
    train_groups=groups.iloc[train_idx]
    folds=min(5,train_groups.nunique())
    cv=StratifiedGroupKFold(n_splits=folds,shuffle=True,random_state=42)
    splits=list(cv.split(X.iloc[train_idx],y.iloc[train_idx],train_groups))
    for a,b in splits:
        if set(y.iloc[train_idx].iloc[a])!=set(y) or set(y.iloc[train_idx].iloc[b])!=set(y):
            raise ValueError("A grouped CV fold lacks classes; collect more participant/class coverage")
    model=RandomForestClassifier(n_estimators=200,max_depth=10,min_samples_split=4,class_weight="balanced",random_state=42)
    scores=cross_val_score(model,X.iloc[train_idx],y.iloc[train_idx],cv=splits,scoring="f1_macro")
    model.fit(X.iloc[train_idx],y.iloc[train_idx]); prediction=model.predict(X.iloc[test_idx])
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump({"model":model,"feature_columns":config.FEATURE_COLUMNS,"criteria_version":criteria["version"],"experimental":True},output)
    classes=sorted(set(y))
    report={"cv_macro_f1":scores.tolist(),"test":classification_report(y.iloc[test_idx],prediction,output_dict=True,zero_division=0),
            "classes":classes,"confusion_matrix":confusion_matrix(y.iloc[test_idx],prediction,labels=classes).tolist(),
            "train_subjects":sorted(set(train_groups)),"test_subjects":sorted(set(groups.iloc[test_idx])),
            "note":"Frame-level classification metrics; not clinical or cycle-level validation."}
    output.with_suffix(".metrics.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(classification_report(y.iloc[test_idx],prediction,zero_division=0))
    print(f"Saved {output}; grouped CV macro-F1: {scores.mean():.3f}")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--output",type=Path,default=config.CLASSIFIER_MODEL)
    p.add_argument("--criteria",type=Path)
    args=p.parse_args()
    train(args.csv,args.output,args.criteria)
