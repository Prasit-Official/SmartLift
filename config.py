import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
DATA_ROOT = Path(os.environ.get("LIFTSAVE_DATA_DIR", str(PROJECT_ROOT)))
LEGACY_DATA_ROOT = Path.home() / "LiftSaveWithAiData"
MODEL_DIR = ROOT / "models"
YOLO_MODEL = MODEL_DIR / "yolo11n-pose.pt"
CLASSIFIER_MODEL = MODEL_DIR / "lifting_classifier.pkl"
CSV_DIR = DATA_ROOT / "dataset"
REPORT_DIR = DATA_ROOT / "reports"
FEATURE_COLUMNS = ["trunk_inclination", "knee_angle", "hip_angle", "elbow_angle", "hand_distance_ratio"]

def load_criteria(path=None):
    with open(path or ROOT / "criteria.json", encoding="utf-8") as f:
        data = json.load(f)
    if data["cycle"]["down_knee_max"] >= data["cycle"]["up_knee_min"]:
        raise ValueError("Cycle down threshold must be below up threshold")
    if data["cycle"]["dwell_seconds"] <= 0 or data["quality"]["max_gap_seconds"] <= 0:
        raise ValueError("Time thresholds must be positive")
    return data
