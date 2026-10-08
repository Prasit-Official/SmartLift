from dataclasses import dataclass, field

@dataclass
class Assessment:
    status: str
    reasons: list = field(default_factory=list)
    unassessed: list = field(default_factory=lambda:["Spinal curvature", "Load weight / object distance", "Twisting / grip"])
    alert_level: str = "NONE"

class RuleEngine:
    def __init__(self, criteria): self.rules=criteria["rules"]
    def assess(self, features):
        if features is None:
            return Assessment("UNKNOWN",["Required shoulder / hip / knee / ankle not visible"])
        trunk,knee=features["trunk_inclination"],features["knee_angle"]
        if trunk>self.rules["stoop_trunk_min"] and knee>self.rules["stoop_knee_min"]:
            return Assessment("REVIEW",["Large trunk inclination with limited knee flexion"],alert_level="DANGER")
        if trunk>self.rules["trunk_review_min"]:
            return Assessment("REVIEW",["Trunk inclination exceeds prototype review threshold"],alert_level="WARNING")
        return Assessment("OBSERVED",["No prototype angle flag; this is not a safety clearance"])
