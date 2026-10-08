class PoseExtractor:
    def get_keypoints(self, result):
        kp = result.keypoints
        if kp is None or kp.conf is None:
            return []
        xy, confidence = kp.xy.cpu().numpy(), kp.conf.cpu().numpy()
        return [[{"x":float(x), "y":float(y), "confidence":float(c)}
                 for (x,y),c in zip(points, scores)] for points,scores in zip(xy, confidence)]
