# Zone/head regression verification

113 Python tests PASS: previous coverage + 20 new tests for frontal/ear/eye head cues, small left/right extended-leg lifts, level-feet squat rejection, partial landmarks, no-entry immediate event, hazard-zone contact, repeated entry before cooldown, and expired leg references.
Existing missing-track test updated for intended behavior: clear sustained timers immediately, preserve calibration briefly, expire after the configured gap.
JavaScript syntax PASS. Browser rendering, real YOLO inference, live camera accuracy and Windows sound not validated in this environment.
No sensitivity/specificity claim is made from synthetic landmark tests.
