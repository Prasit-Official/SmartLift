"""Experimental image-plane compression cue; does not estimate 3D bend angle."""
import math
from pose.utils import PoseUtils
from pose.angles import AngleCalculator


def assess_front_bend(joints, settings, confidence=.5):
    result=dict(available=False,candidate=False,level='UNKNOWN',reason='',
                torso_ratio=None,shoulder_knee_ratio=None,knee_min=None,
                shoulder_width_ratio=None,hip_width_ratio=None)
    if not settings['front_bend_enabled']:
        result.update(level='DISABLED',reason='ปิดเกณฑ์ไหล่ใกล้ขา')
        return result
    core=(5,6,11,12,13,14)
    if not isinstance(joints,(list,tuple)) or not PoseUtils.is_valid_joints(joints,core,confidence):
        result['reason']='ไหล่ใกล้ขา: ต้องเห็นไหล่ สะโพก และเข่าทั้งสองข้าง'
        return result
    def p(i):return joints[i]['x'],joints[i]['y']
    def midpoint(a,b):return ((a[0]+b[0])/2,(a[1]+b[1])/2)
    shoulders=[p(5),p(6)];hips=[p(11),p(12)];knees=[p(13),p(14)]
    thigh_lengths=[math.dist(h,k) for h,k in zip(hips,knees)]
    scale=sum(thigh_lengths)/2
    hmid=midpoint(*hips);kmid=midpoint(*knees)
    axis=(hmid[0]-kmid[0],hmid[1]-kmid[1]);axis_length=math.hypot(*axis)
    if min(thigh_lengths)<20 or axis_length<20:
        result['reason']='ไหล่ใกล้ขา: ช่วงต้นขาในภาพสั้นเกินไปหรือซ้อนกัน'
        return result
    up=(axis[0]/axis_length,axis[1]/axis_length);across=(-up[1],up[0])
    def transverse(a,b):return abs((a[0]-b[0])*across[0]+(a[1]-b[1])*across[1])/scale
    width=transverse(*shoulders);hip_width=transverse(*hips)
    result.update(shoulder_width_ratio=round(width,3),hip_width_ratio=round(hip_width,3))
    # Reject a predominantly side-on or collapsed skeleton. This is an applicability
    # check, NOT a classifier of front vs back vs the exact viewing angle.
    if width<.35 or hip_width<.2:
        result.update(level='NOT_APPLICABLE',reason='ไหล่ใกล้ขา: จุดสองข้างซ้อนกัน ใช้เกณฑ์มุมเดิม')
        return result
    torso=max(((s[0]-h[0])*up[0]+(s[1]-h[1])*up[1])/length
              for s,h,length in zip(shoulders,hips,thigh_lengths))
    proximity=max(math.dist(s,k)/length for s,k,length in zip(shoulders,knees,thigh_lengths))
    result.update(available=True,torso_ratio=round(torso,3),shoulder_knee_ratio=round(proximity,3))
    candidate=torso<=settings['front_torso_max'] and proximity<=settings['front_shoulder_knee_max']
    result['candidate']=candidate
    if not candidate:
        result.update(level='NONE',reason='ไหล่ยังไม่เข้าเกณฑ์ใกล้ขาทั้งสองข้าง')
        return result
    if not PoseUtils.is_valid_joints(joints,(15,16),confidence):
        result.update(level='UNKNOWN',reason='ไหล่เข้าใกล้ขา แต่ไม่เห็นข้อเท้าครบเพื่อแยกการย่อเข่า')
        return result
    angles=[AngleCalculator.calculate_angle(p(h),p(k),p(a)) for h,k,a in [(11,13,15),(12,14,16)]]
    if any(a is None for a in angles):
        result.update(level='UNKNOWN',reason='ไหล่เข้าใกล้ขา แต่วัดมุมเข่าไม่ได้')
        return result
    result['knee_min']=round(min(angles),1)
    if min(angles)<settings['front_knee_min']:
        result.update(level='NONE',reason='พบไหล่ใกล้ขาร่วมกับเข่างอ ยังไม่เข้าเกณฑ์ก้มเข่าเหยียด')
    else:
        result.update(level='DANGER',reason='สงสัยก้มเข้าหา/ออกจากกล้อง: ไหล่ใกล้ขาและลำตัวในภาพสั้นขณะเข่าเหยียด')
    return result
