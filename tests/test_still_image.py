import queue
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import numpy as np
from PIL import Image
import config
from launcher import build_command
from monitoring.still_image import load_image, assess_image_person
from monitoring.rules import validate_settings
from test_front_bend import skeleton

class StillImageTests(unittest.TestCase):
    def test_unicode_image_color_and_orientation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ภาพ ทดสอบ.png'
            Image.new('RGB',(20,30),(255,0,0)).save(path)
            arr=load_image(path)
            self.assertEqual(arr.shape,(30,20,3));self.assertEqual(arr[0,0].tolist(),[0,0,255])
            exif=Image.Exif();exif[274]=6
            Image.new('RGB',(20,30)).save(path.with_suffix('.jpg'),exif=exif)
            self.assertEqual(load_image(path.with_suffix('.jpg')).shape,(20,30,3))
            path.write_text('invalid')
            with self.assertRaises(ValueError):load_image(path)
    def test_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ภาพ คน.png';Image.new('RGB',(20,20)).save(path)
            model=Path(tmp)/'pose.pt';model.touch()
            settings=dict(mode='monitoring',source_type='image',image=str(path),model=str(model),side='auto',subject='',sound=True)
            cmd=build_command(settings)
            self.assertIn('--image',cmd);self.assertEqual(cmd[cmd.index('--source')+1],str(path))
            settings['image']=''
            with self.assertRaises(ValueError):build_command(settings)
    def test_static_geometry_no_temporal_claims_or_settings_mutation(self):
        settings=validate_settings(dict(posture_dwell=120,leg_dwell=120,forbidden_dwell=120))
        before=dict(settings)
        obs=dict(head=30,head_candidates={'side':30},inside=True,distance=0,leg=True,raised_sides=['left'])
        for _ in range(3):
            p=assess_image_person(1,obs,skeleton(160),config.load_criteria(),settings,'hazard')
            self.assertEqual(p['level'],'DANGER');self.assertFalse(p['temporal_assessed'])
            self.assertEqual(p['neck_seconds'],0);self.assertIsNone(p['lift_reps']);self.assertIsNone(p['zone_episode'])
            self.assertTrue(any('ภาพเดียว' in x for x in p['reasons']))
        self.assertEqual(settings,before)
        p2=assess_image_person(2,dict(head_candidates={},inside=False,distance=1,leg=False),skeleton(),config.load_criteria(),settings,'hazard')
        self.assertFalse(p2['danger_reasons'])
        p3=assess_image_person(3,obs,skeleton(),config.load_criteria(),settings,'forbidden')
        self.assertIn('เข้าเขตห้ามเข้า',p3['danger_reasons'])
    def test_runner_predict_once_per_click_no_camera_no_recording(self):
        from monitoring import runner
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.png';Image.new('RGB',(20,20)).save(path)
            model=types.SimpleNamespace(predict=Mock(return_value=[types.SimpleNamespace(boxes=None)]),track=Mock())
            camera=Mock(side_effect=AssertionError('must not open camera'))
            audio=Mock(error=None)
            dashboards=[]
            class Dashboard:
                def __init__(self,*a):
                    self.url='http://test';self.commands=queue.Queue();self.commands.put({'action':'start'})
                    self.renders=0;self.closed=False;dashboards.append(self)
                def publish(self,**values):
                    if values.get('error'):raise AssertionError(values['error'])
                    if 'people' in values and values.get('active') is False:
                        self.renders+=1
                        if self.renders==3:
                            self.commands.put({'action':'settings','settings':{'posture_dwell':7}})
                            self.commands.put({'action':'start'})
                        if self.renders==6:self.commands.put({'action':'stop'})
                def frame(self,*a):pass
                def close(self):self.closed=True
            cv=types.SimpleNamespace(IMWRITE_JPEG_QUALITY=1,imencode=lambda *a:(True,np.array([1],dtype=np.uint8)))
            modules={'cv2':cv,'realtime.camera':types.SimpleNamespace(Camera=camera),
                'pose.detector':types.SimpleNamespace(PoseDetector=lambda *a:types.SimpleNamespace(model=model)),
                'pose.extractor':types.SimpleNamespace(PoseExtractor=lambda:types.SimpleNamespace(get_keypoints=lambda r:[]))}
            args=types.SimpleNamespace(output=tmp,model='test.pt',device='cpu',source=str(path),image=True,camera_backend=0,camera_path='',camera_name='',mute=False,subject='test')
            with patch.dict('sys.modules',modules),patch.object(runner,'Dashboard',Dashboard),patch('realtime.audio_alert.AudioAlert',return_value=audio) as audio_class,patch.object(runner.webbrowser,'open'),patch.object(config,'DATA_ROOT',Path(tmp)),patch.object(runner.EventRecorder,'record') as record:
                runner.run(args)
            self.assertEqual(model.predict.call_count,2);model.track.assert_not_called();camera.assert_not_called();record.assert_not_called()
            audio_class.assert_called_once_with(enabled=False);audio.update.assert_not_called()
            self.assertTrue(dashboards[0].closed)
