"""Bounded, per-track/reason snapshots with a JSONL audit trail."""
from datetime import datetime, timezone
import json
import time

class EventRecorder:
    def __init__(self,folder,cooldown=10,limit=500):
        self.folder=folder;folder.mkdir(parents=True,exist_ok=True)
        self.cooldown=cooldown;self.limit=limit;self.last={};self.events=[]
    def record(self,people,jpeg,source_seconds,now=None,crops=None):
        now=time.monotonic() if now is None else now
        pending=[]
        for person in people:
            reasons=person.get('danger_reasons',[])
            key=(person['id'],tuple(reasons),person.get('zone_episode'))
            if reasons and now-self.last.get(key,-float('inf'))>=self.cooldown:pending.append((person,key))
        if pending and len(self.events)>=self.limit:raise RuntimeError('ครบเพดานบันทึก 500 ภาพในรอบนี้แล้ว')
        for person,key in pending:
            if len(self.events)>=self.limit:break
            name=f'event-{len(self.events)+1:05d}-person-{person["id"]}.jpg'
            target=self.folder/name
            target.write_bytes(jpeg)
            crop_name=None
            if crops and person['id'] in crops:
                crop_name=name.replace('.jpg','-crop.jpg')
                (self.folder/crop_name).write_bytes(crops[person['id']])
            item=dict(image=name,crop=crop_name,id=person['id'],reasons=list(person['danger_reasons']),
                      session=self.folder.name,review_status='pending',angles=person.get('angles'),front_bend=person.get('front_bend'),front_bend_seconds=person.get('front_bend_seconds'),
                      zone_type=person.get('zone_type'),zone_inside=person.get('zone_inside'),
                      zone_source=person.get('zone_source'),raised_sides=person.get('raised_sides'),
                      head_angle=person.get('head_angle'),head_method=person.get('head_method'),
                      leg_height=person.get('leg_height'),zone_episode=person.get('zone_episode'),
                      box=person.get('box'),lift_reps=person.get('lift_reps'),
                      inside_seconds=person.get('inside_seconds'),leg_seconds=person.get('leg_seconds'),
                      zone_record_after=person.get('zone_record_after'),posture_seconds=person.get('posture_seconds'),
                      neck_seconds=person.get('neck_seconds'),standing_seconds=person.get('standing_seconds'),
                      source_seconds=round(source_seconds,3),created_at=datetime.now(timezone.utc).isoformat())
            try:
                with (self.folder/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(item,ensure_ascii=False)+'\n')
            except OSError:
                target.unlink(missing_ok=True)
                if crop_name:(self.folder/crop_name).unlink(missing_ok=True)
                raise
            self.events.append(item);self.last[key]=now
        return self.events[-50:][::-1]
