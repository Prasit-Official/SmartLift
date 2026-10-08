from pathlib import Path

class PoseDetector:
    def __init__(self, model_path, device="cpu"):
        if not Path(model_path).is_file():
            raise FileNotFoundError(f"Pose weights missing: {model_path}. See README_TH.md")
        from ultralytics import YOLO
        self.model = YOLO(str(model_path))
        self.device = device

    def detect(self, frame):
        return self.model.predict(frame, conf=0.35, iou=0.45,
                                  device=self.device, verbose=False)[0]
