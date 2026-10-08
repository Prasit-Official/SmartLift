import csv
import json
from datetime import datetime, timezone
from uuid import uuid4
from config import FEATURE_COLUMNS

class Recorder:
    def __init__(self, output, subject, mode, criteria):
        self.session_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid4().hex[:8]
        self.folder=output/self.session_id
        self.folder.mkdir(parents=True,exist_ok=False)
        self.subject=subject; self.mode=mode; self.criteria=criteria; self.events=[]
        self.handle=open(self.folder/"features.csv","w",newline="",encoding="utf-8-sig")
        fields=["subject_id","session_id","timestamp","mode","phase","criteria_version","valid","side"]+FEATURE_COLUMNS+["rule_status","alert_level","label"]
        self.writer=csv.DictWriter(self.handle,fieldnames=fields)
        self.writer.writeheader()
        self.counts={}
    def record(self,now,features,phase,assessment):
        row=dict(subject_id=self.subject,session_id=self.session_id,timestamp=now,mode=self.mode,phase=phase,
                 criteria_version=self.criteria["version"],valid=features is not None,rule_status=assessment.status,alert_level=assessment.alert_level,label="")
        if features: row.update(features)
        self.writer.writerow(row)
        self.counts[assessment.status]=self.counts.get(assessment.status,0)+1
    def add_event(self,event):
        if event: self.events.append(event)
    def close(self):
        self.handle.close()
        report={"session_id":self.session_id,"subject_id":self.subject,"mode":self.mode,
                "criteria":self.criteria,"sample_counts":self.counts,"cycles":self.events,
                "note":"Prototype posture observations only. No object lift or overall safety verification."}
        (self.folder/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        from session.report import export_cycles
        export_cycles(self.folder,self.events)
