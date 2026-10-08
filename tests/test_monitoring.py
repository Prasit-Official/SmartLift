import json
import tempfile
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from monitoring.rules import SafetyEngine, DEFAULTS, observations, validate_settings, validate_zone, distance_to_zone
from monitoring.events import EventRecorder
from monitoring.server import Dashboard


def obs(head=0, distance=1, leg=False, side=3):
    return dict(head=head,head_side=side,distance=distance,leg=leg)

def calibrated():
    engine=SafetyEngine();engine.update(1,obs(),0);engine.calibrate()
    for i in range(1,7):engine.update(1,obs(),i*.4)
    return engine

class MonitoringRulesTests(unittest.TestCase):
    def test_neck_thresholds(self):
        e=calibrated()
        for i in range(101):p=e.update(1,obs(30),3+i*.1)
        self.assertEqual(p['level'],'DANGER');self.assertEqual(p['neck_seconds'],10)
    def test_warning_before_danger(self):
        e=calibrated()
        for i in range(61):p=e.update(1,obs(30),3+i*.1)
        self.assertEqual(p['level'],'WARNING')
    def test_no_calibration_no_neck_alert(self):
        e=SafetyEngine()
        for i in range(150):p=e.update(1,obs(50),i*.1)
        self.assertEqual(p['level'],'UNKNOWN');self.assertEqual(p['neck_seconds'],0)
    def test_people_independent(self):
        e=calibrated()
        for i in range(120):
            a=e.update(1,obs(30),3+i*.1);b=e.update(2,obs(30),3+i*.1)
        self.assertEqual(a['level'],'DANGER');self.assertEqual(b['level'],'UNKNOWN')
    def test_missing_head_resets_duration(self):
        e=calibrated()
        for i in range(80):e.update(1,obs(30),3+i*.1)
        p=e.update(1,obs(None),11)
        self.assertEqual(p['neck_seconds'],0);self.assertEqual(p['level'],'UNKNOWN')
    def test_gap_drops_calibration(self):
        e=calibrated();p=e.update(1,obs(30),20)
        self.assertFalse(p['calibrated'])
    def test_missing_track_clears_timer_preserves_brief_calibration(self):
        e=calibrated();e.tracks[1].starts['neck']=1
        e.finish_frame(set());self.assertFalse(e.tracks[1].starts)
        self.assertIsNotNone(e.tracks[1].baseline)
        e.now=10;e.finish_frame(set());self.assertFalse(e.tracks)
    def test_changed_side_requires_calibration(self):
        e=calibrated();p=e.update(1,obs(30,side=4),2.5)
        self.assertFalse(p['calibrated'])
    def test_pause_reset(self):
        e=calibrated();e.reset();self.assertFalse(e.tracks)
    def test_leg_in_zone_danger_after_dwell(self):
        e=SafetyEngine({"leg_dwell":1})
        for i in range(12):p=e.update(1,obs(distance=.02,leg=True),i*.1)
        self.assertEqual(p['level'],'DANGER')
    def test_leg_away_from_zone_no_alert(self):
        e=SafetyEngine()
        for i in range(30):p=e.update(1,obs(distance=.3,leg=True),i*.1)
        self.assertFalse(p['danger_reasons'])
    def test_zone_without_leg_warning(self):
        e=SafetyEngine()
        for i in range(10):p=e.update(1,obs(distance=0),i*.1)
        self.assertEqual(p['level'],'WARNING')
    def test_bad_configuration(self):
        for settings in [dict(neck_danger=4),dict(max_people=2.3),dict(head_delta=float('nan')),dict(x=1),None]:
            with self.assertRaises(ValueError):validate_settings(settings)
    def test_zone_validation(self):
        p=validate_zone([[.1,.1],[.9,.1],[.9,.9],[.1,.9]])
        self.assertEqual(distance_to_zone((.5,.5),p),0)
        self.assertAlmostEqual(distance_to_zone((1,.5),p),.1)
        for bad in [[],[[0,0],[1,1],[0,1],[1,0]],[[0,0],[2,0],[0,1]]]:
            with self.assertRaises(ValueError):validate_zone(bad)
    def test_20_people_states(self):
        e=SafetyEngine()
        for i in range(20):e.update(i,obs(),0)
        self.assertEqual(len(e.tracks),20)
    def test_missing_keypoints(self):
        result=observations([], (720,1280,3),[],.5)
        self.assertIsNone(result['head']);self.assertIsNone(result['leg'])
    def test_low_confidence_never_interpreted_as_zero(self):
        kp=[dict(x=0,y=0,confidence=.1) for _ in range(17)]
        result=observations(kp,(720,1280,3),[[0,0],[1,0],[1,1],[0,1]],.5)
        self.assertIsNone(result['near']);self.assertIsNone(result['head'])
    def test_calibration_requires_stability(self):
        e=SafetyEngine();e.update(1,obs(),0);e.calibrate()
        for i in range(1,20):p=e.update(1,obs(30 if i%2 else 0),i*.2)
        self.assertFalse(p['calibrated'])

class EventTests(unittest.TestCase):
    def test_danger_only_cooldown_and_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=EventRecorder(Path(tmp));p=dict(id=1,danger_reasons=[])
            self.assertEqual(r.record([p],b'jpeg',0,0),[])
            p['danger_reasons']=['test'];r.record([p],b'jpeg',1,0);r.record([p],b'jpeg',2,1)
            self.assertEqual(len(r.events),1)
            r.record([p],b'jpeg',12,11);self.assertEqual(len(r.events),2)
            self.assertEqual(len((Path(tmp)/'events.jsonl').read_text().splitlines()),2)
            self.assertEqual((Path(tmp)/r.events[0]['image']).read_bytes(),b'jpeg')
    def test_record_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=EventRecorder(Path(tmp),limit=1);p=dict(id=1,danger_reasons=['test'])
            r.record([p],b'jpeg',0,0)
            with self.assertRaises(RuntimeError):r.record([p],b'jpeg',11,11)

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(Path(self.tmp.name))
    def tearDown(self):self.d.close();self.tmp.cleanup()
    def test_page_and_state(self):
        with urllib.request.urlopen(self.d.url) as r:html=r.read().decode()
        self.assertIn(self.d.token,html);self.assertNotIn('__TOKEN__',html)
        self.d.publish(active=True)
        with urllib.request.urlopen(self.d.url+'/api/state') as r:self.assertTrue(json.load(r)['active'])
    def test_control_requires_token_and_origin(self):
        req=urllib.request.Request(self.d.url+'/api/control',data=b'{"action":"start"}')
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        self.assertEqual(e.exception.code,403)
        req.add_header('X-LiftSave-Token',self.d.token);req.add_header('Origin',self.d.url)
        with urllib.request.urlopen(req) as r:self.assertEqual(r.status,202)
        self.assertEqual(self.d.commands.get_nowait()['action'],'start')
    def test_snapshot_access_only_known_events(self):
        (Path(self.tmp.name)/'secret.jpg').write_bytes(b'secret')
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(self.d.url+'/events/secret.jpg')
        self.d.publish(events=[{'image':'secret.jpg'}])
        with urllib.request.urlopen(self.d.url+'/events/secret.jpg') as r:self.assertEqual(r.read(),b'secret')

class ObservationGeometryTests(unittest.TestCase):
    def joints(self):
        kp=[dict(x=0,y=0,confidence=0) for _ in range(17)]
        for i,(x,y) in {0:(145,65),3:(120,65),5:(120,100),6:(160,100),11:(120,200),12:(160,200),13:(120,300),14:(160,300),15:(120,400),16:(160,400)}.items():
            kp[i]=dict(x=x,y=y,confidence=.9)
        return kp
    def test_neutral_and_raised_head_geometry(self):
        kp=self.joints();self.assertAlmostEqual(observations(kp,(500,500,3),[],.5)['head'],0)
        kp[0]['y']=40;self.assertAlmostEqual(observations(kp,(500,500,3),[],.5)['head'],45)
    def test_standing_and_raised_leg_geometry(self):
        kp=self.joints();zone=validate_zone([[.1,.7],[.5,.7],[.5,.95],[.1,.95]])
        neutral=observations(kp,(500,500,3),zone,.5)
        self.assertFalse(neutral['leg']);self.assertEqual(neutral['distance'],0)
        kp[13].update(x=200,y=250);kp[15].update(x=150,y=290)
        self.assertTrue(observations(kp,(500,500,3),zone,.5)['leg'])

class RunnerIntegrationTests(unittest.TestCase):
    def test_video_start_pause_resume_eof_and_cleanup_with_mock_model(self):
        # Actual runner control loop, fake image codec/model/camera; no CV accuracy claim.
        import queue
        import types
        import numpy as np
        from unittest.mock import patch
        from monitoring import runner
        with tempfile.TemporaryDirectory() as tmp:
            captures=[];dashboards=[];alerts=[]
            class FakeCamera:
                def __init__(self,*a):self.reads=0;self.cap=self;self.released=False;captures.append(self)
                def get(self,*a):return 30
                def read(self):
                    self.reads+=1
                    return np.zeros((20,20,3),dtype=np.uint8) if self.reads<=3 else None
                def release(self):self.released=True
            class FakeDashboard:
                def __init__(self,*a):
                    self.commands=queue.Queue();self.commands.put({'action':'start'});self.url='http://test';self.stage=0;self.closed=False;self.counts=[];dashboards.append(self)
                def publish(self,**values):
                    if values.get('active') and 'people' in values:
                        if self.stage==0:self.commands.put({'action':'pause'});self.stage=1
                    elif values.get('active') is False and 'people' in values and self.stage==1:
                        self.counts.append(captures[0].reads);self.commands.put({'action':'start'});self.stage=2
                    if values.get('ended'):self.commands.put({'action':'stop'})
                def frame(self,*a):pass
                def close(self):self.closed=True
            class FakeAudio:
                def __init__(self,*a,**kw):self.error=None;self.closed=False;alerts.append(self)
                def update(self,*a):pass
                def silence(self):pass
                def close(self):self.closed=True
            class Model:
                def track(self,*a,**kw):return [types.SimpleNamespace(boxes=None)]
            cv=types.SimpleNamespace(CAP_PROP_FPS=5,IMWRITE_JPEG_QUALITY=1,imencode=lambda *a:(True,np.array([1,2,3],dtype=np.uint8)))
            modules={'cv2':cv,'realtime.camera':types.SimpleNamespace(Camera=FakeCamera),
                     'pose.detector':types.SimpleNamespace(PoseDetector=lambda *a:types.SimpleNamespace(model=Model())),
                     'pose.extractor':types.SimpleNamespace(PoseExtractor=lambda:types.SimpleNamespace(get_keypoints=lambda r:[]))}
            args=types.SimpleNamespace(output=tmp,model='test.pt',device='cpu',source='video.mp4',camera_backend=0,camera_path='',camera_name='',mute=True,subject='test')
            with patch.dict('sys.modules',modules),patch.object(runner,'Dashboard',FakeDashboard),patch('realtime.audio_alert.AudioAlert',FakeAudio),patch.object(runner.webbrowser,'open'),patch.object(runner.time,'sleep'):
                runner.run(args)
            self.assertEqual(dashboards[0].counts,[1])
            self.assertEqual(captures[0].reads,4);self.assertTrue(captures[0].released)
            self.assertTrue(dashboards[0].closed);self.assertTrue(alerts[0].closed)
