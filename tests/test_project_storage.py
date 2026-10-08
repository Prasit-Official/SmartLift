import os
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

class ProjectStorageTests(unittest.TestCase):
    def test_default_reports_inside_project(self):
        root=Path(__file__).resolve().parents[1]
        env={k:v for k,v in os.environ.items() if k!='LIFTSAVE_DATA_DIR'}
        with patch.dict(os.environ,env,clear=True):values=runpy.run_path(str(root/'config.py'))
        self.assertEqual(values['REPORT_DIR'],root/'reports')
        self.assertEqual(values['DATA_ROOT'],root)
    def test_explicit_override_still_works(self):
        root=Path(__file__).resolve().parents[1]
        with patch.dict(os.environ,{'LIFTSAVE_DATA_DIR':str(root/'custom-data')}):values=runpy.run_path(str(root/'config.py'))
        self.assertEqual(values['REPORT_DIR'],root/'custom-data'/'reports')
    def test_frozen_stores_next_to_executable(self):
        root=Path(__file__).resolve().parents[1]
        env={k:v for k,v in os.environ.items() if k!='LIFTSAVE_DATA_DIR'}
        with patch.dict(os.environ,env,clear=True),patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(root/'bin'/'LiftSave.exe')):
            values=runpy.run_path(str(root/'config.py'))
        self.assertEqual(values['REPORT_DIR'],root/'bin'/'reports')
