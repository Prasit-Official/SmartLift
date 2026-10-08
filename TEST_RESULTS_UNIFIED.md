# Unified monitoring verification

- Python unittest suite: 93 PASS (78 existing + 15 added).
- Added: independent angles/timers/cycles across IDs; simultaneous leg and lifting alerts; concurrent standing reminder; missing/gapped observations; 20 separate state instances.
- Archive: full frame/crop bytes and per-person metrics; persisted reviews after reopening; distinct sessions with reused IDs; invalid paths/events/statuses rejected.
- HTTP: historical event retrieval and persisted review; review-only mode rejects starting inference.
- Dashboard JavaScript syntax check PASS. No browser-rendering claim.
- Camera, live YOLO, Windows audio, actual crowd accuracy and hardware FPS not tested here.
