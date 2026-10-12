"""Independent concurrent posture assessments for each tracked person."""
from assessment.features import FeatureExtractor
from assessment.front_bend import assess_front_bend
from assessment.smoothing import Smoother
from assessment.rules import RuleEngine
from assessment.standing import StandingAssessment
from assessment.lift_cycle import LiftCycle
from monitoring.rules import SafetyEngine

class PersonPosture:
    def __init__(self, criteria, side):
        self.features=FeatureExtractor(criteria['quality']['keypoint_confidence'],side)
        self.smoother=Smoother(criteria['quality']['smoothing_seconds'])
        self.standing=StandingAssessment(criteria)
        self.cycle=LiftCycle(criteria)
        self.last=None
        self.completed=0
        self.last_rep=None
        self.danger_since=None
        self.front_since=None

class UnifiedEngine:
    def __init__(self, criteria, settings=None, side='auto'):
        self.criteria=criteria;self.side=side;self.safety=SafetyEngine(settings)
        self.postures={};self.rules=RuleEngine(criteria)
    @property
    def settings(self):return self.safety.settings
    @property
    def tracks(self):return self.safety.tracks
    def reset(self):self.safety.reset();self.postures.clear()
    def calibrate(self):self.safety.calibrate()
    def finish_frame(self,visible):
        self.safety.finish_frame(visible)
        for key in list(self.postures):
            if key not in visible:del self.postures[key]
    def update(self,person_id,obs,now,joints):
        person=self.safety.update(person_id,obs,now)
        state=self.postures.get(person_id)
        if state is None or (state.last is not None and now-state.last>self.criteria['quality']['max_gap_seconds']):
            state=PersonPosture(self.criteria,self.side);self.postures[person_id]=state
        state.last=now
        raw=state.features.extract(joints)
        if raw is None:
            state.smoother.reset();filtered=None
        else:filtered=state.smoother.update(raw,now)
        lifting=self.rules.assess(raw)
        front=assess_front_bend(joints,self.settings,self.criteria['quality']['keypoint_confidence'])
        # Foreshortened frontal geometry cannot validate a side-view practice cycle.
        cycle_features=None if front['candidate'] else filtered
        rep=state.cycle.update(cycle_features,lifting,now)
        if rep:
            state.last_rep=rep
            if rep['outcome']!='INCOMPLETE':state.completed+=1
        standing=state.standing.update(cycle_features,now)
        warnings=[];danger=[]
        if lifting.alert_level=='DANGER':
            if state.danger_since is None:state.danger_since=now
            if now-state.danger_since>=self.settings['posture_dwell']:danger.append('ก้มลำตัวมากขณะเข่าเหยียด — ควรตรวจท่ายก')
            else:warnings.append('ท่าก้มเข้าเกณฑ์ — กำลังรอให้ครบเวลาก่อนบันทึก')
        else:state.danger_since=None
        if front['level']=='DANGER':
            if state.front_since is None:state.front_since=now
            if now-state.front_since>=self.settings['posture_dwell']:danger.append(front['reason'])
            else:warnings.append('ไหล่ใกล้ขาเข้าเกณฑ์ — กำลังรอให้ครบเวลาก่อนบันทึก')
        else:state.front_since=None
        if front['level']=='UNKNOWN':person['missing'].append(front['reason'])
        if lifting.alert_level=='WARNING':warnings.append('ลำตัวเอียงเกินเกณฑ์ทดลอง')
        if standing.status=='REMINDER':warnings.append('ยืนนิ่งต่อเนื่อง — ควรเปลี่ยนท่า')
        if raw is None:person['missing'].append('ท่ายก/ยืน: ไม่เห็นไหล่ สะโพก เข่า ข้อเท้าด้านที่ติดตามครบ')
        person['danger_reasons']+=danger
        person['reasons']+=danger+warnings
        if person['danger_reasons']:person['level']='DANGER'
        elif person['reasons']:person['level']='WARNING'
        elif raw is not None and not (front['candidate'] and front['level']=='UNKNOWN'):
            person['level']='NONE'
        else:person['level']='UNKNOWN'
        # Missing face/zone observations must not erase a valid body assessment.
        # A visible face alone, or an unresolved frontal bend, is not body clearance.
        person['posture_level']=('DANGER' if danger else 'WARNING' if lifting.alert_level in ('WARNING','DANGER') or front['level']=='DANGER'
                                 else 'NONE' if raw is not None and not (front['candidate'] and front['level']=='UNKNOWN') else 'UNKNOWN')
        person['partial_assessment']=bool(person['missing'])
        person['posture_feedback']={'NONE':'ท่าทางอยู่ในเกณฑ์ที่ประเมินได้',
                                    'UNKNOWN':'ยังประเมินท่าทางไม่ได้ครบ — ตรวจจุดไหล่ สะโพก เข่า และข้อเท้า',
                                    'WARNING':'ท่าทางเข้าเกณฑ์เตือน / กำลังรอยืนยัน',
                                    'DANGER':'ท่าทางเข้าเกณฑ์อันตราย'}[person['posture_level']]
        person.update(front_bend=front,front_bend_seconds=round(now-state.front_since,1) if state.front_since is not None else 0,posture_seconds=round(now-state.danger_since,1) if state.danger_since is not None else 0,angles=None if raw is None else {k:round(v,1) if isinstance(v,(int,float)) else v for k,v in raw.items()},
                      lift_phase=state.cycle.phase,lift_reps=state.completed,
                      lift_attempts=state.cycle.total,last_rep=state.last_rep,
                      standing_seconds=round(max(0,now-state.standing.since),1) if state.standing.since is not None else 0,
                      assessments={'lifting':lifting.alert_level if raw else 'UNKNOWN',
                                   'standing':standing.status,'front_bend':front['level'],
                                   'head': 'CALIBRATED' if person['calibrated'] else 'ABSOLUTE' if person.get('head_angle') is not None else 'UNKNOWN'})
        return person
