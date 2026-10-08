"""Nonblocking Windows alerts; only the latest fresh assessment can play."""
import math
import struct
import tempfile
import threading
import time
import wave
from pathlib import Path

# duration (seconds), pitch (Hz), start-to-start repeat interval (seconds)
TONES={'WARNING':(.12,880,1.5),'DANGER':(.85,1100,2.5)}

class AlertSchedule:
    def __init__(self,dwell=.3,stale_after=1.0):
        self.dwell=dwell;self.stale_after=stale_after
        self.level='NONE';self.since=0.;self.next_play=0.
    def tick(self,requested,heartbeat,now):
        level=requested if requested in TONES and now-heartbeat<=self.stale_after else 'NONE'
        actions=[]
        if level!=self.level:
            actions.append('STOP');self.level=level;self.since=now
            self.next_play=now+self.dwell
        if level!='NONE' and now>=self.next_play:
            actions.append(level);self.next_play=now+TONES[level][2]
        return actions

def write_tone(path,duration,frequency):
    rate=22050;size=int(rate*duration);fade=int(rate*.01)
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
        samples=[]
        for i in range(size):
            envelope=min(1.,i/fade,(size-1-i)/fade)
            value=int(32767*.18*envelope*math.sin(2*math.pi*frequency*i/rate))
            samples.append(struct.pack('<h',value))
        stream.writeframes(b''.join(samples))

class WindowsPlayer:
    def __init__(self):
        import winsound
        self.ws=winsound;self.temp=tempfile.TemporaryDirectory(prefix='liftsave-audio-')
        self.paths={}
        try:
            for level,(duration,hz,_) in TONES.items():
                path=Path(self.temp.name)/(level+'.wav');write_tone(path,duration,hz);self.paths[level]=path
        except Exception:
            self.temp.cleanup();raise
    def play(self,level):
        self.ws.PlaySound(str(self.paths[level]),self.ws.SND_FILENAME|self.ws.SND_ASYNC|self.ws.SND_NODEFAULT)
    def stop(self): self.ws.PlaySound(None,0)
    def close(self):
        try: self.stop()
        finally: self.temp.cleanup()

class AudioAlert:
    def __init__(self,enabled=True,player=None):
        self.enabled=enabled;self.error=None;self.player=None
        self.lock=threading.Lock();self.wake=threading.Event();self.closed=False
        self.level='NONE';self.heartbeat=0.;self.thread=None
        if not enabled:return
        try: self.player=player or WindowsPlayer()
        except (ImportError,OSError,RuntimeError) as exc:
            self.error=str(exc);self.enabled=False
            print('เสียงแจ้งเตือนไม่พร้อมใช้งาน แต่ภาพยังทำงานได้:',exc)
            return
        self.thread=threading.Thread(target=self._run,name='liftsave-audio',daemon=True)
        self.thread.start()
    def update(self,level,active=True):
        with self.lock:
            self.level=level if active and level in TONES else 'NONE'
            self.heartbeat=time.monotonic()
        self.wake.set()
    def silence(self): self.update('NONE')
    def _run(self):
        schedule=AlertSchedule()
        try:
            while True:
                # Serialize output with state changes so no stale queued beep is played.
                with self.lock:
                    if self.closed:break
                    for action in schedule.tick(self.level,self.heartbeat,time.monotonic()):
                        if action=='STOP': self.player.stop()
                        else:self.player.play(action)
                self.wake.wait(.025);self.wake.clear()
        except (OSError,RuntimeError) as exc:
            self.error=str(exc);self.enabled=False
            print('หยุดเสียงเนื่องจากอุปกรณ์เสียงขัดข้อง:',exc)
        finally:
            self.player.close()
    def close(self):
        with self.lock:self.closed=True
        self.wake.set()
        if self.thread:self.thread.join()


def test_sound():
    alert=AudioAlert()
    if not alert.enabled:return
    print('ทดสอบเสียง: ปิ๊บสั้น ตามด้วยปิ๊บยาว (ปรับระดับเสียงที่ Windows)')
    try:
        for level,duration in [('WARNING',2.2),('NONE',.4),('DANGER',1.4)]:
            until=time.monotonic()+duration
            while time.monotonic()<until:
                alert.update(level);time.sleep(.05)
    finally:alert.close()
