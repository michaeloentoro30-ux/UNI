from datetime import datetime, timezone
from database import upsert_university

def clean_text(v):
    return (v or '').strip() or None

def normalize_openalex(item):
    geo = item.get('geo') or {}
    country = geo.get('country') or ''
    cc = geo.get('country_code') or ''
    city = geo.get('city') or ''
    website = item.get('homepage_url') or item.get('website_url') or ''
    ids = item.get('ids') or {}
    source_id = str(item.get('id') or ids.get('openalex') or '')
    return {
        'name': clean_text(item.get('display_name') or item.get('name')) or 'Unnamed institution',
        'country': clean_text(country), 'country_code': clean_text(cc), 'city': clean_text(city),
        'website': clean_text(website), 'logo_url': clean_text(item.get('image_url')),
        'description': None, 'ranking': None, 'tuition_min': None, 'tuition_max': None,
        'tuition_currency': None, 'tuition_period': 'year', 'university_type': 'University',
        'student_count': None, 'international_student_count': None, 'majors': None,
        'degree_levels': None, 'admission_requirements': None, 'application_deadline': None,
        'source': 'OpenAlex', 'source_id': source_id,
        'last_updated': datetime.now(timezone.utc).isoformat()
    }

def import_records(records):
    stats = {'new':0,'updated':0,'skipped':0,'errors':0}
    for record in records:
        try:
            status, _ = upsert_university(record); stats[status] += 1
        except Exception as exc:
            stats['errors'] += 1
            print('Import error:', exc)
    return stats
