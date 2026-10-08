import cv2

class Camera:
    def __init__(self, source=0, backend=0):
        self.cap=cv2.VideoCapture(source,backend) if isinstance(source,int) and backend else cv2.VideoCapture(source)
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError("Cannot open camera/video. Check permissions and source.")
        if isinstance(source,int):
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
    def read(self):
        ok,frame=self.cap.read()
        return frame if ok else None
    def release(self): self.cap.release()
