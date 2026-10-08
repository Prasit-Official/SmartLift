"""Frame stepping: pause files without consuming frames; keep camera preview live."""
class FrameStepper:
    def __init__(self,camera,is_video):
        self.camera=camera;self.is_video=is_video
        self.frame=None;self.frame_index=-1;self.was_active=False
    def next(self,active):
        should_read=self.frame is None or not self.is_video or (active and self.was_active)
        if should_read:
            self.frame=self.camera.read()
            if self.frame is None:return None
            self.frame_index+=1
        self.was_active=active
        return self.frame.copy()
