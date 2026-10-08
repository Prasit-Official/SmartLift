import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from launcher import build_command
from realtime.playback import FrameStepper

class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.model=self.root/'pose model.pt';self.model.write_bytes(b'test')
        self.options=dict(mode='lifting',source_type='camera',camera='0',video='',subject='P001',sound=True,side='auto',model=str(self.model))
    def tearDown(self):self.temp.cleanup()
    def test_camera_and_mute(self):
        self.options.update(camera='2',sound=False,mode='standing')
        cmd=build_command(self.options,root=self.root,frozen=False)
        self.assertEqual(cmd[cmd.index('--source')+1],'2')
        self.assertEqual(cmd[cmd.index('--mode')+1],'standing');self.assertIn('--mute',cmd)
    def test_monitoring_mode(self):
        self.options["mode"]="monitoring"
        cmd=build_command(self.options)
        self.assertEqual(cmd[cmd.index("--mode")+1],"monitoring")
    def test_invalid_camera(self):
        for value in ['-1','abc','1.5','100']:
            self.options['camera']=value
            with self.assertRaises(ValueError):build_command(self.options)
    def test_missing_video(self):
        self.options.update(source_type='video',video=str(self.root/'missing.mp4'))
        with self.assertRaises(ValueError):build_command(self.options)
    def test_missing_model(self):
        self.options['model']=str(self.root/'missing.pt')
        with self.assertRaises(ValueError):build_command(self.options)
    def test_video_unicode_spaces_roundtrip(self):
        video=self.root/'วิดีโอ ทดลอง & 1.mp4';video.write_bytes(b'test')
        self.options.update(source_type='video',video=str(video),subject='ผู้ฝึก A & B')
        # A stand-in runner verifies actual subprocess argument boundaries.
        (self.root/'app.py').write_text('import sys,json;print(json.dumps(sys.argv[1:],ensure_ascii=False))',encoding='utf-8')
        cmd=build_command(self.options,root=self.root,executable=sys.executable,frozen=False)
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',check=True)
        args=json.loads(result.stdout)
        self.assertEqual(args[args.index('--source')+1],str(video.resolve()))
        self.assertEqual(args[args.index('--subject')+1],'ผู้ฝึก A & B')
    def test_compiled_launch_no_script_argument(self):
        cmd=build_command(self.options,executable='LiftSaveWithAi.exe',frozen=True)
        self.assertEqual(cmd[:2],['LiftSaveWithAi.exe','--mode'])

class FakeCamera:
    def __init__(self):self.reads=0
    def read(self):
        self.reads+=1
        return np.full((2,2,3),self.reads,dtype=np.uint8) if self.reads<=4 else None

class PlaybackTests(unittest.TestCase):
    def test_paused_video_does_not_advance(self):
        camera=FakeCamera();p=FrameStepper(camera,True)
        for _ in range(10):p.next(False)
        self.assertEqual(camera.reads,1);self.assertEqual(p.frame_index,0)
    def test_resume_uses_current_frame_then_advances(self):
        camera=FakeCamera();p=FrameStepper(camera,True)
        p.next(False);p.next(True);self.assertEqual(camera.reads,1)
        p.next(True);self.assertEqual(camera.reads,2)
        p.next(False);p.next(False);p.next(True);self.assertEqual(camera.reads,2)
        p.next(True);self.assertEqual(camera.reads,3)
    def test_camera_preview_keeps_running(self):
        camera=FakeCamera();p=FrameStepper(camera,False)
        p.next(False);p.next(False);self.assertEqual(camera.reads,2)
    def test_overlay_cannot_mutate_cached_frame(self):
        p=FrameStepper(FakeCamera(),True)
        image=p.next(False);image[:]=0
        self.assertTrue((p.next(False)==1).all())
    def test_end_of_video(self):
        p=FrameStepper(FakeCamera(),True)
        for _ in range(4):self.assertIsNotNone(p.next(True))
        self.assertIsNone(p.next(True))

if __name__=='__main__':unittest.main()
