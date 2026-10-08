"""Loopback-only dashboard with bounded commands and same-origin CSRF checks."""
import json
import queue
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from monitoring.archive import EventArchive

class Dashboard:
    def __init__(self, folder, review_only=False):
        self.folder=Path(folder);self.token=secrets.token_urlsafe(32)
        self.lock=threading.Lock();self.commands=queue.Queue(maxsize=30)
        self.review_only=review_only
        self.state={'review_only':review_only,'status':'กำลังโหลดโมเดล','people':[],'events':[],'active':False}
        self.jpeg=None
        self.archive=EventArchive(self.folder.parent)
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,code,data,mime='application/json; charset=utf-8'):
                self.send_response(code);self.send_header('Content-Type',mime)
                self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'")
                self.send_header('Content-Length',str(len(data)));self.end_headers()
                try:self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError):pass
            def valid_host(self):return self.headers.get('Host')==f'127.0.0.1:{outer.http.server_port}'
            def do_GET(self):
                if not self.valid_host():return self.send(403,b'{}')
                parsed=urlsplit(self.path);path=parsed.path
                query=parse_qs(parsed.query)
                if path=='/':
                    html=(Path(__file__).resolve().parent.parent/'website'/'lift-safe-training.html').read_text(encoding='utf-8').replace('__TOKEN__',outer.token)
                    return self.send(200,html.encode(),'text/html; charset=utf-8')
                if path=='/api/state':
                    with outer.lock:data=json.dumps(outer.state,ensure_ascii=False,allow_nan=False).encode()
                    return self.send(200,data)
                if path=='/api/sessions':
                    return self.send(200,json.dumps({'sessions':outer.archive.sessions(),'current':outer.folder.name}).encode())
                if path=='/api/history':
                    try:data=outer.archive.events(query.get('session',[outer.folder.name])[0])
                    except (ValueError,OSError) as exc:return self.send(400,json.dumps({'error':str(exc)}).encode())
                    return self.send(200,json.dumps({'events':data},ensure_ascii=False).encode())
                if path=='/api/event-image':
                    try:data=outer.archive.image(query.get('session',[''])[0],query.get('name',[''])[0])
                    except (ValueError,OSError):return self.send(404,b'{}')
                    return self.send(200,data,'image/jpeg')
                if path=='/frame.jpg':
                    with outer.lock:data=outer.jpeg
                    return self.send(200 if data else 503,data or b'','image/jpeg')
                if path.startswith('/events/'):
                    name=path[len('/events/'):]
                    with outer.lock:allowed={name for e in outer.state.get('events',[]) for name in (e.get('image'),e.get('crop'))}
                    if name not in allowed or Path(name).name!=name:return self.send(404,b'{}')
                    try:return self.send(200,(outer.folder/name).read_bytes(),'image/jpeg')
                    except OSError:return self.send(404,b'{}')
                return self.send(404,b'{}')
            def do_POST(self):
                if not self.valid_host() or self.headers.get('X-LiftSave-Token')!=outer.token or self.headers.get('Origin')!=outer.url:
                    return self.send(403,b'{}')
                if self.path!='/api/control':return self.send(404,b'{}')
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=32768:raise ValueError('request size')
                    data=json.loads(self.rfile.read(size))
                    if not isinstance(data,dict) or data.get('action') not in ('start','pause','stop','calibrate','zone','settings','review'):
                        raise ValueError('command')
                    if outer.review_only and data['action'] not in ('review','stop'):raise ValueError('review only')
                    if data['action']=='review':
                        outer.archive.review(data.get('session'),data.get('image'),data.get('status'),data.get('note',''))
                    else:outer.commands.put_nowait(data)
                except (ValueError,OSError,queue.Full):return self.send(400,b'{"ok":false}')
                self.send(202,b'{"ok":true}')
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.http.daemon_threads=True
        self.url=f'http://127.0.0.1:{self.http.server_port}'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
    def publish(self, **values):
        with self.lock:self.state.update(values)
    def frame(self,jpeg):
        with self.lock:
            self.jpeg=jpeg;self.state["frame_at"]=time.time()
    def close(self):
        self.http.shutdown();self.http.server_close();self.thread.join()


def run_review(output):
    import webbrowser
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    archive=EventArchive(root);sessions=archive.sessions()
    dashboard=Dashboard(root/(sessions[0] if sessions else 'monitor-0'),review_only=True)
    dashboard.publish(status='ตรวจเหตุการณ์ย้อนหลัง — ไม่เปิดกล้องหรือโมเดล',output=str(root))
    print('Review dashboard:',dashboard.url,flush=True)
    try:
        webbrowser.open(dashboard.url)
        while dashboard.commands.get().get('action')!='stop':pass
    finally:dashboard.close()
