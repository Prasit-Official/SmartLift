"""Discover OS camera names together with matching OpenCV indices/backends."""
import sys
from collections import Counter

def enumerate_devices():
    try:
        import cv2
        from cv2_enumerate_cameras import enumerate_cameras
    except ImportError as exc:
        raise RuntimeError('ติดตั้งตัวอ่านชื่อกล้องก่อน: python -m pip install "cv2-enumerate-cameras>=1.2,<2"') from exc
    backend=cv2.CAP_DSHOW if sys.platform=='win32' else (cv2.CAP_AVFOUNDATION if sys.platform=='darwin' else cv2.CAP_V4L2)
    return [dict(index=int(c.index),backend=int(c.backend),name=str(c.name),path=str(c.path or ''))
            for c in enumerate_cameras(backend)]

def display_labels(devices):
    counts=Counter(d['name'] for d in devices);labels=[]
    for d in devices:
        name=d['name'] or 'อุปกรณ์ไม่ระบุชื่อ'
        label=name if counts[d['name']]==1 else f"{name} (อุปกรณ์ {d['index']+1})"
        if label in labels:label+=f" [{d['backend']}:{d['index']}]"
        labels.append(label)
    return labels

def preferred_index(devices,path='',name=''):
    if path:
        matches=[i for i,d in enumerate(devices) if d['path']==path]
        return matches[0] if len(matches)==1 else -1
    if name:
        matches=[i for i,d in enumerate(devices) if d['name']==name]
        return matches[0] if len(matches)==1 else -1
    return 0 if devices else -1

def resolve_device(devices,backend,path='',name=''):
    candidates=[d for d in devices if d['backend']==backend and ((d['path']==path) if path else (d['name']==name))]
    if len(candidates)!=1:
        raise RuntimeError('กล้องที่เลือกถูกถอดหรือระบุอุปกรณ์ไม่ได้ กรุณากดรีเฟรชกล้องและเลือกใหม่')
    return candidates[0]
