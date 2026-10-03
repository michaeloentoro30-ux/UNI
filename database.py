import os, sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'uniscout.db')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS universities (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 country TEXT,
 country_code TEXT,
 city TEXT,
 website TEXT,
 logo_url TEXT,
 description TEXT,
 ranking INTEGER,
 tuition_min REAL,
 tuition_max REAL,
 tuition_currency TEXT,
 tuition_period TEXT,
 university_type TEXT,
 student_count INTEGER,
 international_student_count INTEGER,
 majors TEXT,
 degree_levels TEXT,
 admission_requirements TEXT,
 application_deadline TEXT,
 source TEXT,
 source_id TEXT,
 last_updated TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_universities_name ON universities(name);
CREATE INDEX IF NOT EXISTS idx_universities_country ON universities(country);
CREATE INDEX IF NOT EXISTS idx_universities_city ON universities(city);
CREATE INDEX IF NOT EXISTS idx_universities_ranking ON universities(ranking);
CREATE INDEX IF NOT EXISTS idx_universities_type ON universities(university_type);
CREATE TABLE IF NOT EXISTS university_stats (
 university_id INTEGER PRIMARY KEY,
 popularity INTEGER DEFAULT 0,
 views INTEGER DEFAULT 0,
 FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE CASCADE
);
'''

@contextmanager
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)

def row_to_dict(row):
    return dict(row) if row else None

def split_list(value):
    if not value: return []
    return [x.strip() for x in value.split('|') if x.strip()]

def normalize_university(row):
    if not row: return None
    d = dict(row)
    d['majors_list'] = split_list(d.get('majors'))
    d['degree_levels_list'] = split_list(d.get('degree_levels'))
    return d

def list_distinct(column, country=None):
    allowed = {'country','city','majors','university_type'}
    if column not in allowed: raise ValueError('Invalid column')
    with get_db() as db:
        if column == 'majors':
            rows = db.execute('SELECT majors FROM universities WHERE majors IS NOT NULL AND majors != ""').fetchall()
            vals = sorted({m.strip() for r in rows for m in split_list(r['majors'])}, key=str.lower)
        else:
            if column == 'city' and country:
                rows = db.execute('SELECT DISTINCT city FROM universities WHERE city IS NOT NULL AND city != "" AND country = ? ORDER BY city COLLATE NOCASE', (country,)).fetchall()
            else:
                rows = db.execute(f'SELECT DISTINCT {column} FROM universities WHERE {column} IS NOT NULL AND {column} != "" ORDER BY {column} COLLATE NOCASE').fetchall()
            vals = [r[column] for r in rows]
    return vals

def search_universities(q='', country='', city='', major='', min_tuition=None, max_tuition=None, university_type='', min_ranking=None, limit=60, offset=0):
    clauses, params = [], []
    q = (q or '').strip()
    if q:
        like = f'%{q}%'
        clauses.append('(name LIKE ? OR country LIKE ? OR city LIKE ? OR description LIKE ? OR majors LIKE ? OR country_code LIKE ?)')
        params += [like]*6
    if country: clauses.append('country = ?'); params.append(country)
    if city: clauses.append('city = ?'); params.append(city)
    if major: clauses.append('majors LIKE ?'); params.append(f'%{major}%')
    if min_tuition is not None: clauses.append('(tuition_max IS NULL OR tuition_max >= ?)'); params.append(min_tuition)
    if max_tuition is not None: clauses.append('(tuition_min IS NULL OR tuition_min <= ?)'); params.append(max_tuition)
    if university_type: clauses.append('university_type = ?'); params.append(university_type)
    if min_ranking is not None: clauses.append('(ranking IS NOT NULL AND ranking <= ?)'); params.append(min_ranking)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    order = 'ORDER BY CASE WHEN ranking IS NULL THEN 999999 ELSE ranking END ASC, name COLLATE NOCASE ASC'
    with get_db() as db:
        total = db.execute(f'SELECT COUNT(*) FROM universities{where}', params).fetchone()[0]
        rows = db.execute(f'SELECT * FROM universities{where} {order} LIMIT ? OFFSET ?', params + [limit, offset]).fetchall()
    return [normalize_university(r) for r in rows], total

def get_university(uid):
    with get_db() as db:
        row = db.execute('SELECT * FROM universities WHERE id = ?', (uid,)).fetchone()
        if row:
            db.execute('UPDATE university_stats SET views = views + 1 WHERE university_id = ?', (uid,))
    return normalize_university(row)

def suggestions(q, limit=10):
    q = (q or '').strip()
    if len(q) < 2: return []
    like = f'%{q}%'
    out = []
    with get_db() as db:
        rows = db.execute('SELECT id,name,city,country FROM universities WHERE name LIKE ? ORDER BY name LIMIT ?', (like, limit)).fetchall()
        out += [{'type':'university','label':r['name'],'sub':f"{r['city'] or 'Unknown city'}, {r['country'] or 'Unknown country'}",'value':r['name']} for r in rows]
        remaining = limit-len(out)
        if remaining > 0:
            rows = db.execute('SELECT DISTINCT country FROM universities WHERE country LIKE ? ORDER BY country LIMIT ?', (like, remaining)).fetchall()
            out += [{'type':'country','label':r['country'],'sub':'Country','value':r['country']} for r in rows]
        remaining = limit-len(out)
        if remaining > 0:
            rows = db.execute('SELECT DISTINCT city,country FROM universities WHERE city LIKE ? ORDER BY city LIMIT ?', (like, remaining)).fetchall()
            out += [{'type':'city','label':r['city'],'sub':r['country'] or 'City','value':r['city']} for r in rows]
        remaining = limit-len(out)
        if remaining > 0:
            rows = db.execute('SELECT majors FROM universities WHERE majors LIKE ? LIMIT 30', (like,)).fetchall()
            majors = sorted({m for r in rows for m in split_list(r['majors']) if q.lower() in m.lower()}, key=str.lower)[:remaining]
            out += [{'type':'major','label':m,'sub':'Major','value':m} for m in majors]
    return out[:limit]

def upsert_university(record):
    fields = ['name','country','country_code','city','website','logo_url','description','ranking','tuition_min','tuition_max','tuition_currency','tuition_period','university_type','student_count','international_student_count','majors','degree_levels','admission_requirements','application_deadline','source','source_id','last_updated']
    data = {k: record.get(k) for k in fields}
    with get_db() as db:
        existing = db.execute('SELECT id FROM universities WHERE source = ? AND source_id = ?', (data['source'], data['source_id'])).fetchone() if data['source'] and data['source_id'] else None
        if existing:
            sets = ', '.join(f'{k} = ?' for k in fields if k not in ('source','source_id'))
            vals = [data[k] for k in fields if k not in ('source','source_id')] + [existing['id']]
            db.execute(f'UPDATE universities SET {sets} WHERE id = ?', vals)
            return 'updated', existing['id']
        duplicate = db.execute('SELECT id FROM universities WHERE lower(name)=lower(?) AND lower(COALESCE(country,""))=lower(COALESCE(?,""))', (data['name'], data['country'])).fetchone()
        if duplicate:
            return 'skipped', duplicate['id']
        cols = ','.join(fields); marks = ','.join('?' for _ in fields)
        cur = db.execute(f'INSERT INTO universities ({cols}) VALUES ({marks})', [data[k] for k in fields])
        uid = cur.lastrowid
        db.execute('INSERT OR IGNORE INTO university_stats(university_id) VALUES(?)', (uid,))
        return 'new', uid
