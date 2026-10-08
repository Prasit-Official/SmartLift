"""Thai desktop launcher; starts the existing runner in the same Python environment."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import queue
import threading
from realtime.camera_devices import display_labels, preferred_index
import config

MODE_NAMES={'ฝึกรวมทุกท่า / หลายคน / Dashboard':'monitoring'}
SIDE_NAMES={'เลือกด้านที่เห็นชัดอัตโนมัติ':'auto','ด้านซ้าย':'left','ด้านขวา':'right'}

def build_command(settings, root=None, executable=None, frozen=None):
    root=Path(root or config.ROOT)
    executable=executable or sys.executable
    frozen=getattr(sys,'frozen',False) if frozen is None else frozen
    if settings['mode'] not in ('lifting','standing','monitoring'):raise ValueError('กรุณาเลือกโหมดฝึก')
    if settings['source_type']=='camera':
        try: number=int(settings['camera'])
        except (TypeError,ValueError):raise ValueError('หมายเลขกล้องต้องเป็นจำนวนเต็ม เช่น 0 หรือ 1')
        if not 0<=number<=99:raise ValueError('หมายเลขกล้องต้องอยู่ระหว่าง 0 ถึง 99')
        source=str(number)
    elif settings['source_type']=='video':
        video=Path(settings['video']).expanduser()
        if not settings['video'].strip() or not video.is_file():raise ValueError('กรุณาเลือกไฟล์วิดีโอที่มีอยู่จริง')
        source=str(video.resolve())
    elif settings['source_type']=='image':
        image=Path(settings.get('image','')).expanduser()
        if not settings.get('image','').strip() or not image.is_file():raise ValueError('กรุณาเลือกไฟล์ภาพที่มีอยู่จริง')
        if settings['mode']!='monitoring':raise ValueError('ภาพนิ่งใช้กับโหมด Dashboard')
        source=str(image.resolve())
    else:raise ValueError('กรุณาเลือกกล้อง วิดีโอ หรือภาพนิ่ง')
    model=Path(settings['model']).expanduser()
    if not model.is_file():raise ValueError('ไม่พบไฟล์โมเดล กรุณาเลือก yolo11n-pose.pt ในส่วนตัวเลือกเพิ่มเติม')
    if settings['side'] not in ('auto','left','right'):raise ValueError('ด้านร่างกายไม่ถูกต้อง')
    subject=settings['subject'].strip() or 'anonymous'
    command=[executable] if frozen else [executable,str(root/'app.py')]
    command+=['--mode',settings['mode'],'--source',source,'--subject',subject,
              '--side',settings['side'],'--model',str(model.resolve())]
    if settings["source_type"]=="camera" and settings.get("camera_name"):
        command += ["--camera-backend",str(settings["camera_backend"]),"--camera-name",settings["camera_name"]]
        if settings.get("camera_path"):command += ["--camera-path",settings["camera_path"]]
    if settings['source_type']=='image':command.append('--image')
    if not settings['sound']:command.append('--mute')
    return command

class Launcher:
    def __init__(self, window):
        import tkinter as tk
        from tkinter import ttk
        self.tk=tk;self.ttk=ttk;self.window=window
        self.child=None;self.log=None;self.log_path=None;self.kind=None
        self.settings_path=config.DATA_ROOT/'launcher_settings.json'
        self.status=tk.StringVar(value='เลือกโหมดและแหล่งภาพ แล้วกดเปิดหน้าฝึก')
        saved={}
        try:saved=json.loads((self.settings_path if self.settings_path.exists() else config.LEGACY_DATA_ROOT/'launcher_settings.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        if not isinstance(saved,dict):saved={}
        self.mode=tk.StringVar(value=next((k for k,v in MODE_NAMES.items() if v==saved.get('mode')),next(iter(MODE_NAMES))))
        self.source_type=tk.StringVar(value=saved.get('source_type') if saved.get('source_type') in ('video','image') else 'camera')
        self.camera=tk.StringVar(value='')
        self.devices=[];self.scanning=False;self.discovery_queue=queue.Queue()
        self.saved_camera_path=saved.get('camera_path','');self.saved_camera_name=saved.get('camera_name','')
        self.camera_status=tk.StringVar(value='กำลังอ่านชื่ออุปกรณ์…')
        self.image=tk.StringVar(value=saved.get('image',''))
        self.video=tk.StringVar(value=saved.get('video',''))
        self.subject=tk.StringVar(value=saved.get('subject','P001'))
        self.sound=tk.BooleanVar(value=saved.get('sound',True))
        self.side=tk.StringVar(value=next((k for k,v in SIDE_NAMES.items() if v==saved.get('side')),next(iter(SIDE_NAMES))))
        self.model=tk.StringVar(value=saved.get('model',str(config.YOLO_MODEL)))
        window.title('LiftSaveWithAi — เลือกโหมดและแหล่งภาพ')
        height=min(760,max(580,window.winfo_screenheight()-100))
        window.geometry(f'820x{height}');window.minsize(700,560)
        window.option_add('*Font',('Tahoma',11))
        style=ttk.Style(window)
        if 'clam' in style.theme_names():style.theme_use('clam')
        style.configure('TLabel',font=('Tahoma',11))
        style.configure('TButton',font=('Tahoma',11),padding=(12,8))
        style.configure('Title.TLabel',font=('Tahoma',22,'bold'))
        style.configure('TCombobox',font=('Tahoma',11))
        outer=ttk.Frame(window);outer.pack(fill='both',expand=True)
        canvas=tk.Canvas(outer,highlightthickness=0)
        scroll=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        content=ttk.Frame(canvas,padding=24)
        item=canvas.create_window((0,0),window=content,anchor='nw')
        content.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item,width=event.width))
        def wheel(event):
            if event.widget.winfo_class()!='TCombobox':canvas.yview_scroll(int(-event.delta/120),'units')
        window.bind('<MouseWheel>',wheel)
        content.columnconfigure(1,weight=1)
        ttk.Label(content,text='LiftSaveWithAi',style='Title.TLabel').grid(row=0,column=0,columnspan=3,sticky='w')
        ttk.Label(content,text='ตั้งค่าการฝึกผ่านหน้าจอ • ใช้กล้อง วิดีโอ หรือภาพนิ่ง').grid(row=1,column=0,columnspan=3,sticky='w',pady=(0,18))
        ttk.Label(content,text='โหมดฝึก').grid(row=2,column=0,sticky='w',padx=(0,16))
        ttk.Combobox(content,textvariable=self.mode,values=list(MODE_NAMES),state='readonly').grid(row=2,column=1,columnspan=2,sticky='ew',pady=7)
        ttk.Label(content,text='รหัสผู้ฝึก').grid(row=3,column=0,sticky='w')
        ttk.Entry(content,textvariable=self.subject).grid(row=3,column=1,columnspan=2,sticky='ew',pady=7)
        sources=ttk.LabelFrame(content,text='รับภาพจาก',padding=14)
        sources.grid(row=4,column=0,columnspan=3,sticky='ew',pady=12);sources.columnconfigure(1,weight=1)
        ttk.Radiobutton(sources,text='กล้อง',variable=self.source_type,value='camera',command=self.source_changed).grid(row=0,column=0,sticky='w')
        self.camera_box=ttk.Combobox(sources,textvariable=self.camera,values=[],state='readonly',width=32)
        self.camera_box.grid(row=0,column=1,sticky='ew',padx=12)
        self.refresh_button=ttk.Button(sources,text='รีเฟรชกล้อง',command=self.refresh_cameras)
        self.refresh_button.grid(row=0,column=2)
        ttk.Label(sources,textvariable=self.camera_status,wraplength=470).grid(row=1,column=1,columnspan=2,sticky='w',padx=12,pady=(0,12))
        ttk.Radiobutton(sources,text='ไฟล์วิดีโอ',variable=self.source_type,value='video',command=self.source_changed).grid(row=2,column=0,sticky='w')
        self.video_entry=ttk.Entry(sources,textvariable=self.video)
        self.video_entry.grid(row=2,column=1,sticky='ew',padx=12)
        self.browse_button=ttk.Button(sources,text='เลือกไฟล์…',command=self.browse_video)
        self.browse_button.grid(row=2,column=2)
        ttk.Label(sources,text='เช่น MP4, AVI, MOV, MKV (ขึ้นกับตัวถอดรหัสในเครื่อง)').grid(row=3,column=1,columnspan=2,sticky='w',padx=12,pady=(5,0))
        ttk.Radiobutton(sources,text='ภาพนิ่ง (ทดสอบ)',variable=self.source_type,value='image',command=self.source_changed).grid(row=4,column=0,sticky='w',pady=12)
        self.image_entry=ttk.Entry(sources,textvariable=self.image)
        self.image_entry.grid(row=4,column=1,sticky='ew',padx=12)
        self.image_button=ttk.Button(sources,text='เลือกภาพ…',command=self.browse_image)
        self.image_button.grid(row=4,column=2)
        ttk.Label(sources,text='JPG / PNG / BMP / WEBP — วิเคราะห์ครั้งเดียว ไม่จับเวลาค้าง').grid(row=5,column=1,columnspan=2,sticky='w',padx=12)
        soundrow=ttk.Frame(content);soundrow.grid(row=5,column=0,columnspan=3,sticky='ew',pady=5)
        ttk.Checkbutton(soundrow,text='เปิดเสียงแจ้งเตือน',variable=self.sound).pack(side='left')
        self.test_button=ttk.Button(soundrow,text='ทดสอบเสียง',command=self.test_sound);self.test_button.pack(side='right')
        advanced=ttk.LabelFrame(content,text='ตัวเลือกเพิ่มเติม',padding=12)
        advanced.grid(row=6,column=0,columnspan=3,sticky='ew',pady=10);advanced.columnconfigure(1,weight=1)
        ttk.Label(advanced,text='ด้านร่างกาย').grid(row=0,column=0,sticky='w',padx=(0,12))
        ttk.Combobox(advanced,textvariable=self.side,values=list(SIDE_NAMES),state='readonly').grid(row=0,column=1,columnspan=2,sticky='ew',pady=5)
        ttk.Label(advanced,text='ไฟล์โมเดล').grid(row=1,column=0,sticky='w')
        ttk.Entry(advanced,textvariable=self.model).grid(row=1,column=1,sticky='ew',pady=5)
        ttk.Button(advanced,text='เลือก…',command=self.browse_model).grid(row=1,column=2,padx=(8,0))
        ttk.Label(content,text='ตรวจท่ายก การยืน แหงนหน้า และเขตอันตรายพร้อมกัน\nแยกค่าและรอบฝึกตาม ID ของแต่ละคนใน Dashboard\nวาดเขต เริ่มเฝ้าระวัง และตั้งศีรษะปกติผ่านหน้าเว็บ',wraplength=700).grid(row=7,column=0,columnspan=3,sticky='w',pady=10)
        self.start_button=ttk.Button(content,text='เปิดหน้าฝึก',command=self.start)
        self.start_button.grid(row=8,column=0,columnspan=2,sticky='ew',pady=10,padx=(0,12))
        ttk.Button(content,text='เปิดโฟลเดอร์ผล',command=self.open_reports).grid(row=8,column=2,sticky='ew')
        ttk.Label(content,textvariable=self.status,wraplength=700,foreground='#14614a').grid(row=9,column=0,columnspan=3,sticky='w',pady=8)
        self.review_button=ttk.Button(content,text='ตรวจเหตุการณ์ย้อนหลัง (ไม่เปิดกล้อง)',command=self.open_review)
        self.review_button.grid(row=10,column=0,columnspan=3,sticky='ew',pady=8)
        self.source_changed()
        window.protocol('WM_DELETE_WINDOW',self.close)
        window.after(100,self.refresh_cameras)

    def source_changed(self):
        camera=self.source_type.get()=='camera'
        self.camera_box.configure(state='readonly' if camera and not self.scanning else 'disabled')
        self.video_entry.configure(state='normal' if self.source_type.get()=='video' else 'disabled')
        self.browse_button.configure(state='normal' if self.source_type.get()=='video' else 'disabled')

        self.image_entry.configure(state='normal' if self.source_type.get()=='image' else 'disabled')
        self.image_button.configure(state='normal' if self.source_type.get()=='image' else 'disabled')

    def browse_image(self):
        from tkinter import filedialog
        path=filedialog.askopenfilename(parent=self.window,title='เลือกภาพทดสอบ',filetypes=[('ภาพ','*.jpg *.jpeg *.png *.bmp *.webp'),('ทุกไฟล์','*.*')])
        if path:self.image.set(path)

    def refresh_cameras(self):
        if self.scanning:return
        current=self.camera_box.current()
        if 0<=current<len(self.devices):
            self.saved_camera_path=self.devices[current]['path'];self.saved_camera_name=self.devices[current]['name']
        self.scanning=True;self.camera.set('');self.devices=[]
        self.camera_status.set('กำลังอ่านชื่ออุปกรณ์…');self.refresh_button.configure(state='disabled');self.source_changed()
        command=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(config.ROOT/'app.py')]
        def worker():
            try:
                env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
                result=subprocess.run(command+['--list-cameras'],capture_output=True,text=True,encoding='utf-8',errors='replace',
                                      env=env,cwd=str(config.ROOT),timeout=12,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode:raise RuntimeError(result.stderr.strip() or result.stdout.strip())
                data=json.loads(result.stdout)
                if not isinstance(data,list):raise ValueError('รายการกล้องไม่ถูกต้อง')
                self.discovery_queue.put((data,None))
            except subprocess.TimeoutExpired:self.discovery_queue.put(([], 'อ่านชื่อกล้องนานเกินไป กรุณากดรีเฟรชอีกครั้ง'))
            except Exception as exc:self.discovery_queue.put(([],str(exc)))
        threading.Thread(target=worker,daemon=True,name='camera-discovery').start()
        self.window.after(100,self.finish_discovery)

    def finish_discovery(self):
        try:devices,error=self.discovery_queue.get_nowait()
        except queue.Empty:
            self.window.after(100,self.finish_discovery);return
        self.scanning=False;self.devices=devices;self.refresh_button.configure(state='normal')
        self.camera_box.configure(values=display_labels(devices))
        selected=preferred_index(devices,self.saved_camera_path,self.saved_camera_name)
        if selected>=0:self.camera_box.current(selected)
        else:self.camera.set('')
        if error:self.camera_status.set(error)
        elif not devices:self.camera_status.set('ไม่พบกล้อง กรุณาเสียบอุปกรณ์แล้วกดรีเฟรช')
        elif selected<0:self.camera_status.set('ไม่พบกล้องเดิม กรุณาเลือกอุปกรณ์ใหม่')
        else:self.camera_status.set('แสดงชื่อตามที่ไดรเวอร์รายงาน • เสียบ/ถอดกล้องแล้วกดรีเฟรช')
        self.source_changed()

    def browse_video(self):
        from tkinter import filedialog
        path=filedialog.askopenfilename(parent=self.window,title='เลือกไฟล์วิดีโอ',filetypes=[('วิดีโอ','*.mp4 *.avi *.mov *.mkv *.wmv *.m4v'),('ทุกไฟล์','*.*')])
        if path:self.video.set(path)

    def browse_model(self):
        from tkinter import filedialog
        path=filedialog.askopenfilename(parent=self.window,title='เลือกโมเดลตรวจจับข้อต่อ',filetypes=[('โมเดล PyTorch','*.pt')])
        if path:self.model.set(path)

    def settings(self):
        device={}
        if self.source_type.get()=='camera':
            selected=self.camera_box.current()
            if self.scanning or not 0<=selected<len(self.devices):raise ValueError('กรุณารอค้นหากล้อง แล้วเลือกชื่ออุปกรณ์')
            device=self.devices[selected]
        return dict(mode=MODE_NAMES[self.mode.get()],source_type=self.source_type.get(),camera=str(device.get('index',0)),video=self.video.get(),image=self.image.get(),
                    camera_name=device.get('name',''),camera_path=device.get('path',''),camera_backend=device.get('backend',0),
                    subject=self.subject.get(),sound=self.sound.get(),side=SIDE_NAMES[self.side.get()],model=self.model.get())

    def start(self):
        from tkinter import messagebox
        if self.child is not None:return
        try:
            settings=self.settings();command=build_command(settings)
            self.settings_path.parent.mkdir(parents=True,exist_ok=True)
            self.settings_path.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
            self.spawn(command,'practice')
        except (ValueError,OSError) as exc:messagebox.showerror('ยังเริ่มไม่ได้',str(exc),parent=self.window)

    def open_review(self):
        from tkinter import messagebox
        if self.child is not None:return
        command=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(config.ROOT/'app.py')]
        try:self.spawn(command+['--review-only'],'review')
        except OSError as exc:messagebox.showerror('เปิดเว็บตรวจเหตุการณ์ไม่ได้',str(exc),parent=self.window)

    def test_sound(self):
        from tkinter import messagebox
        if self.child is not None:return
        command=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(config.ROOT/'app.py')]
        try:self.spawn(command+['--test-sound'],'sound')
        except OSError as exc:messagebox.showerror('เปิดเสียงไม่ได้',str(exc),parent=self.window)

    def spawn(self,command,kind):
        folder=config.DATA_ROOT/'logs';folder.mkdir(parents=True,exist_ok=True)
        self.log_path=folder/f'launcher-{time.time_ns()}.log'
        self.log=open(self.log_path,'w',encoding='utf-8')
        env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['PYTHONUNBUFFERED']='1'
        try:
            self.child=subprocess.Popen(command,cwd=str(config.ROOT),stdout=self.log,stderr=subprocess.STDOUT,
                                        env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception:
            self.log.close();self.log=None;raise
        self.kind=kind
        self.start_button.configure(state='disabled');self.test_button.configure(state='disabled');self.review_button.configure(state='disabled')
        self.status.set('กำลังเปิด… โหมดเฝ้าระวังใช้ปุ่มใน Dashboard / โหมดฝึกใช้ Space' if kind=='practice' else 'กำลังทดสอบเสียงสั้นและเสียงยาว…')
        if kind=='review':self.status.set('เปิดเว็บตรวจเหตุการณ์ย้อนหลังแล้ว ปิดรอบในเว็บเพื่อกลับเมนู')
        self.window.after(250,self.poll)

    def poll(self):
        if self.child is None:return
        code=self.child.poll()
        if code is None:
            self.window.after(250,self.poll);return
        self.child=None
        if self.log:self.log.close();self.log=None
        self.start_button.configure(state='normal');self.test_button.configure(state='normal');self.review_button.configure(state='normal')
        if code:
            from tkinter import messagebox
            self.status.set('เปิดไม่สำเร็จ ตรวจกล้อง/วิดีโอหรือรายละเอียดข้อผิดพลาด')
            try:details=self.log_path.read_text(encoding='utf-8',errors='replace')[-2200:]
            except OSError:details='ไม่สามารถอ่านรายละเอียดได้'
            messagebox.showerror('โปรแกรมแจ้งข้อผิดพลาด',f'{details}\n\nไฟล์บันทึก: {self.log_path}',parent=self.window)
        else:
            self.status.set('จบการฝึกแล้ว เลือกโหมดหรือแหล่งภาพใหม่ได้' if self.kind=='practice' else 'ทดสอบเสียงเสร็จ หากไม่ได้ยินให้ตรวจระดับเสียงของ Windows')

    def open_reports(self):
        from tkinter import messagebox
        try:
            config.REPORT_DIR.mkdir(parents=True,exist_ok=True)
            if os.name=='nt':os.startfile(str(config.REPORT_DIR))
            elif sys.platform=='darwin':subprocess.Popen(['open',str(config.REPORT_DIR)])
            else:subprocess.Popen(['xdg-open',str(config.REPORT_DIR)])
        except OSError as exc:messagebox.showerror('เปิดโฟลเดอร์ไม่ได้',str(exc),parent=self.window)

    def close(self):
        from tkinter import messagebox
        if self.child is not None and self.child.poll() is None:
            messagebox.showinfo('มีงานกำลังทำงาน','กด Esc ในหน้าฝึก หรือปุ่มปิดรอบใน Dashboard ก่อน\nหากกำลังทดสอบเสียง รอจนทดสอบเสร็จ',parent=self.window)
            return
        if self.log:self.log.close()
        self.window.destroy()

def main():
    import tkinter as tk
    window=tk.Tk();Launcher(window);window.mainloop()

if __name__=='__main__':main()
