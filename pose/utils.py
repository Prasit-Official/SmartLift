import math

class PoseUtils:
    @staticmethod
    def valid_point(joints, index, min_conf=0.5):
        if joints is None or len(joints) <= index:
            return False
        j = joints[index]
        try:
            return all(math.isfinite(float(j[k])) for k in ("x", "y", "confidence")) and j["confidence"] >= min_conf
        except (KeyError, TypeError, ValueError):
            return False

    @classmethod
    def is_valid_joints(cls, joints, indices=(5, 11, 13, 15), min_conf=0.5):
        return all(cls.valid_point(joints, i, min_conf) for i in indices)
