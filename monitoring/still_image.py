"""Static geometry preview: fresh state per person, no incident or time claim."""
from monitoring.unified import UnifiedEngine


def load_image(path):
    import numpy as np
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(path) as image:
            if image.format not in ('JPEG', 'PNG', 'BMP', 'WEBP'):
                raise ValueError('รองรับภาพ JPG, PNG, BMP และ WEBP เท่านั้น')
            if getattr(image, 'is_animated', False):
                raise ValueError('กรุณาเลือกภาพนิ่ง ไม่ใช่ภาพเคลื่อนไหว')
            rgb = ImageOps.exif_transpose(image).convert('RGB')
            return np.asarray(rgb)[:, :, ::-1].copy()
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError('เปิดภาพไม่ได้ กรุณาเลือกไฟล์ภาพที่สมบูรณ์') from exc


def assess_image_person(person_id, obs, joints, criteria, settings, zone_type, side='auto'):
    # Reuse geometry rules with zero geometric dwell in a private, one-shot engine.
    # Persisted monitoring settings are never changed; no frame is replayed.
    preview = dict(settings)
    preview.update(posture_dwell=0, leg_dwell=0, forbidden_dwell=0)
    engine = UnifiedEngine(criteria, preview, side)
    engine.safety.zone_type = zone_type
    person = engine.update(person_id, obs, 0, joints)
    angle = person.get('head_angle')
    threshold = settings['head_absolute'] * (.2 if person.get('head_method') == 'front_eyes' else 1)
    if angle is not None and angle >= threshold:
        person['reasons'].append('สงสัยแหงนหน้าจากภาพเดียว — ยังยืนยันการค้างท่าไม่ได้')
        if person['level'] != 'DANGER':person['level'] = 'WARNING'
    person.update(is_image=True, temporal_assessed=False, zone_episode=None,
                  lift_reps=None, lift_attempts=None, last_rep=None,
                  lift_phase='NOT_ASSESSED', standing_seconds=None)
    person['assessments']['standing'] = 'NOT_ASSESSED'
    return person
