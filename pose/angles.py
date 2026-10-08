import math

class AngleCalculator:
    @staticmethod
    def calculate_angle(a, b, c):
        u = (a[0]-b[0], a[1]-b[1])
        v = (c[0]-b[0], c[1]-b[1])
        lengths = math.hypot(*u)*math.hypot(*v)
        if not math.isfinite(lengths) or lengths < 1e-8:
            return None
        cosine = (u[0]*v[0]+u[1]*v[1])/lengths
        return math.degrees(math.acos(max(-1.0,min(1.0,cosine))))

    @staticmethod
    def trunk_inclination(hip, shoulder):
        # 2D projected trunk inclination, NOT spinal curvature.
        dx, dy = shoulder[0]-hip[0], shoulder[1]-hip[1]
        length = math.hypot(dx,dy)
        if not math.isfinite(length) or length < 1e-8:
            return None
        return math.degrees(math.acos(max(-1.0,min(1.0,-dy/length))))
