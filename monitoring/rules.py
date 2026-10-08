"""Experimental 2D proxies, not physical neck angles or ground-plane distances."""
import math
import statistics
import uuid
from dataclasses import dataclass, field

DEFAULTS = dict(neck_warning=5.0, neck_danger=10.0, head_delta=12.0, head_absolute=25.0, head_confidence=0.35, leg_rise=0.08,
                front_bend_enabled=1, front_torso_max=0.6, front_shoulder_knee_max=1.6, front_knee_min=150.0,
                zone_margin=0.04, leg_dwell=2.0, forbidden_dwell=2.0, posture_dwell=2.0, zone_dwell=0.5,
                confidence=0.5, max_gap=1.5, max_people=20, snapshot_cooldown=10.0)

def validate_settings(values):
    result = dict(DEFAULTS)
    if not isinstance(values, dict) or set(values) - set(DEFAULTS):
        raise ValueError('ตัวเลือกไม่ถูกต้อง')
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('ค่าตั้งต้องเป็นตัวเลขจำกัด')
        result[key] = value
    if not (0.5 <= result['neck_warning'] < result['neck_danger'] <= 120):
        raise ValueError('เวลาเตือนต้องน้อยกว่าเวลาสีแดง และอยู่ระหว่าง 0.5–120 วินาที')
    for key, low, high in [('front_bend_enabled',0,1),('front_torso_max',0.1,1.5),('front_shoulder_knee_max',0.8,2.5),('front_knee_min',90,180),('head_delta',3,60),('head_absolute',5,70),('head_confidence',0.2,0.95),('leg_rise',0.02,0.5),('zone_margin',0,0.3),('leg_dwell',0,120),('forbidden_dwell',0,120),('posture_dwell',0,120),
                          ('zone_dwell',0.2,10),('confidence',0.2,0.95),('max_gap',0.1,2),
                          ('max_people',1,100),('snapshot_cooldown',2,120)]:
        if not low <= result[key] <= high: raise ValueError('ค่าตั้งอยู่นอกช่วง: '+key)
    if result['front_bend_enabled'] not in (0,1):raise ValueError('เกณฑ์ไหล่ใกล้ขาต้องเป็น 0 หรือ 1')
    if int(result['max_people']) != result['max_people']: raise ValueError('จำนวนคนต้องเป็นจำนวนเต็ม')
    result['max_people'] = int(result['max_people'])
    return result

def validate_zone(points):
    """Any simple polygon: concave, convex, either winding, redundant edge points."""
    if not isinstance(points,list) or not 3<=len(points)<=201:
        raise ValueError('วาดอย่างน้อย 3 จุด และไม่เกิน 200 จุด')
    out=[];eps=1e-10
    for p in points:
        if not isinstance(p,list) or len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in p):
            raise ValueError('พิกัดเขตต้องอยู่ในภาพ')
        value=tuple(p)
        if not out or math.dist(out[-1],value)>eps:out.append(value)
    if len(out)>1 and math.dist(out[0],out[-1])<=eps:out.pop()
    if not 3<=len(out)<=200:raise ValueError('ต้องมีจุดที่ต่างกันอย่างน้อย 3 จุด และไม่เกิน 200 จุด')
    def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on_segment(a,b,c):return abs(orient(a,b,c))<=eps and min(a[0],b[0])-eps<=c[0]<=max(a[0],b[0])+eps and min(a[1],b[1])-eps<=c[1]<=max(a[1],b[1])+eps
    def intersects(a,b,c,d):
        u,v,w,z=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
        if ((u>eps and v< -eps) or (v>eps and u< -eps)) and ((w>eps and z< -eps) or (z>eps and w< -eps)):return True
        return on_segment(a,b,c) or on_segment(a,b,d) or on_segment(c,d,a) or on_segment(c,d,b)
    for i in range(len(out)):
        a,b,c=out[i-1],out[i],out[(i+1)%len(out)]
        if abs(orient(a,b,c))<=eps and (a[0]-b[0])*(c[0]-b[0])+(a[1]-b[1])*(c[1]-b[1])>eps:
            raise ValueError('เส้นย้อนทับกันบริเวณจุด '+str(i+1)+' กรุณาย้อนจุดแล้ววาดต่อไปตามขอบ')
        for j in range(i+1,len(out)):
            if j==i+1 or (i==0 and j==len(out)-1):continue
            if intersects(out[i],out[(i+1)%len(out)],out[j],out[(j+1)%len(out)]):
                raise ValueError('เส้นขอบช่วง '+str(i+1)+' และ '+str(j+1)+' ไขว้หรือแตะกัน กรุณากดย้อนจุดแล้วเรียงตามขอบพื้นที่')
    area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(out,out[1:]+out[:1])))/2
    if area<=eps:raise ValueError('เขตต้องมีพื้นที่ ไม่ใช่เส้นตรง')
    return out

def distance_to_zone(p, polygon):
    """Zero inside/on boundary; otherwise minimum Euclidean edge distance."""
    inside=False; nearest=float('inf')
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/max(dx*dx+dy*dy,1e-12)))
        nearest=min(nearest,math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy))
        if (a[1]>p[1]) != (b[1]>p[1]) and p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:
            inside=not inside
    return 0.0 if inside else nearest

def angle(a,b,c):
    u=(a[0]-b[0],a[1]-b[1]);v=(c[0]-b[0],c[1]-b[1])
    den=math.hypot(*u)*math.hypot(*v)
    if den<1e-6:return None
    return math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/den))))

def observations(joints, shape, zone, confidence, box=None, leg_rise=0.08, head_confidence=0.35):
    def point(i):
        if i>=len(joints):return None
        p=joints[i]
        if p['confidence']<(head_confidence if i<5 else confidence) or not all(math.isfinite(p[k]) for k in ('x','y','confidence')):return None
        return p['x'],p['y']
    values={'head':None,'head_side':None,'near':None,'inside':None,'leg':None,
            'head_candidates':{},'zone_source':None,'raised_sides':[],'leg_height':None}
    nose=point(0);ears=[point(3),point(4)];eyes=[point(1),point(2)]
    candidates=values['head_candidates']
    # Different projections keep independent neutral references. Do not require hips
    # or an upright torso merely to measure visible facial landmarks.
    if nose is not None:
        if all(e is not None for e in ears):
            mid=((ears[0][0]+ears[1][0])/2,(ears[0][1]+ears[1][1])/2)
            span=math.dist(*ears)
            if span>=12 and abs(nose[0]-mid[0])<span*.3:
                candidates['front_ears']=math.degrees(math.atan2(mid[1]-nose[1],span/2))
        if 'front_ears' not in candidates:
            for index,e in enumerate(ears):
                if e is not None and abs(nose[0]-e[0])>=6:
                    candidates['ear_'+str(index)]=math.degrees(math.atan2(e[1]-nose[1],abs(nose[0]-e[0])))
        if all(e is not None for e in eyes):
            span=math.dist(*eyes);mid=((eyes[0][0]+eyes[1][0])/2,(eyes[0][1]+eyes[1][1])/2)
            if span>=10 and abs(nose[0]-mid[0])<span*.4:
                candidates['front_eyes']=math.degrees(math.atan2(mid[1]-nose[1],span))
    if candidates:
        # Prefer ears; eyes are fallback when ears disappear. Nose below the eyes
        # gives a negative neutral value, rising nose makes it more positive.
        method=next(iter(candidates));values['head']=candidates[method];values['head_side']=method
    ankles=[point(15),point(16)]
    h,w=shape[:2]
    if zone:
        polygon=[(x*w,y*h) for x,y in zone]
        feet=[a for a in ankles if a is not None]
        if feet:
            values['inside']=any(distance_to_zone(a,polygon)<=1e-6 for a in feet)
            values['zone_source']='ankle'
        elif box is not None and len(box)==4 and all(math.isfinite(v) for v in box):
            # Ground-contact estimate only; do not call upper-body overlap entry.
            foot=((box[0]+box[2])/2,box[3])
            values['inside']=distance_to_zone(foot,polygon)<=1e-6
            feet=[foot];values['zone_source']='box_base'
        # A raised foot may be outside while the person holds the boundary.
        contact=feet+[p for p in (point(9),point(10),point(11),point(12),point(13),point(14)) if p is not None]
        if contact:
            values['distance']=min(distance_to_zone(p,polygon) for p in contact)/min(w,h)
            values['near']=values['distance']<=1e-6
    torso_lengths=[math.dist(point(a),point(b)) for a,b in [(5,11),(6,12)] if point(a) is not None and point(b) is not None]
    torso=sum(torso_lengths)/len(torso_lengths) if torso_lengths else 0
    if torso<20 and box is not None and len(box)==4:torso=max(0,(box[3]-box[1])*.3)
    values['torso_scale']=torso
    values['ankle_y']={side:p[1] for side,p in zip(('left','right'),ankles) if p is not None}
    values['leg_extensions']={}
    if torso>=20:
        for side,hip,ankle in [('left',11,15),('right',12,16)]:
            hp,ap=point(hip),point(ankle)
            if hp is not None and ap is not None:values['leg_extensions'][side]=(ap[1]-hp[1])/torso
        if all(a is not None for a in ankles):
            difference=(ankles[1][1]-ankles[0][1])/torso
            values['leg_height']=abs(difference)
            # No mandatory knee bend or straight supporting leg: small lifts and
            # extended-leg lifts are both observable from ankle separation.
            values['leg']=abs(difference)>=leg_rise
            if values['leg']:values['raised_sides']=['left' if difference>0 else 'right']
    return values

@dataclass
class TrackState:
    seen: float
    starts: dict = field(default_factory=dict)
    baseline: float | None = None
    side: int | None = None
    samples: list = field(default_factory=list)
    calibration_start: float | None = None
    calibrating: bool = False
    baselines: dict = field(default_factory=dict)
    channel_samples: dict = field(default_factory=dict)
    channel_since: dict = field(default_factory=dict)
    extensions: dict = field(default_factory=dict)
    ankle_reference: dict = field(default_factory=dict)
    extension_seen: dict = field(default_factory=dict)
    leg_signature: tuple | None = None
    zone_trigger: bool = False
    zone_episode: str | None = None

class SafetyEngine:
    def __init__(self, settings=None):
        self.settings=validate_settings(settings or {});self.tracks={};self.zone_type='hazard';self.now=0
    def reset(self):self.tracks.clear()
    def calibrate(self):
        for s in self.tracks.values():
            s.baseline=None;s.baselines.clear();s.channel_samples.clear();s.channel_since.clear();s.samples=[];s.calibration_start=None;s.calibrating=True;s.starts.pop('neck',None)
    def update(self, person_id, obs, now):
        s=self.tracks.setdefault(person_id,TrackState(now))
        if now-s.seen>self.settings['max_gap']:
            # ID may be reused after occlusion: discard calibration as well as timers.
            s=TrackState(now);self.tracks[person_id]=s
        s.seen=now
        self.now=now
        head=obs.get('head');side=obs.get('head_side')
        channels=obs.get('head_candidates')
        modern=channels is not None
        if channels is None:channels={} if head is None else {str(side):head}
        if s.calibrating:
            for key in list(s.channel_samples):
                if key not in channels:s.channel_samples.pop(key,None);s.channel_since.pop(key,None)
            for key,value in channels.items():
                s.channel_since.setdefault(key,now);s.channel_samples.setdefault(key,[]).append(value)
                if now-s.channel_since[key]>=2 and len(s.channel_samples[key])>=5:
                    samples=s.channel_samples[key]
                    if max(samples)-min(samples)<=12:s.baselines[key]=statistics.median(samples)
                    s.channel_samples[key]=[];s.channel_since[key]=now
            if s.baselines:s.calibrating=False
        method=next(iter(channels),None)
        if method is not None:
            # Prefer a calibrated projection if it is currently visible.
            method=next((k for k in channels if k in s.baselines),method)
            head=channels[method]
        baseline=s.baselines.get(method)
        s.baseline=baseline;s.side=side
        delta=None if head is None or baseline is None else head-baseline
        # Modern observations can work without manual calibration, with a stricter
        # absolute nose-elevation threshold. No absolute fallback for legacy callers.
        neck=None if head is None else (delta>=self.settings['head_delta'] if delta is not None else
                                      (head>=(self.settings['head_absolute']*.2 if method=='front_eyes' else self.settings['head_absolute']) if modern and not s.calibrating else None))
        near=None if obs.get('distance') is None else obs['distance']<=self.settings['zone_margin']
        leg=obs.get('leg');raised=list(obs.get('raised_sides',[]))
        # A stable neutral extension lets a single visible leg trigger after its
        # ankle moves toward its own hip, even if the other leg becomes occluded.
        for key,extension in obs.get('leg_extensions',{}).items():
            previous=s.extensions.get(key)
            if (obs.get('leg') is None and previous is not None and
                now-s.extension_seen.get(key,-float('inf'))<=self.settings['max_gap'] and
                previous-extension>=self.settings['leg_rise'] and
                key in s.ankle_reference and key in obs.get('ankle_y',{}) and
                s.ankle_reference[key]-obs['ankle_y'][key]>=self.settings['leg_rise']*obs.get('torso_scale',float('inf'))):
                leg=True
                if key not in raised:raised.append(key)
            # Acquire reference only with both feet observed level, and keep it
            # fixed while lifted. No reference is invented for a lone hidden leg.
            if obs.get('leg') is False:
                s.extensions[key]=extension;s.extension_seen[key]=now
                if key in obs.get('ankle_y',{}):s.ankle_reference[key]=obs['ankle_y'][key]
        lifted=None if near is None or leg is None else near and leg
        signature=tuple(sorted(raised)) if lifted else None
        if signature!=s.leg_signature:
            s.starts.pop('leg',None)
            if self.zone_type=='hazard':s.zone_trigger=False;s.zone_episode=None
        s.leg_signature=signature
        elapsed={}
        for key,condition in [('neck',neck),('zone',near),('leg',lifted),('inside',obs.get('inside'))]:
            if condition is True:
                s.starts.setdefault(key,now);elapsed[key]=max(0,now-s.starts[key])
            else:
                s.starts.pop(key,None);elapsed[key]=0.0
        warnings=[];danger=[]
        if elapsed['neck']>=self.settings['neck_danger']:danger.append('แหงนหน้าค้างเกินเวลา')
        elif elapsed['neck']>=self.settings['neck_warning']:warnings.append('แหงนหน้าค้าง: ควรเปลี่ยนท่า')
        if near and elapsed['zone']>=self.settings['zone_dwell']:warnings.append('อยู่ในหรือใกล้เขตอันตราย')
        zone_trigger=False
        if self.zone_type=='forbidden':
            zone_trigger=obs.get('inside') is True and elapsed['inside']>=self.settings['forbidden_dwell']
            if zone_trigger:danger.append('เข้าเขตห้ามเข้า')
        else:
            zone_trigger=bool(lifted and elapsed['leg']>=self.settings['leg_dwell'])
            if zone_trigger:danger.append('ยกขาในหรือใกล้ขอบเขตอันตราย')
        if zone_trigger and not s.zone_trigger:s.zone_episode=uuid.uuid4().hex
        if zone_trigger:s.zone_trigger=True
        elif (obs.get('inside') is False if self.zone_type=='forbidden' else near is False or leg is False):
            s.zone_trigger=False;s.zone_episode=None
        missing=[]
        if head is None:missing.append('ไม่เห็นจมูกและหู/ตาชัดพอ')
        elif s.calibrating:missing.append('กำลังตั้งศีรษะปกติ')
        elif baseline is None and not modern:missing.append('ยังไม่ตั้งศีรษะปกติ')
        if near is None:missing.append('ยังไม่วาดเขต/ไม่มีจุดอ้างอิงตำแหน่ง')
        if leg is None:missing.append('ไม่เห็นข้อต่อขาครบ')
        level='DANGER' if danger else 'WARNING' if warnings else 'UNKNOWN' if missing else 'NONE'
        return dict(id=person_id,level=level,reasons=danger+warnings,missing=missing,
                    neck_seconds=round(elapsed['neck'],1),leg_seconds=round(elapsed['leg'],1),
                    inside_seconds=round(elapsed['inside'],1),
                    zone_record_after=self.settings['forbidden_dwell'] if self.zone_type=='forbidden' else self.settings['leg_dwell'],
                    head_delta=None if delta is None else round(delta,1),
                    head_angle=None if head is None else round(head,1),head_method=method,
                    head_mode='relative' if baseline is not None else 'absolute',
                    leg_height=obs.get('leg_height'),raised_sides=raised,zone_type=self.zone_type,
                    zone_inside=obs.get('inside'),zone_near=near,zone_source=obs.get('zone_source'),
                    zone_episode=s.zone_episode if zone_trigger else None,
                    calibrated=s.baseline is not None, danger_reasons=danger)
    def finish_frame(self, visible):
        for key in list(self.tracks):
            if key not in visible:
                state=self.tracks[key];state.starts.clear()
                state.channel_samples.clear();state.channel_since.clear()
                if self.now-state.seen>self.settings['max_gap']:del self.tracks[key]
