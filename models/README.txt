Place yolo11n-pose.pt here from the official Ultralytics distribution.
Weights are not included in this source package.
From an internet-connected Python environment with requirements installed:
python -c "from ultralytics import YOLO; YOLO('yolo11n-pose.pt')"
Then move the downloaded yolo11n-pose.pt into this models directory.
Official reference: https://docs.ultralytics.com/models/yolo11/
Optional lifting_classifier.pkl must be generated from independently labelled data.
Do not load pickle/joblib models from untrusted sources.
