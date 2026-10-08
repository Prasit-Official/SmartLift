import math
from pose.utils import PoseUtils
from pose.angles import AngleCalculator

class FeatureExtractor:
    SIDES = {"left":(5,7,9,11,13,15), "right":(6,8,10,12,14,16)}
    def __init__(self, confidence=0.5, side="auto"):
        self.confidence = confidence
        self.requested_side = side
        self.side = None

    def reset(self):
        self.side = None

    def extract(self, joints):
        def valid(i): return PoseUtils.valid_point(joints,i,self.confidence)
        def core(side):
            s,e,w,h,k,a = self.SIDES[side]
            return (s,h,k,a)
        if self.side is None:
            candidates = [s for s in self.SIDES if self.requested_side in ("auto",s)
                          and all(valid(i) for i in core(s))]
            if not candidates:
                return None
            self.side = max(candidates,key=lambda s:min(joints[i]["confidence"] for i in core(s)))
        s,e,w,h,k,a = self.SIDES[self.side]
        if not all(valid(i) for i in core(self.side)):
            return None  # Do not silently switch body side mid-session.
        def p(i): return (joints[i]["x"],joints[i]["y"])
        calc = AngleCalculator
        features = {"side":self.side,
                    "trunk_inclination":calc.trunk_inclination(p(h),p(s)),
                    "knee_angle":calc.calculate_angle(p(h),p(k),p(a)),
                    "hip_angle":calc.calculate_angle(p(s),p(h),p(k)),
                    "elbow_angle":None,"hand_distance_ratio":None}
        if any(features[key] is None for key in ("trunk_inclination","knee_angle","hip_angle")):
            return None
        if valid(e) and valid(w):
            features["elbow_angle"] = calc.calculate_angle(p(s),p(e),p(w))
        trunk_length = math.dist(p(s),p(h))
        if valid(w) and trunk_length > 1e-8:
            # Image-plane hand-to-hip distance only. Not object distance or RNLE H.
            features["hand_distance_ratio"] = math.dist(p(w),p(h))/trunk_length
        return features
