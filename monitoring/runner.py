"""One inference producer; dashboard consumers never advance the source."""
import json
import math
import queue
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from monitoring.rules import observations, validate_settings, validate_zone
from monitoring.unified import UnifiedEngine
import config
from monitoring.server import Dashboard
from monitoring.events import EventRecorder
from monitoring.preferences import load_settings, save_settings

COLORS={'NONE':(100,200,80),'UNKNOWN':(170,170,170),'WARNING':(0,200,255),'DANGER':(50,50,240)}

def run(args):
    import cv2
    from realtime.camera import Camera
    from realtime.audio_alert import AudioAlert
    from pose.detector import PoseDetector
    from pose.extractor import PoseExtractor
    folder=Path(args.output)/('monitor-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    recorder=EventRecorder(folder)
    dashboard=Dashboard(folder)
    camera=None;sound=None
    try:
        print('Dashboard:',dashboard.url,flush=True)
        webbrowser.open(dashboard.url)
        detector=PoseDetector(args.model,args.device);extractor=PoseExtractor()
        is_image=getattr(args,'image',False)
        source=int(args.source) if str(args.source).isdigit() else args.source
        backend=args.camera_backend
        if isinstance(source,int) and (args.camera_path or args.camera_name):
            from realtime.camera_devices import enumerate_devices,resolve_device
            selected=resolve_device(enumerate_devices(),backend,args.camera_path,args.camera_name)
            source=selected['index'];backend=selected['backend']
        if not is_image:camera=Camera(source,backend)
        is_video=isinstance(source,str) and not is_image
        fps=camera.cap.get(cv2.CAP_PROP_FPS) if is_video else None
        if is_video and (not math.isfinite(fps) or fps<=0):raise RuntimeError('อ่าน FPS ของวิดีโอไม่ได้')
        sound=AudioAlert(enabled=not args.mute and not is_image)
        criteria=config.load_criteria(getattr(args,"criteria",None))
        preferences_path=config.DATA_ROOT/"monitoring_settings.json"
        settings_source=preferences_path if preferences_path.exists() else config.LEGACY_DATA_ROOT/'monitoring_settings.json'
        saved_settings,settings_error=load_settings(settings_source)
        engine=UnifiedEngine(criteria,saved_settings,side=getattr(args,"side","auto"));zone=[];zone_type="hazard";active=False;ended=False;stop=False;frame_index=0
        if is_image:
            from monitoring.still_image import load_image, assess_image_person
            frame=load_image(args.source)
        else:frame=camera.read()
        if frame is None:raise RuntimeError('อ่านภาพแรกไม่ได้')
        dashboard.publish(status='พร้อม: วาดเขต แล้วเริ่มเฝ้าระวัง',settings=engine.settings,zone=[],zone_type=zone_type,
                          current_session=folder.name,output=str(folder),error=settings_error or '',sound_error=sound.error,is_video=is_video,is_image=is_image)
        recorder.cooldown=engine.settings['snapshot_cooldown']
        start=time.monotonic();last_render=0.;people=[];last_infer=0.;measured_fps=0.
        def save_config():
            (folder/'session.json').write_text(json.dumps(dict(settings=engine.settings,zone=zone,zone_type=zone_type,
                source_type='image' if is_image else 'video' if is_video else 'camera',subject=args.subject,criteria=criteria,
                note='Experimental 2D proxies; track IDs are not identities'),ensure_ascii=False,indent=2),encoding='utf-8')
        save_config()
        if is_image:dashboard.publish(status='พร้อมทดสอบภาพ: วาดเขตตามต้องการ แล้วกดวิเคราะห์ภาพ')
        while not stop:
            began=time.monotonic()
            while True:
                try:cmd=dashboard.commands.get_nowait()
                except queue.Empty:break
                try:
                    action=cmd['action']
                    if action=='stop':stop=True;active=False;sound.silence()
                    elif action=='start':
                        if ended:raise ValueError('วิดีโอจบแล้ว กรุณาปิดรอบนี้และเปิดใหม่จากเมนู')
                        active=True;dashboard.publish(active=True,status='กำลังวิเคราะห์ภาพ' if is_image else 'กำลังเฝ้าระวัง',error='')
                    elif action=='pause':
                        active=False;engine.reset();people=[];sound.silence();dashboard.publish(status='พัก — เริ่มใหม่ได้ ใช้เกณฑ์หัวอัตโนมัติหรือตั้งท่าปกติเพิ่ม')
                    elif action=='calibrate':
                        if is_image:raise ValueError('ภาพนิ่งไม่รองรับการตั้งศีรษะปกติแบบจับเวลา')
                        if not active or not engine.tracks:raise ValueError('เริ่มเฝ้าระวังและรอให้มี ID ก่อนตั้งศีรษะปกติ')
                        engine.calibrate();dashboard.publish(status='ให้ทุกคนมองตรงตามปกติด้านข้างค้าง 2 วินาที')
                    elif action=='zone':
                        if active:raise ValueError('กดพักก่อนแก้เขต')
                        chosen_type=cmd.get('zone_type',zone_type)
                        if chosen_type not in ('forbidden','hazard'):raise ValueError('ชนิดเขตไม่ถูกต้อง')
                        new_zone=[] if cmd.get('points')==[] else validate_zone(cmd.get('points'))
                        zone=new_zone;zone_type=chosen_type;engine.safety.zone_type=zone_type
                        engine.reset();save_config();dashboard.publish(zone=zone,zone_type=zone_type,error='',zone_result=dict(request_id=cmd.get('request_id'),ok=True))
                    elif action=='settings':
                        if active:raise ValueError('กดพักก่อนแก้เกณฑ์')
                        settings=save_settings(preferences_path,cmd.get('settings'))
                        engine=UnifiedEngine(criteria,settings,getattr(args,"side","auto"))
                        engine.safety.zone_type=zone_type
                        recorder.cooldown=engine.settings['snapshot_cooldown'];save_config()
                        dashboard.publish(settings=engine.settings,error='',status='บันทึกค่าและเตรียมใช้งานแล้ว กดเริ่มเพื่อใช้งาน',
                            settings_result=dict(request_id=cmd.get('request_id'),ok=True,saved_at=time.time(),settings=engine.settings))
                    if is_image and action in ('zone','settings'):
                        people=[];dashboard.publish(people=[],detected=0,capped=False,status='เปลี่ยนค่าแล้ว กดวิเคราะห์ภาพใหม่')
                except (ValueError,TypeError,OSError) as exc:
                    dashboard.publish(error=str(exc))
                    if cmd.get('action')=='zone':dashboard.publish(zone_result=dict(request_id=cmd.get('request_id'),ok=False,error=str(exc)))
                    if cmd.get('action')=='settings':
                        dashboard.publish(settings=engine.settings,settings_result=dict(request_id=cmd.get('request_id'),ok=False,error=str(exc)))
            if stop:break
            if active:
                if last_infer and not is_image: # Keep first frame until first start, advance only once/inference.
                    next_frame=camera.read()
                    if next_frame is None:
                        active=False;ended=True;engine.reset();people=[];sound.silence()
                        dashboard.publish(status='วิดีโอจบแล้ว' if is_video else 'รับภาพขาดหาย — กรุณาปิดและเปิดใหม่',ended=True)
                    else:
                        frame=next_frame;frame_index+=1
                if active:
                    tick=0 if is_image else frame_index/fps if is_video else time.monotonic()-start
                    infer=detector.model.predict if is_image else detector.model.track
                    tracking={} if is_image else dict(persist=True,tracker='bytetrack.yaml')
                    result=infer(frame,**tracking,
                        conf=.35,iou=.45,device=args.device,verbose=False,max_det=engine.settings['max_people'])[0]
                    joints=extractor.get_keypoints(result);boxes=result.boxes
                    ids=[] if boxes is None or boxes.id is None else boxes.id.int().cpu().tolist()
                    coords=[] if boxes is None else boxes.xyxy.cpu().tolist()
                    if is_image:ids=list(range(1,len(coords)+1))
                    people=[]
                    for person_id,kp,box in zip(ids,joints,coords):
                        obs=observations(kp,frame.shape,zone,engine.settings['confidence'],box,engine.settings['leg_rise'],engine.settings['head_confidence'])
                        person=assess_image_person(person_id,obs,kp,criteria,engine.settings,zone_type,getattr(args,'side','auto')) if is_image else engine.update(person_id,obs,tick,kp)
                        person['box']=box
                        person['visible_points']={i:(int(p['x']),int(p['y'])) for i,p in enumerate(kp) if math.isfinite(p['x']) and math.isfinite(p['y']) and p['confidence'] >= (engine.settings['head_confidence'] if i<5 else engine.settings['confidence'])}
                        people.append(person)
                    engine.safety.now=tick
                    engine.finish_frame({p['id'] for p in people})
                    elapsed=time.monotonic()-began;measured_fps=1/max(elapsed,.001)
                    last_infer=time.monotonic()
                    level='DANGER' if any(p['level']=='DANGER' for p in people) else 'WARNING' if any(p['level']=='WARNING' for p in people) else 'NONE'
                    if not is_image:sound.update(level)
                    else:
                        active=False
                        dashboard.publish(status='วิเคราะห์ภาพเสร็จแล้ว — ปรับเกณฑ์หรือเขตแล้ววิเคราะห์ซ้ำได้',active=False)
                    dashboard.publish(detected=len(coords),untracked=max(0,len(coords)-len(ids)),
                                      capped=len(coords)>=engine.settings['max_people'],source_seconds=round(tick,2))
            elif not is_video and not is_image and not ended:
                next_frame=camera.read()
                if next_frame is not None:frame=next_frame
            if active or time.monotonic()-last_render>.2:
                rendered=frame.copy();h,w=frame.shape[:2]
                if zone:
                    import numpy as np
                    polygon=np.array([(int(x*w),int(y*h)) for x,y in zone],dtype=np.int32)
                    tint=rendered.copy();cv2.fillPoly(tint,[polygon],(20,50,220))
                    rendered=cv2.addWeighted(tint,.18,rendered,.82,0)
                    cv2.polylines(rendered,[polygon],True,(30,70,255),2)
                for person in people:
                    x1,y1,x2,y2=map(int,person['box']);color=COLORS[person['level']]
                    cv2.rectangle(rendered,(x1,y1),(x2,y2),color,2)
                    points=person.get('visible_points',{})
                    for a,b in [(0,1),(0,2),(0,3),(0,4),(5,6),(5,11),(6,12),(5,13),(6,14),(11,13),(13,15),(12,14),(14,16)]:
                        if a in points and b in points:cv2.line(rendered,points[a],points[b],color,2)
                    for point in points.values():cv2.circle(rendered,point,3,color,-1)
                    cv2.putText(rendered,(f"ID {person['id']} STATIC {person['level']}" if is_image else f"ID {person['id']} {person['level']} {person['neck_seconds']:.1f}s"),(x1,max(20,y1-8)),cv2.FONT_HERSHEY_SIMPLEX,.55,color,2)
                ok,encoded=cv2.imencode('.jpg',rendered,[cv2.IMWRITE_JPEG_QUALITY,82])
                if not ok:raise RuntimeError('เข้ารหัสภาพไม่ได้')
                jpeg=encoded.tobytes();dashboard.frame(jpeg);last_render=time.monotonic()
                if active and not is_image:
                    try:
                        crops={}
                        for person in people:
                            if not person['danger_reasons']:continue
                            x1,y1,x2,y2=map(int,person['box'])
                            crop=rendered[max(0,y1-30):min(h,y2+15),max(0,x1-15):min(w,x2+15)]
                            if crop.size:
                                ok_crop,data=cv2.imencode('.jpg',crop,[cv2.IMWRITE_JPEG_QUALITY,90])
                                if ok_crop:crops[person['id']]=data.tobytes()
                        events=recorder.record(people,jpeg,tick,crops=crops)
                        dashboard.publish(events=events,event_count=len(recorder.events),recording_error='')
                    except (OSError,RuntimeError) as exc:dashboard.publish(recording_error='บันทึกภาพไม่สำเร็จ: '+str(exc))
                dashboard.publish(people=people,active=active,fps=round(measured_fps,1),processing_ms=round(1000/max(measured_fps,.001)) if active else None,sound_error=sound.error)
            target=1/fps if is_video and active else .05 if not active else 0
            remaining=target-(time.monotonic()-began)
            if remaining>0:time.sleep(remaining)
        dashboard.publish(status='ปิดการเฝ้าระวังแล้ว',active=False,people=[])
    except Exception as exc:
        dashboard.publish(status='เกิดข้อผิดพลาด',error=str(exc),active=False)
        if sound:sound.silence()
        print('Monitoring error:',exc,flush=True)
        # Keep the actionable error visible until the user closes the session.
        while True:
            try:
                if dashboard.commands.get(timeout=.5).get('action')=='stop':break
            except queue.Empty:pass
    finally:
        if sound:sound.close()
        if camera:camera.release()
        dashboard.close()
