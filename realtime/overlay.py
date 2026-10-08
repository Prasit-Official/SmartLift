"""Thai participant interface. Backend status codes and assessment rules stay stable."""
import os
from pathlib import Path
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PAIRS=[(5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16)]
COLORS={"DANGER":(55,65,240),"OBSERVED":(190,210,130),"REVIEW":(50,180,255),"UNKNOWN":(170,170,170),"READY":(255,220,100),"REMINDER":(60,220,255)}
STATUS={"OBSERVED":"ไม่พบข้อเตือนจากเกณฑ์ทดลอง", "REVIEW":"ควรทบทวนท่าทาง", "UNKNOWN":"ข้อมูลไม่เพียงพอ", "READY":"รอเริ่มฝึก", "REMINDER":"ลองเปลี่ยนอิริยาบถ", "INCOMPLETE":"รอบฝึกไม่ครบ", "UNAVAILABLE":"ยังประเมินไม่ได้"}
PHASE={"WAIT_READY":"ยืนเตรียมพร้อม", "READY":"พร้อมเริ่มรอบ", "DESCENDING":"กำลังย่อตัว", "LOWERED":"ช่วงย่อตัว", "RISING":"กำลังลุกขึ้น", "LIFTING":"ฝึกท่าทางการยก", "STANDING":"สังเกตการยืน"}
TEXT={
 "Required shoulder / hip / knee / ankle not visible":"ขยับให้กล้องเห็นไหล่ สะโพก เข่า และข้อเท้าชัดเจน",
 "Large trunk inclination with limited knee flexion":"ลำตัวเอียงมากขณะที่เข่างอน้อย ควรให้ผู้สอนช่วยทบทวน",
 "Trunk inclination exceeds prototype review threshold":"ลำตัวเอียงเกินค่าทดลอง ควรทบทวนกับผู้สอน",
 "No prototype angle flag; this is not a safety clearance":"ไม่พบข้อเตือนจากมุมที่วัดได้ ยังไม่ยืนยันความปลอดภัยทั้งหมด",
 "Standing observation interrupted":"มองเห็นท่าทางไม่ครบ กรุณาจัดตำแหน่งใหม่",
 "Outside prototype standing observation range":"ท่าปัจจุบันอยู่นอกช่วงที่ระบบใช้สังเกตการยืน",
 "Little observed angle change; consider changing position":"ท่าทางเปลี่ยนน้อยมาระยะหนึ่ง ลองเปลี่ยนอิริยาบถ",
 "Standing observation: posture variation timer active":"กำลังสังเกตการเปลี่ยนท่าทางขณะยืน",
 "Exactly one person must be visible":"ให้มีผู้ฝึกอยู่ในภาพเพียงหนึ่งคน",
 "Side view / level camera / one person":"จัดกล้องด้านข้างให้ได้ระดับ และมีผู้ฝึกหนึ่งคน",
 "Press SPACE to confirm setup and start":"เมื่อพร้อม คลิกหน้าต่างนี้แล้วกดปุ่มเว้นวรรค",
 "Spinal curvature":"ความโค้งของกระดูกสันหลัง",
 "Load weight / object distance":"น้ำหนักและระยะห่างของสิ่งของ",
 "Twisting / grip":"การบิดตัวและลักษณะการจับ",
 "Workstation fit":"ความเหมาะสมของพื้นที่ทำงาน",
 "Balance / weight distribution":"การทรงตัวและการกระจายน้ำหนัก",
}


def find_font(explicit=None):
    """Use the project's optional font, or Thai-capable system fonts."""
    base=Path(__file__).resolve().parents[1]
    windows=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"
    candidates=[explicit or os.environ.get("LIFTSAVE_THAI_FONT"),
                base/"fonts"/"NotoSansThai-Regular.ttf",windows/"tahoma.ttf",
                windows/"LeelawUI.ttf",windows/"leelawad.ttf",
                Path('/System/Library/Fonts/Thonburi.ttc'),
                Path('/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf'),
                Path('/usr/share/fonts/truetype/tlwg/Garuda.ttf')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file(): return str(candidate)
    raise RuntimeError('ไม่พบฟอนต์ไทย: ตั้งค่า LIFTSAVE_THAI_FONT ให้ชี้ไปยังไฟล์ฟอนต์ไทย .ttf')


def wrap_text(text, font, width):
    # Keep Thai vowel/tone marks with the preceding character when wrapping.
    clusters=[]
    for char in text:
        if clusters and (unicodedata.category(char).startswith('M') or char=='\u0e33'):
            clusters[-1]+=char
        else: clusters.append(char)
    lines=[];current=''
    for cluster in clusters:
        candidate=current+cluster
        if current and font.getlength(candidate)>width:
            # Prefer a space, then fall back to glyph clusters for long Thai phrases.
            split=current.rfind(' ')
            if split>len(current)//2:
                lines.append(current[:split]);current=current[split+1:]+cluster
            else:
                lines.append(current.rstrip());current=cluster.lstrip()
        else: current=candidate
    lines.append(current.rstrip())
    return lines


class Overlay:
    def __init__(self, font_path=None):
        path=find_font(font_path)
        self.font=ImageFont.truetype(path,22)
        self.title_font=ImageFont.truetype(path,30)
        self.cached_key=None;self.cached_panel=None

    def panel(self,features,assessment,phase,total,ml):
        danger=getattr(assessment,'alert_level','NONE')=='DANGER'
        color=tuple(reversed(COLORS.get('DANGER' if danger else assessment.status,COLORS['UNKNOWN'])))
        rows=[('LiftSaveWithAi',self.title_font,(245,245,245)),
              ('ระบบฝึกท่าทาง • รุ่นทดลอง',self.font,(190,190,190)),
              ('เว้นวรรค: เริ่ม / พัก   R: ตั้งต้นใหม่   Esc: จบ',self.font,(230,230,230)),
              ('',self.font,color),
              ('สถานะ: '+('เตือนระดับสูง — หยุดและทบทวนท่า' if danger else STATUS.get(assessment.status,'กำลังประมวลผล')),self.font,color),
              ('ช่วงฝึก: '+PHASE.get(phase,'กำลังสังเกต'),self.font,color),
              (f'รอบฝึกที่บันทึก: {total} (รวมรอบไม่ครบ)',self.font,color),
              ('',self.font,color),('คำแนะนำ',self.title_font,(245,245,245))]
        for reason in assessment.reasons:
            rows.append((TEXT.get(reason,'มีข้อความเพิ่มเติม กรุณาให้ผู้สอนตรวจสอบ'),self.font,color))
        if features:
            rows.append(('',self.font,color))
            rows.append(('ค่าที่วัดได้ในภาพ',self.font,(220,220,220)))
            rows.append(('ด้านที่ใช้วัด: '+{'left':'ซ้าย','right':'ขวา'}.get(features.get('side'),'ยังไม่ระบุ'),self.font,(190,190,190)))
            for key,label in [('trunk_inclination','มุมเอียงลำตัว'),('knee_angle','มุมเข่า'),('hip_angle','มุมสะโพก')]:
                value=features.get(key)
                label+=': '+('วัดไม่ได้' if value is None else f'{value:.0f} องศา')
                rows.append((label,self.font,(190,190,190)))
        if ml:
            rows.append(('ผลโมเดลทดลอง: '+STATUS.get(ml,'มีผลสำหรับผู้สอนตรวจสอบ'),self.font,(190,190,190)))
        rows += [('',self.font,color),('สิ่งที่ระบบยังประเมินไม่ได้',self.font,(190,190,190))]
        for item in assessment.unassessed:
            rows.append(('• '+TEXT.get(item,'ข้อมูลเพิ่มเติม'),self.font,(170,170,170)))
        wrapped=[]
        for text,font,fill in rows:
            for line in wrap_text(text,font,536): wrapped.append((line,font,fill))
        height=max(640,32+sum(44 if font==self.title_font else 34 for _,font,_ in wrapped))
        panel=Image.new('RGB',(580,height),(25,29,34));draw=ImageDraw.Draw(panel);y=16
        for line,font,fill in wrapped:
            draw.text((22,y),line,font=font,fill=fill)
            y+=44 if font==self.title_font else 34
        return np.asarray(panel)[:,:,::-1].copy()

    def draw(self,frame,joints,features,assessment,phase,total,confidence,fps,ml=None):
        if joints:
            import cv2
            from pose.utils import PoseUtils
            color=COLORS.get('DANGER' if getattr(assessment,'alert_level','NONE')=='DANGER' else assessment.status,COLORS['UNKNOWN'])
            for a,b in PAIRS:
                if PoseUtils.is_valid_joints(joints,(a,b),confidence):
                    cv2.line(frame,(int(joints[a]['x']),int(joints[a]['y'])),
                             (int(joints[b]['x']),int(joints[b]['y'])),color,2,cv2.LINE_AA)
        # Cache Thai shaping when the displayed text has not changed.
        values=tuple((k,round(v) if isinstance(v,(int,float)) else v) for k,v in sorted((features or {}).items())
                        if k in ('side','trunk_inclination','knee_angle','hip_angle'))
        key=(values,getattr(assessment,"alert_level","NONE"),assessment.status,tuple(assessment.reasons),tuple(assessment.unassessed),phase,total,ml)
        if key!=self.cached_key:
            self.cached_panel=self.panel(features,assessment,phase,total,ml);self.cached_key=key
        panel=self.cached_panel
        h=max(frame.shape[0],panel.shape[0]);w=frame.shape[1]+panel.shape[1]
        canvas=np.full((h,w,3),24,dtype=np.uint8)
        canvas[:frame.shape[0],:frame.shape[1]]=frame
        canvas[:panel.shape[0],frame.shape[1]:]=panel
        return canvas
