"""Local review archive: session-scoped paths and human review annotations."""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

class EventArchive:
    def __init__(self,root):self.root=Path(root).resolve();self.lock=threading.RLock()
    def folder(self,session):
        if not isinstance(session,str) or not re.fullmatch(r'monitor-[0-9-]+',session):raise ValueError('รอบไม่ถูกต้อง')
        folder=self.root/session
        if folder.is_symlink() or folder.resolve().parent!=self.root or not folder.is_dir():raise ValueError('ไม่พบรอบ')
        return folder
    def sessions(self):
        return sorted([p.name for p in self.root.glob('monitor-*') if p.is_dir() and not p.is_symlink() and re.fullmatch(r'monitor-[0-9-]+',p.name)],reverse=True)
    def events(self,session):
        folder=self.folder(session);items=[]
        try:
            with (folder/'events.jsonl').open(encoding='utf-8') as f:
                for line in f:
                    try:
                        row=json.loads(line)
                        if isinstance(row,dict) and isinstance(row.get('image'),str):items.append(row)
                    except ValueError:continue # Writer may be appending the final line.
        except FileNotFoundError:pass
        with self.lock:
            try:reviews=json.loads((folder/'reviews.json').read_text(encoding='utf-8'))
            except FileNotFoundError:reviews={}
            if not isinstance(reviews,dict):raise ValueError('ไฟล์ผลตรวจไม่ถูกต้อง')
        for row in items:
            row['session']=session;row['review_status']='pending';row['review_note']=''
            row.update(reviews.get(row['image'],{}))
        return items[::-1]
    def image(self,session,name):
        if not isinstance(name,str) or Path(name).name!=name:raise ValueError('ชื่อภาพไม่ถูกต้อง')
        rows=self.events(session)
        if not any(name in (e.get('image'),e.get('crop')) for e in rows):raise ValueError('ไม่พบภาพเหตุการณ์')
        target=self.folder(session)/name
        if target.is_symlink():raise ValueError('ไม่อนุญาตลิงก์ไฟล์')
        return target.read_bytes()
    def review(self,session,image,status,note):
        if status not in ('pending','confirmed','false_alarm') or not isinstance(note,str) or len(note)>1000:raise ValueError('ผลตรวจไม่ถูกต้อง')
        with self.lock:
            if not any(e['image']==image for e in self.events(session)):raise ValueError('ไม่พบเหตุการณ์')
            folder=self.folder(session);path=folder/'reviews.json'
            try:reviews=json.loads(path.read_text(encoding='utf-8'))
            except FileNotFoundError:reviews={}
            reviews[image]=dict(review_status=status,review_note=note,reviewed_at=datetime.now(timezone.utc).isoformat())
            temp=folder/'reviews.tmp';temp.write_text(json.dumps(reviews,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
