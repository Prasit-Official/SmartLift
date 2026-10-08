# ผลตรวจสอบ 2026-09-26

- Python unit/integration tests: 21 ผ่าน (geometry, missing data, side lock, cycle state, gaps, reports, standing reminder, grouped training/load roundtrip)
- Python source syntax: ผ่าน
- CLI `python app.py --help`: ผ่าน
- JavaScript syntax: ผ่าน
- แบบทดสอบเว็บไซต์: ตรวจคะแนนก่อน/หลัง เฉลย รหัสผู้ฝึก และ JSON export ผ่านด้วย DOM stub
- ทดสอบ classifier ด้วยข้อมูลสังเคราะห์เพื่อเช็กการเชื่อมต่อเท่านั้น ไม่ใช่หลักฐานความแม่นยำกับคนจริง

ยังไม่ได้ทดสอบ:
- ภาพจากกล้องจริง / YOLO inference (ไม่มี cv2, ultralytics และ weights ในเครื่องทดสอบนี้)
- การแสดงผลเว็บไซต์บนเบราว์เซอร์จริง: Playwright มีแต่ไม่มี Chromium executable
- Windows executable build และการติดตั้งบนเครื่องผู้ใช้
- ความสอดคล้องของค่ามุมกับผู้ประเมินด้านการยศาสตร์

คำสั่งทดสอบ:
```
python -m unittest discover -s tests -v
node tests/test_website.cjs
```
