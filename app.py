"""CLI camera runner. SPACE confirms side-view setup and starts observation."""
import argparse
from pathlib import Path
import time
import sys
import math
import config
from assessment.features import FeatureExtractor
from assessment.smoothing import Smoother
from assessment.rules import RuleEngine, Assessment
from assessment.lift_cycle import LiftCycle
from assessment.standing import StandingAssessment
from session.recorder import Recorder

def parse_args():
    p=argparse.ArgumentParser(description="LiftSaveWithAi: prototype posture training")
    p.add_argument("--review-only",action="store_true",help="Review saved events without camera/model")
    p.add_argument("--mode",choices=["lifting","standing","monitoring"],default="monitoring")
    p.add_argument("--image",action="store_true",help="Test one still image in monitoring Dashboard")
    p.add_argument("--source",default="0",help="Camera number or video filename")
    p.add_argument("--list-cameras",action="store_true",help="List OS camera devices as JSON")
    p.add_argument("--camera-backend",type=int,default=0)
    p.add_argument("--camera-path",default="")
    p.add_argument("--camera-name",default="")
    p.add_argument("--side",choices=["auto","left","right"],default="auto")
    p.add_argument("--subject",default="anonymous",help="Pseudonymous participant ID")
    p.add_argument("--device",default="cpu",help="cpu or CUDA device, e.g. 0")
    p.add_argument("--model",type=Path,default=config.YOLO_MODEL)
    p.add_argument("--criteria",type=Path,default=config.ROOT/"criteria.json")
    p.add_argument("--classifier",type=Path,help="Optional trusted experimental .pkl")
    p.add_argument("--mute",action="store_true",help="Disable audible alerts")
    p.add_argument("--test-sound",action="store_true",help="Test short and long tones without camera/model")
    p.add_argument("--output",type=Path,default=config.REPORT_DIR)
    return p.parse_args()

def main(args=None):
    args=args or parse_args()
    if getattr(args,"review_only",False):
        from monitoring.server import run_review
        run_review(args.output);return
    if args.list_cameras:
        import json
        from realtime.camera_devices import enumerate_devices
        print(json.dumps(enumerate_devices(),ensure_ascii=False)); return
    from realtime.audio_alert import AudioAlert, test_sound
    if args.test_sound:
        test_sound(); return
    if getattr(args,"image",False) and args.mode != "monitoring":
        raise ValueError("--image requires --mode monitoring")
    if args.mode == "monitoring":
        from monitoring.runner import run
        run(args); return
    criteria=config.load_criteria(args.criteria)
    from realtime.camera import Camera
    from realtime.playback import FrameStepper
    from realtime.overlay import Overlay
    from pose.detector import PoseDetector
    from pose.extractor import PoseExtractor
    import cv2
    detector=PoseDetector(args.model,args.device)
    classifier=None
    if args.classifier:
        from assessment.classifier import ExperimentalClassifier
        classifier=ExperimentalClassifier(args.classifier,criteria["version"])
    features=FeatureExtractor(criteria["quality"]["keypoint_confidence"],args.side)
    smooth=Smoother(criteria["quality"]["smoothing_seconds"])
    rules=RuleEngine(criteria); cycle=LiftCycle(criteria); standing=StandingAssessment(criteria)
    extractor=PoseExtractor(); overlay=Overlay()
    source=int(args.source) if str(args.source).isdigit() else args.source
    sound=None
    camera=None; recorder=None; active=False; now=0.0; last_sample=-1.0; last_features_time=None
    wall_start=time.monotonic(); previous_wall=wall_start; frame_index=0
    try:
        backend=args.camera_backend
        if isinstance(source,int) and (args.camera_path or args.camera_name):
            from realtime.camera_devices import enumerate_devices, resolve_device
            selected=resolve_device(enumerate_devices(),backend,args.camera_path,args.camera_name)
            source=selected["index"];backend=selected["backend"]
        camera=Camera(source,backend=backend)
        recorder=Recorder(args.output,args.subject,args.mode,criteria)
        video_fps=camera.cap.get(cv2.CAP_PROP_FPS) if isinstance(source,str) else None
        if video_fps is not None and (not math.isfinite(video_fps) or video_fps<=0):
            raise RuntimeError("Cannot read video FPS; use a video with valid timing metadata")
        stepper=FrameStepper(camera,is_video=video_fps is not None)
        sound=AudioAlert(enabled=not args.mute)
        cv2.namedWindow("LiftSaveWithAi",cv2.WINDOW_NORMAL)
        print("Side view, camera level, full shoulder-to-ankle visibility, one person only.")
        print("Use SPACE after checking the setup; the app cannot verify the camera viewpoint.")
        while True:
            loop_started=time.monotonic()
            frame=stepper.next(active)
            if frame is None:
                if stepper.frame_index<0:
                    raise RuntimeError("Cannot read frames from selected camera/video")
                break
            frame_index=stepper.frame_index+1
            wall=time.monotonic()
            now=(frame_index-1)/video_fps if video_fps else wall-wall_start
            fps=1/max(wall-previous_wall,1e-6); previous_wall=wall
            raw=None; filtered=None; joints=None; ml=None
            assessment=Assessment("READY",["Side view / level camera / one person", "Press SPACE to confirm setup and start"])
            if active:
                result=detector.detect(frame)
                people=extractor.get_keypoints(result)
                count=len(result.boxes) if result.boxes is not None else 0
                if count==1 and len(people)==1:
                    joints=people[0]; raw=features.extract(joints)
                assessment=rules.assess(raw)
                if count!=1:
                    assessment=Assessment("UNKNOWN",["Exactly one person must be visible"])
                if raw is None:
                    smooth.reset()
                else:
                    if last_features_time is not None and now-last_features_time>criteria["quality"]["max_gap_seconds"]:
                        smooth.reset(); standing.reset()
                    filtered=smooth.update(raw,now)
                    last_features_time=now
                if args.mode=="lifting":
                    recorder.add_event(cycle.update(filtered,assessment,now))
                else:
                    assessment=standing.update(filtered,now)
                    if count!=1: assessment=Assessment("UNKNOWN",["Exactly one person must be visible"])
                if classifier: ml=classifier.predict(raw)
                # Log raw features for consistent training/inference, sample at up to 10 Hz.
                if now-last_sample>=0.1:
                    recorder.record(now,raw,cycle.phase if args.mode=="lifting" else "STANDING",assessment)
                    last_sample=now
            sound.update(assessment.alert_level,active=active and args.mode=="lifting")
            rendered=overlay.draw(frame,joints,filtered,assessment,cycle.phase if active and args.mode=="lifting" else args.mode.upper(),
                                  cycle.total,criteria["quality"]["keypoint_confidence"],fps,ml)
            cv2.imshow("LiftSaveWithAi",rendered)
            delay=max(1,round(1000/video_fps-(time.monotonic()-loop_started)*1000)) if video_fps and active else (30 if video_fps else 1)
            key=cv2.waitKey(delay)&0xff
            if key in (27,ord('q')): break
            if key in (32,ord('r')):
                sound.silence()
                recorder.add_event(cycle.abort(now))
                cycle.reset(); features.reset(); smooth.reset(); standing.reset()
                last_features_time=None
                if key==32: active=not active
                else: active=False
            if cv2.getWindowProperty("LiftSaveWithAi",cv2.WND_PROP_VISIBLE)<1: break
    finally:
        if sound: sound.close()
        if camera: camera.release()
        cv2.destroyAllWindows()
        if recorder:
            recorder.add_event(cycle.abort(now))
            recorder.close()
            print(f"Reports: {recorder.folder}")

if __name__=="__main__":
    try:
        if len(sys.argv)==1:
            from launcher import main as launch
            launch()
        else:
            main()
    except (ImportError,FileNotFoundError,RuntimeError,ValueError) as exc:
        raise SystemExit(f"Cannot start/continue: {exc}")
