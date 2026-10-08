import math

class Smoother:
    def __init__(self, seconds=0.15):
        self.seconds=seconds
        self.reset()
    def reset(self):
        self.previous={}
        self.last_time=None
    def update(self, data, now):
        alpha = 1.0 if self.last_time is None else 1-math.exp(-max(0,now-self.last_time)/self.seconds)
        result={}
        for key,value in data.items():
            old=self.previous.get(key)
            if isinstance(value,(float,int)) and isinstance(old,(float,int)):
                result[key]=old+alpha*(value-old)
            else:
                result[key]=value  # Missing values remain missing; never invent them.
        self.previous=result.copy()
        self.last_time=now
        return result
