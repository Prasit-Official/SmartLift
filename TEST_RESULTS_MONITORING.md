# Monitoring verification — 2026-10-02

- `python -m unittest discover -s tests -q`: 78 PASS.
- Includes existing 51 tests, launcher monitoring selection, 26 monitoring tests.
- Real loopback HTTP tests exercise page/token substitution, state, command authorization, snapshot access.
- Runner integration uses mocked model, camera and image codec to verify start/pause/resume/EOF/cleanup.
- Synthetic keypoint geometry checks neutral/raised nose-ear angle, standing and bent raised leg.
- `node tests/test_website.cjs`: archived training quiz tests PASS.
- Live YOLO inference, actual camera/video decoding and performance with 3/5/10 people are NOT tested (OpenCV/model unavailable here).
- Windows sound/device integration and executable packaging are NOT tested here.
- Browser visual validation NOT performed: both browser downloads failed (invalid archive).

Passing tests verify implementation behavior under the stated fixtures; they do not establish sensitivity, specificity, physical risk, or clinical validity.

- Dashboard JavaScript syntax check: PASS (no browser rendering claim).
