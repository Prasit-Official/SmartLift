import math
import unittest
from monitoring.rules import validate_zone,distance_to_zone,observations

L=[[.1,.1],[.9,.1],[.9,.3],[.3,.3],[.3,.9],[.1,.9]]
class FreeformZoneTests(unittest.TestCase):
    def test_concave_L_preserves_empty_notch(self):
        p=validate_zone(L)
        self.assertEqual(distance_to_zone((.2,.7),p),0)
        self.assertEqual(distance_to_zone((.7,.2),p),0)
        self.assertGreater(distance_to_zone((.7,.7),p),0)
    def test_clockwise_and_counterclockwise(self):
        for points in [L,L[::-1]]:
            self.assertEqual(distance_to_zone((.2,.7),validate_zone(points)),0)
    def test_redundant_points_and_explicit_closing(self):
        self.assertEqual(validate_zone([L[0],L[0]]+L[1:]+[L[0]]),[tuple(p) for p in L])
    def test_collinear_forward_edges_allowed(self):
        p=validate_zone([[0,0],[.5,0],[1,0],[1,1],[0,1]])
        self.assertEqual(distance_to_zone((.5,.5),p),0)
    def test_curve_200_vertices(self):
        points=[[.5+.4*math.cos(i*2*math.pi/200),.5+.4*math.sin(i*2*math.pi/200)] for i in range(200)]
        self.assertEqual(len(validate_zone(points)),200)
    def test_reject_crossing_touching_and_backtracking(self):
        cases=[[[0,0],[1,1],[0,1],[1,0]],[[0,0],[1,0],[.5,0],[1,1],[0,1]],[[0,0],[1,0],[.5,.5],[1,1],[0,1],[.5,.5]]]
        for points in cases:
            with self.assertRaises(ValueError):validate_zone(points)
    def test_invalid_or_flat_shapes(self):
        for points in [[],[[0,0],[.5,.5],[1,1]],[[0,0],[2,0],[1,1]],[[0,0],[float('nan'),0],[1,1]]]:
            with self.assertRaises(ValueError):validate_zone(points)
    def test_notch_does_not_trigger_forbidden_entry(self):
        kp=[dict(x=0,y=0,confidence=0) for _ in range(17)]
        kp[15]=dict(x=700,y=700,confidence=.9)
        self.assertFalse(observations(kp,(1000,1000,3),validate_zone(L),.5)['inside'])
        kp[15]=dict(x=200,y=700,confidence=.9)
        self.assertTrue(observations(kp,(1000,1000,3),validate_zone(L),.5)['inside'])
