from assessment.rules import Assessment

class StandingAssessment:
    def __init__(self, criteria):
        self.c=criteria["standing"]
        self.posture=criteria["cycle"]
        self.reset()
    def reset(self):
        self.anchor=None
        self.since=None
    def update(self, features, now):
        if features is None:
            self.reset()
            return Assessment("UNKNOWN",["Standing observation interrupted"])
        if features["knee_angle"] < self.posture["up_knee_min"] or features["trunk_inclination"] > self.posture["up_trunk_max"]:
            self.reset()
            return Assessment("UNKNOWN",["Outside prototype standing observation range"],["Workstation fit", "Balance / weight distribution"])
        values=(features["trunk_inclination"],features["knee_angle"])
        if self.anchor is None or max(abs(a-b) for a,b in zip(values,self.anchor))>=self.c["movement_change_degrees"]:
            self.anchor=values; self.since=now
        if now-self.since>=self.c["reminder_seconds"]:
            return Assessment("REMINDER",["Little observed angle change; consider changing position"],["Workstation fit", "Balance / weight distribution"])
        return Assessment("OBSERVED",["Standing observation: posture variation timer active"],["Workstation fit", "Balance / weight distribution"])
