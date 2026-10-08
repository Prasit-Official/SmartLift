class LiftCycle:
    """Counts posture practice cycles, not confirmed object lifts."""
    def __init__(self, criteria):
        self.c=criteria["cycle"]
        self.max_gap=criteria["quality"]["max_gap_seconds"]
        self.total=0
        self.reset()

    def reset(self):
        self.phase="WAIT_READY"
        self.candidate=None
        self.since=None
        self.started=None
        self.missing_since=None
        self.last_valid=None
        self.review=False
        self.incomplete=False

    def stable(self, name, condition, now):
        if not condition:
            self.candidate=None; self.since=None
            return False
        if self.candidate!=name:
            self.candidate=name; self.since=now
            return False
        return now-self.since>=self.c["dwell_seconds"]

    def finish(self, now, force_incomplete=False):
        self.total+=1
        outcome="INCOMPLETE" if self.incomplete or force_incomplete else ("REVIEW" if self.review else "OBSERVED")
        event={"rep_id":self.total,"started":self.started,"ended":now,"outcome":outcome}
        self.reset()
        return event

    def update(self, features, assessment, now):
        if self.last_valid is not None and now-self.last_valid>self.max_gap:
            if self.started is not None:
                return self.finish(now,True)
            self.reset()
        if features is None:
            self.candidate=None; self.since=None
            if self.started is not None: self.incomplete=True
            if self.missing_since is None: self.missing_since=now
            if now-self.missing_since>=self.max_gap:
                if self.started is not None: return self.finish(now,True)
                self.reset()
            return None
        self.last_valid=now
        self.missing_since=None
        knee,trunk=features["knee_angle"],features["trunk_inclination"]
        upright=knee>=self.c["up_knee_min"] and trunk<=self.c["up_trunk_max"]
        if self.phase=="WAIT_READY":
            if self.stable("ready",upright,now):
                self.phase="READY"; self.candidate=None
        elif self.phase=="READY":
            if not upright:
                self.phase="DESCENDING"; self.started=now
                self.review=assessment.status=="REVIEW"; self.candidate=None
        elif self.phase=="DESCENDING":
            self.review |= assessment.status=="REVIEW"
            if self.stable("down",knee<=self.c["down_knee_max"],now):
                self.phase="LOWERED"; self.candidate=None
            elif upright:
                return self.finish(now,True)
        elif self.phase in ("LOWERED","RISING"):
            self.review |= assessment.status=="REVIEW"
            if knee>self.c["down_knee_max"]:
                self.phase="RISING"
            if self.stable("finished",upright,now):
                return self.finish(now)
        if self.started is not None and now-self.started>self.c["max_cycle_seconds"]:
            return self.finish(now,True)
        return None

    def abort(self,now):
        return self.finish(now,True) if self.started is not None else None
