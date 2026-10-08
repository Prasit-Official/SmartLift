"""Validated monitoring settings persisted independently of source-specific zones."""
import json
from monitoring.rules import validate_settings

def load_settings(path):
    try:return validate_settings(json.loads(path.read_text(encoding='utf-8'))),None
    except FileNotFoundError:return validate_settings({}),None
    except (OSError,ValueError) as exc:return validate_settings({}),'อ่านค่าที่บันทึกไม่ได้ ใช้ค่าเริ่มต้น: '+str(exc)

def save_settings(path,values):
    settings=validate_settings(values)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)
    return settings
