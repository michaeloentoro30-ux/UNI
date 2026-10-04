```python
import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "data", "uniscout.db")
TUITION_DB_PATH = os.path.join(BASE_DIR, "data", "tuition_estimates.db")


SCHEMA = """
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

CREATE INDEX IF NOT EXISTS idx_universities_name
ON universities(name);

CREATE INDEX IF NOT EXISTS idx_universities_country
ON universities(country);

CREATE INDEX IF NOT EXISTS idx_universities_city
ON universities(city);

CREATE INDEX IF NOT EXISTS idx_universities_ranking
ON universities(ranking);


CREATE TABLE IF NOT EXISTS university_stats (
    university_id INTEGER PRIMARY KEY,
    popularity INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    FOREIGN KEY(university_id)
        REFERENCES universities(id)
        ON DELETE CASCADE
);
"""


def tuition_database_available():
    """
    Check whether the separate tuition database exists
    and contains the expected table.
    """
    if not os.path.exists(TUITION_DB_PATH):
        return False

    try:
        conn = sqlite3.connect(TUITION_DB_PATH)

        result = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'tuition_estimates'
            """
        ).fetchone()

        conn.close()

        return result is not None

    except Exception:
        return False


@contextmanager
def get_db():
    """
    Open the main UniScout database.

    The tuition database is attached when available.
    If it is missing, UniScout continues working normally.
    """

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")

    tuition_attached = False

    try:
        if tuition_database_available():
            try:
                conn.execute(
                    "ATTACH DATABASE ? AS tuition_db",
                    (TUITION_DB_PATH,)
                )
                tuition_attached = True
            except Exception:
                tuition_attached = False

        yield conn

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        if tuition_attached:
            try:
                conn.execute("DETACH DATABASE tuition_db")
            except Exception:
                pass

        conn.close()


def init_db():
    """
    Initialize the main UniScout database.
    """
    with get_db() as db:
        db.executescript(SCHEMA)


def split_list(value):
    """
    Convert pipe-separated database values into a Python list.
    """
    if not value:
        return []

    return [
        item.strip()
        for item in value.split("|")
        if item.strip()
    ]


def normalize_university(row):
    """
    Convert sqlite Row into a normal dictionary and add
    convenient fields for the application.
    """

    if row is None:
        return None

    university = dict(row)

    university["majors_list"] = split_list(
        university.get("majors")
    )

    university["degree_levels_list"] = split_list(
        university.get("degree_levels")
    )

    university["tuition_is_estimate"] = bool(
        university.get("tuition_estimated", 0)
    )

    return university


def _has_tuition_db(db):
    """
    Determine whether the tuition database is attached
    to this connection.
    """

    try:
        row = db.execute(
            """
            SELECT name
            FROM tuition_db.sqlite_master
            WHERE type = 'table'
              AND name = 'tuition_estimates'
            """
        ).fetchone()

        return row is not None

    except Exception:
        return False


def _university_select(db):
    """
    Build the main university SELECT query.

    Existing tuition stored in uniscout.db takes priority.
    Estimated tuition is used only when existing tuition is NULL.
    """

    if _has_tuition_db(db):

        return """
            SELECT
                u.id,
                u.name,
                u.country,
                u.country_code,
                u.city,
                u.website,
                u.logo_url,
                u.description,
                u.ranking,

                COALESCE(
                    u.tuition_min,
                    t.estimated_min
                ) AS tuition_min,

                COALESCE(
                    u.tuition_max,
                    t.estimated_max
                ) AS tuition_max,

                COALESCE(
                    u.tuition_currency,
                    t.currency
                ) AS tuition_currency,

                COALESCE(
                    u.tuition_period,
                    t.period
                ) AS tuition_period,

                CASE
                    WHEN u.tuition_min IS NULL
                     AND t.estimated_min IS NOT NULL
                    THEN 1
                    ELSE 0
                END AS tuition_estimated,

                u.university_type,
                u.student_count,
                u.international_student_count,
                u.majors,
                u.degree_levels,
                u.admission_requirements,
                u.application_deadline,
                u.source,
                u.source_id,
                u.last_updated,
                u.created_at

            FROM universities u

            LEFT JOIN tuition_db.tuition_estimates t
                ON t.university_id = u.id
        """

    return """
        SELECT
            u.id,
            u.name,
            u.country,
            u.country_code,
            u.city,
            u.website,
            u.logo_url,
            u.description,
            u.ranking,

            u.tuition_min AS tuition_min,
            u.tuition_max AS tuition_max,
            u.tuition_currency AS tuition_currency,
            u.tuition_period AS tuition_period,

            0 AS tuition_estimated,

            u.university_type,
            u.student_count,
            u.international_student_count,
            u.majors,
            u.degree_levels,
            u.admission_requirements,
            u.application_deadline,
            u.source,
            u.source_id,
            u.last_updated,
            u.created_at

        FROM universities u
    """


def list_distinct(column, country=None):

    allowed = {
        "country",
        "city",
        "majors",
        "university_type",
    }

    if column not in allowed:
        raise ValueError("Invalid column")

    with get_db() as db:

        if column == "majors":

            rows = db.execute(
                """
                SELECT majors
                FROM universities
                WHERE majors IS NOT NULL
                  AND majors != ''
                """
            ).fetchall()

            values = sorted(
                {
                    major.strip()
                    for row in rows
                    for major in split_list(row["majors"])
                },
                key=str.lower
            )

            return values

        if column == "city" and country:

            rows = db.execute(
                """
                SELECT DISTINCT city
                FROM universities
                WHERE city IS NOT NULL
                  AND city != ''
                  AND country = ?
                ORDER BY city COLLATE NOCASE
                """,
                (country,)
            ).fetchall()

        else:

            rows = db.execute(
                f"""
                SELECT DISTINCT {column}
                FROM universities
                WHERE {column} IS NOT NULL
                  AND {column} != ''
                ORDER BY {column} COLLATE NOCASE
                """
            ).fetchall()

        return [
            row[column]
            for row in rows
        ]


def search_universities(
    q="",
    country="",
    city="",
    major="",
    min_tuition=None,
    max_tuition=None,
    university_type="",
    min_ranking=None,
    limit=60,
    offset=0
):

    conditions = []
    params = []

    q = (q or "").strip()

    with get_db() as db:

        has_tuition = _has_tuition_db(db)

        if has_tuition:

            tuition_min = """
                COALESCE(u.tuition_min, t.estimated_min)
            """

            tuition_max = """
                COALESCE(u.tuition_max, t.estimated_max)
            """

            tuition_join = """
                LEFT JOIN tuition_db.tuition_estimates t
                    ON t.university_id = u.id
            """

        else:

            tuition_min = "u.tuition_min"
            tuition_max = "u.tuition_max"
            tuition_join = ""

        if q:

            like = f"%{q}%"

            conditions.append(
                """
                (
                    u.name LIKE ?
                    OR u.country LIKE ?
                    OR u.city LIKE ?
                    OR u.description LIKE ?
                    OR u.majors LIKE ?
                    OR u.country_code LIKE ?
                )
                """
            )

            params.extend(
                [like, like, like, like, like, like]
            )

        if country:

            conditions.append(
                "u.country = ?"
            )

            params.append(country)

        if city:

            conditions.append(
                "u.city = ?"
            )

            params.append(city)

        if major:

            conditions.append(
                "u.majors LIKE ?"
            )

            params.append(f"%{major}%")

        if min_tuition is not None:

            conditions.append(
                f"""
                (
                    {tuition_max} IS NULL
                    OR {tuition_max} >= ?
                )
                """
            )

            params.append(min_tuition)

        if max_tuition is not None:

            conditions.append(
                f"""
                (
                    {tuition_min} IS NULL
                    OR {tuition_min} <= ?
                )
                """
            )

            params.append(max_tuition)

        if university_type:

            conditions.append(
                "u.university_type = ?"
            )

            params.append(university_type)

        if min_ranking is not None:

            conditions.append(
                """
                (
                    u.ranking IS NOT NULL
                    AND u.ranking <= ?
                )
                """
            )

            params.append(min_ranking)

        where_clause = ""

        if conditions:

            where_clause = (
                "WHERE " +
                " AND ".join(conditions)
            )

        count_query = f"""
            SELECT COUNT(*)
            FROM universities u
            {tuition_join}
            {where_clause}
        """

        total = db.execute(
            count_query,
            params
        ).fetchone()[0]

        select_query = _university_select(db)

        rows = db.execute(
            f"""
            {select_query}

            {where_clause}

            ORDER BY
                CASE
                    WHEN u.ranking IS NULL
                    THEN 999999
                    ELSE u.ranking
                END ASC,

                u.name COLLATE NOCASE ASC

            LIMIT ?
            OFFSET ?
            """,
            params + [limit, offset]
        ).fetchall()

        return [
            normalize_university(row)
            for row in rows
        ], total


def get_university(uid):

    with get_db() as db:

        query = _university_select(db)

        row = db.execute(
            f"""
            {query}
            WHERE u.id = ?
            """,
            (uid,)
        ).fetchone()

        if row:

            try:
                db.execute(
                    """
                    INSERT OR IGNORE INTO university_stats
                    (university_id, popularity, views)
                    VALUES (?, 0, 0)
                    """,
                    (uid,)
                )

                db.execute(
                    """
                    UPDATE university_stats
                    SET views = views + 1
                    WHERE university_id = ?
                    """,
                    (uid,)
                )

            except sqlite3.Error:
                pass

        return normalize_university(row)


def suggestions(q, limit=10):

    q = (q or "").strip()

    if len(q) < 2:
        return []

    like = f"%{q}%"

    results = []

    with get_db() as db:

        rows = db.execute(
            """
            SELECT id, name, city, country
            FROM universities
            WHERE name LIKE ?
            ORDER BY name
            LIMIT ?
            """,
            (like, limit)
        ).fetchall()

        for row in rows:

            results.append(
                {
                    "type": "university",
                    "label": row["name"],
                    "sub": (
                        f"{row['city'] or 'Unknown city'}, "
                        f"{row['country'] or 'Unknown country'}"
                    ),
                    "value": row["name"]
                }
            )

        remaining = limit - len(results)

        if remaining > 0:

            rows = db.execute(
                """
                SELECT DISTINCT country
                FROM universities
                WHERE country LIKE ?
                ORDER BY country
                LIMIT ?
                """,
                (like, remaining)
            ).fetchall()

            for row in rows:

                results.append(
                    {
                        "type": "country",
                        "label": row["country"],
                        "sub": "Country",
                        "value": row["country"]
                    }
                )

        remaining = limit - len(results)

        if remaining > 0:

            rows = db.execute(
                """
                SELECT DISTINCT city, country
                FROM universities
                WHERE city LIKE ?
                ORDER BY city
                LIMIT ?
                """,
                (like, remaining)
            ).fetchall()

            for row in rows:

                results.append(
                    {
                        "type": "city",
                        "label": row["city"],
                        "sub": row["country"] or "City",
                        "value": row["city"]
                    }
                )

        remaining = limit - len(results)

        if remaining > 0:

            rows = db.execute(
                """
                SELECT majors
                FROM universities
                WHERE majors LIKE ?
                LIMIT 30
                """,
                (like,)
            ).fetchall()

            majors = sorted(
                {
                    major
                    for row in rows
                    for major in split_list(row["majors"])
                    if q.lower() in major.lower()
                },
                key=str.lower
            )

            for major in majors[:remaining]:

                results.append(
                    {
                        "type": "major",
                        "label": major,
                        "sub": "Major",
                        "value": major
                    }
                )

    return results[:limit]


def upsert_university(record):

    fields = [
        "name",
        "country",
        "country_code",
        "city",
        "website",
        "logo_url",
        "description",
        "ranking",
        "tuition_min",
        "tuition_max",
        "tuition_currency",
        "tuition_period",
        "university_type",
        "student_count",
        "international_student_count",
        "majors",
        "degree_levels",
        "admission_requirements",
        "application_deadline",
        "source",
        "source_id",
        "last_updated"
    ]

    data = {
        field: record.get(field)
        for field in fields
    }

    with get_db() as db:

        existing = None

        if data["source"] and data["source_id"]:

            existing = db.execute(
                """
                SELECT id
                FROM universities
                WHERE source = ?
                  AND source_id = ?
                """,
                (
                    data["source"],
                    data["source_id"]
                )
            ).fetchone()

        if existing:

            update_fields = [
                field
                for field in fields
                if field not in (
                    "source",
                    "source_id"
                )
            ]

            set_clause = ", ".join(
                f"{field} = ?"
                for field in update_fields
            )

            values = [
                data[field]
                for field in update_fields
            ]

            values.append(existing["id"])

            db.execute(
                f"""
                UPDATE universities
                SET {set_clause}
                WHERE id = ?
                """,
                values
            )

            return "updated", existing["id"]

        duplicate = db.execute(
            """
            SELECT id
            FROM universities
            WHERE lower(name) = lower(?)
              AND lower(
                    COALESCE(country, '')
                  ) = lower(
                    COALESCE(?, '')
                  )
            """,
            (
                data["name"],
                data["country"]
            )
        ).fetchone()

        if duplicate:

            return "skipped", duplicate["id"]

        columns = ",".join(fields)

        placeholders = ",".join(
            "?"
            for _ in fields
        )

        cursor = db.execute(
            f"""
            INSERT INTO universities
            ({columns})
            VALUES
            ({placeholders})
            """,
            [
                data[field]
                for field in fields
            ]
        )

        university_id = cursor.lastrowid

        db.execute(
            """
            INSERT OR IGNORE INTO university_stats
            (university_id, popularity, views)
            VALUES (?, 0, 0)
            """,
            (university_id,)
        )

        return "new", university_id
```
