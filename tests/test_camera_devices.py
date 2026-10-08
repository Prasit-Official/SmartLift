import unittest
from realtime.camera_devices import display_labels,preferred_index,resolve_device
from launcher import build_command
from unittest.mock import patch,MagicMock
from pathlib import Path
import tempfile,sys,importlib

class DeviceTests(unittest.TestCase):
    def devices(self):
        return [dict(index=0,backend=700,name='Integrated Camera',path='internal'),dict(index=1,backend=700,name='USB Camera',path='usb-A')]
    def test_real_names_not_numeric(self):
        self.assertEqual(display_labels(self.devices()),['Integrated Camera','USB Camera'])
    def test_duplicate_names_are_distinct(self):
        d=self.devices();d[0]['name']='USB Camera'
        labels=display_labels(d);self.assertEqual(len(set(labels)),2)
        self.assertTrue(all('USB Camera' in x for x in labels))
    def test_same_device_after_reorder(self):
        d=self.devices();d[1]['index']=0;d[0]['index']=1
        resolved=resolve_device(d,700,path='usb-A',name='USB Camera')
        self.assertEqual(resolved['index'],0)
    def test_removed_device_not_replaced_silently(self):
        with self.assertRaises(RuntimeError):resolve_device(self.devices(),700,path='missing',name='USB Camera')
    def test_restore_by_path_not_old_number(self):
        self.assertEqual(preferred_index(list(reversed(self.devices())),'internal'),1)
    def test_missing_previous_selection_stays_empty(self):
        self.assertEqual(preferred_index(self.devices(),'removed'),-1)
    def test_duplicate_names_without_path_rejected(self):
        d=self.devices();d[0]['name']='USB Camera'
        with self.assertRaises(RuntimeError):resolve_device(d,700,name='USB Camera')
    def test_no_cameras(self):
        self.assertEqual(display_labels([]),[]);self.assertEqual(preferred_index([]),-1)
    def test_video_has_no_device_flags(self):
        with tempfile.TemporaryDirectory() as t:
            model=Path(t)/'model.pt';model.touch();video=Path(t)/'video.mp4';video.touch()
            s=dict(mode='lifting',source_type='video',video=str(video),camera='0',model=str(model),side='auto',subject='P001',sound=True,camera_name='USB Camera',camera_backend=700,camera_path='usb-A')
            cmd=build_command(s,frozen=False)
            self.assertNotIn('--camera-backend',cmd)
            s['source_type']='camera';cmd=build_command(s,frozen=False)
            self.assertEqual(cmd[cmd.index('--camera-path')+1],'usb-A')
            self.assertEqual(cmd[cmd.index('--camera-backend')+1],'700')
    def test_capture_backend_matches_enumeration(self):
        fake=MagicMock();fake.VideoCapture.return_value.isOpened.return_value=True
        with patch.dict(sys.modules,{'cv2':fake}):
            # Camera module is not otherwise loaded by headless unit tests.
            sys.modules.pop('realtime.camera',None)
            module=importlib.import_module('realtime.camera')
            module.Camera(2,backend=700)
            fake.VideoCapture.assert_called_with(2,700)
            module.Camera('test.mp4',backend=700)
            fake.VideoCapture.assert_called_with('test.mp4')
            sys.modules.pop('realtime.camera',None)

if __name__=='__main__':unittest.main()
