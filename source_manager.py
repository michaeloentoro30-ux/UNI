import logging
from typing import Any, Dict, Iterable

from database import init_db, upsert_university

logger = logging.getLogger(__name__)


# ============================================================
# ESTIMATED TUITION BY COUNTRY
# ============================================================
#
# These are ESTIMATES in USD per academic year.
# They are NOT official university tuition figures.
#
# The goal is to make UniScout useful for comparing thousands
# of universities where official tuition data is unavailable.
#

COUNTRY_TUITION_USD = {
    "United States": 28000,
    "United Kingdom": 22000,
    "Canada": 18000,
    "Australia": 22000,
    "New Zealand": 18000,

    "Germany": 1500,
    "France": 4500,
    "Netherlands": 12000,
    "Belgium": 6000,
    "Switzerland": 18000,
    "Austria": 3000,
    "Italy": 3500,
    "Spain": 3000,
    "Portugal": 3000,
    "Ireland": 16000,

    "Denmark": 10000,
    "Sweden": 12000,
    "Norway": 1500,
    "Finland": 10000,

    "Poland": 3500,
    "Czechia": 3500,
    "Czech Republic": 3500,
    "Hungary": 5000,
    "Romania": 3000,
    "Greece": 3000,

    "Japan": 9000,
    "South Korea": 7000,
    "China": 5000,
    "Hong Kong": 18000,
    "Singapore": 18000,
    "Taiwan": 5000,

    "India": 2500,
    "Indonesia": 3000,
    "Malaysia": 5000,
    "Thailand": 4500,
    "Vietnam": 3000,
    "Philippines": 3500,

    "United Arab Emirates": 18000,
    "Saudi Arabia": 12000,
    "Turkey": 4000,

    "Brazil": 5000,
    "Mexico": 6000,
    "Argentina": 3000,
    "Chile": 6000,
    "Colombia": 4000,

    "South Africa": 4000,
    "Egypt": 3000,
    "Nigeria": 2500,
    "Kenya": 2500,

    "Russia": 4000,
    "Ukraine": 3000,

    "Israel": 12000,

    "Pakistan": 2500,
    "Bangladesh": 2000,

    "Iran": 2500,
}


# ============================================================
# CURRENCY
# ============================================================

COUNTRY_CURRENCY = {
    "United States": "USD",
    "Canada": "CAD",
    "United Kingdom": "GBP",
    "Australia": "AUD",
    "New Zealand": "NZD",

    "Germany": "EUR",
    "France": "EUR",
    "Netherlands": "EUR",
    "Belgium": "EUR",
    "Austria": "EUR",
    "Italy": "EUR",
    "Spain": "EUR",
    "Portugal": "EUR",
    "Ireland": "EUR",
    "Finland": "EUR",
    "Greece": "EUR",

    "Switzerland": "CHF",

    "Denmark": "DKK",
    "Sweden": "SEK",
    "Norway": "NOK",

    "Poland": "PLN",
    "Czechia": "CZK",
    "Czech Republic": "CZK",
    "Hungary": "HUF",
    "Romania": "RON",

    "Japan": "JPY",
    "South Korea": "KRW",
    "China": "CNY",
    "Hong Kong": "HKD",
    "Singapore": "SGD",
    "Taiwan": "TWD",

    "India": "INR",
    "Indonesia": "IDR",
    "Malaysia": "MYR",
    "Thailand": "THB",
    "Vietnam": "VND",
    "Philippines": "PHP",

    "United Arab Emirates": "AED",
    "Saudi Arabia": "SAR",
    "Turkey": "TRY",

    "Brazil": "BRL",
    "Mexico": "MXN",
    "Argentina": "ARS",
    "Chile": "CLP",
    "Colombia": "COP",

    "South Africa": "ZAR",
    "Egypt": "EGP",
    "Nigeria": "NGN",
    "Kenya": "KES",

    "Russia": "RUB",
    "Ukraine": "UAH",

    "Israel": "ILS",

    "Pakistan": "PKR",
    "Bangladesh": "BDT",

    "Iran": "IRR",
}


# ============================================================
# HELPERS
# ============================================================

def _first(
    value: Any,
    default: str = "",
) -> str:

    if isinstance(value, list):

        if not value:
            return default

        return str(value[0])

    if value is None:
        return default

    return str(value)


def _country_name(
    record: Dict[str, Any],
) -> str:

    country = record.get("country")

    if isinstance(country, dict):

        return (
            country.get("display_name")
            or country.get("name")
            or ""
        )

    return _first(country)


def _country_code(
    record: Dict[str, Any],
) -> str:

    country = record.get("country")

    if isinstance(country, dict):

        return (
            country.get("country_code")
            or country.get("code")
            or ""
        )

    return (
        record.get("country_code")
        or ""
    )


def _city_name(
    record: Dict[str, Any],
) -> str:

    return (
        record.get("city")
        or record.get("city_name")
        or record.get("location_city")
        or ""
    )


def _website(
    record: Dict[str, Any],
) -> str:

    return (
        record.get("website")
        or record.get("homepage")
        or record.get("homepage_url")
        or ""
    )


def _openalex_id(
    record: Dict[str, Any],
) -> str:

    value = (
        record.get("id")
        or record.get("openalex_id")
        or ""
    )

    return str(value)


# ============================================================
# TUITION
# ============================================================

def _estimate_tuition(
    country: str,
) -> int:

    return COUNTRY_TUITION_USD.get(
        country,
        7000,
    )


def _tuition_range(
    country: str,
) -> tuple:

    base = _estimate_tuition(
        country
    )

    # Give a realistic estimated range
    # instead of pretending there is one
    # exact price for every institution.

    minimum = int(
        base * 0.70
    )

    maximum = int(
        base * 1.35
    )

    return (
        minimum,
        maximum,
    )


# ============================================================
# STUDENTS
# ============================================================

def _stable_seed(
    record: Dict[str, Any],
) -> int:

    institution_id = str(
        record.get("id")
        or record.get("openalex_id")
        or record.get("display_name")
        or ""
    )

    return sum(
        ord(character)
        for character in institution_id
    )


def _estimate_students(
    record: Dict[str, Any],
) -> int:

    values = [
        1200,
        2500,
        4000,
        6000,
        8000,
        12000,
        18000,
        25000,
        35000,
        50000,
        75000,
    ]

    seed = _stable_seed(
        record
    )

    return values[
        seed % len(values)
    ]


def _estimate_international_students(
    students: int,
    country: str,
) -> int:

    rates = {
        "United States": 0.12,
        "United Kingdom": 0.25,
        "Australia": 0.30,
        "Canada": 0.22,
        "New Zealand": 0.25,

        "Germany": 0.15,
        "France": 0.15,
        "Netherlands": 0.20,
        "Switzerland": 0.25,

        "Japan": 0.08,
        "South Korea": 0.08,
        "China": 0.05,

        "India": 0.05,
        "Indonesia": 0.04,
        "Malaysia": 0.15,
        "Singapore": 0.25,

        "United Arab Emirates": 0.70,

        "Saudi Arabia": 0.30,

        "Turkey": 0.08,

        "Brazil": 0.05,
        "Mexico": 0.06,

        "South Africa": 0.10,
    }

    rate = rates.get(
        country,
        0.08,
    )

    return max(
        0,
        int(
            students * rate
        ),
    )


# ============================================================
# MAJORS
# ============================================================

MAJOR_KEYWORDS = {
    "computer": "Computer Science",
    "computing": "Computer Science",
    "software": "Software Engineering",
    "informatics": "Information Technology",

    "engineering": "Engineering",
    "mechanical": "Mechanical Engineering",
    "electrical": "Electrical Engineering",
    "civil engineering": "Civil Engineering",

    "biology": "Biology",
    "biomedical": "Biomedical Science",
    "medicine": "Medicine",
    "health": "Health Sciences",
    "nursing": "Nursing",

    "business": "Business",
    "management": "Business Administration",
    "economics": "Economics",
    "finance": "Finance",
    "accounting": "Accounting",
    "marketing": "Marketing",

    "psychology": "Psychology",
    "chemistry": "Chemistry",
    "physics": "Physics",
    "mathematics": "Mathematics",

    "law": "Law",
    "education": "Education",

    "political": "Political Science",
    "international relations": "International Relations",
    "sociology": "Sociology",
    "anthropology": "Anthropology",

    "history": "History",
    "philosophy": "Philosophy",

    "arts": "Arts",
    "design": "Design",
    "architecture": "Architecture",

    "environment": "Environmental Science",
    "agriculture": "Agriculture",
    "forestry": "Forestry",

    "communication": "Communications",
    "media": "Media Studies",

    "geography": "Geography",
}


DEFAULT_MAJORS = [
    "Computer Science",
    "Business",
    "Engineering",
    "Economics",
    "Psychology",
    "Biology",
    "Mathematics",
    "Social Sciences",
    "Arts",
    "Natural Sciences",
]


def _estimate_majors(
    record: Dict[str, Any],
) -> list:

    concepts = (
        record.get(
            "x_concepts"
        )
        or []
    )

    concept_names = []

    for concept in concepts:

        if not isinstance(
            concept,
            dict,
        ):
            continue

        name = (
            concept.get(
                "display_name"
            )
            or concept.get(
                "name"
            )
        )

        if name:
            concept_names.append(
                str(name)
            )

    majors = []

    # Use OpenAlex concepts to personalize
    # the estimated majors.

    for name in concept_names:

        lower = name.lower()

        for keyword, major in MAJOR_KEYWORDS.items():

            if keyword in lower:

                if major not in majors:

                    majors.append(
                        major
                    )

    # Add general majors so every university
    # has useful discovery data.

    seed = _stable_seed(
        record
    )

    rotated_defaults = (
        DEFAULT_MAJORS[
            seed % len(DEFAULT_MAJORS):
        ]
        + DEFAULT_MAJORS[
            : seed % len(DEFAULT_MAJORS)
        ]
    )

    for major in rotated_defaults:

        if len(majors) >= 10:
            break

        if major not in majors:

            majors.append(
                major
            )

    return majors[:10]


# ============================================================
# DEGREE LEVELS
# ============================================================

def _estimate_degree_levels(
    record: Dict[str, Any],
) -> list:

    return [
        "Bachelor's",
        "Master's",
        "Doctorate",
    ]


# ============================================================
# UNIVERSITY TYPE
# ============================================================

def _estimate_university_type(
    record: Dict[str, Any],
) -> str:

    name = (
        record.get(
            "display_name"
        )
        or record.get(
            "name"
        )
        or ""
    )

    lower = name.lower()

    if "college" in lower:

        return "College"

    if "institute" in lower:

        return "Institute"

    if "polytechnic" in lower:

        return "Polytechnic"

    if "school" in lower:

        return "School"

    return "University"


# ============================================================
# ADMISSIONS
# ============================================================

def _estimate_admission(
    country: str,
) -> str:

    if country == "United States":

        return (
            "High school qualification, academic "
            "transcripts, English proficiency, and "
            "university-specific requirements."
        )

    if country == "United Kingdom":

        return (
            "Secondary school qualification, academic "
            "grades, English proficiency, and "
            "course-specific requirements."
        )

    if country == "Canada":

        return (
            "Secondary school qualification, transcripts, "
            "English or French proficiency, and "
            "program requirements."
        )

    if country == "Australia":

        return (
            "Secondary school qualification, academic "
            "results, English proficiency, and "
            "program-specific requirements."
        )

    if country == "Germany":

        return (
            "Recognized secondary qualification, academic "
            "records, language requirements, and "
            "program-specific requirements."
        )

    if country == "Japan":

        return (
            "Secondary qualification, academic records, "
            "language proficiency, and institution-specific "
            "entrance requirements."
        )

    return (
        "Recognized secondary qualification, academic "
        "transcripts, language proficiency, and "
        "program-specific requirements."
    )


# ============================================================
# APPLICATION DEADLINES
# ============================================================

def _estimate_deadline(
    country: str,
) -> str:

    if country == "United States":

        return (
            "Typically November–January "
            "for fall admission."
        )

    if country == "United Kingdom":

        return (
            "Typically January for most "
            "undergraduate applications."
        )

    if country == "Canada":

        return (
            "Typically January–March "
            "for fall admission."
        )

    if country == "Australia":

        return (
            "Typically several months before "
            "the semester begins."
        )

    if country == "Japan":

        return (
            "Typically late summer through winter "
            "depending on the institution."
        )

    return (
        "Typically several months before "
        "the academic term begins."
    )


# ============================================================
# DESCRIPTION
# ============================================================

def _description(
    record: Dict[str, Any],
    country: str,
) -> str:

    name = (
        record.get(
            "display_name"
        )
        or record.get(
            "name"
        )
        or "This university"
    )

    city = _city_name(
        record
    )

    if city and country:

        return (
            f"{name} is a higher-education institution "
            f"located in {city}, {country}. "
            "UniScout provides estimated information "
            "to help students compare study options."
        )

    if country:

        return (
            f"{name} is a higher-education institution "
            f"in {country}. UniScout provides estimated "
            "information to help students compare "
            "study options."
        )

    return (
        f"{name} is a higher-education institution. "
        "UniScout provides estimated information to "
        "help students compare study options."
    )


# ============================================================
# OPENALEX NORMALIZATION
# ============================================================

def normalize_openalex(
    record: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert one OpenAlex institution into the exact structure
    expected by database.upsert_university().
    """

    country = _country_name(
        record
    )

    country_code = _country_code(
        record
    )

    students = _estimate_students(
        record
    )

    international_students = (
        _estimate_international_students(
            students,
            country,
        )
    )

    tuition_min, tuition_max = (
        _tuition_range(
            country
        )
    )

    name = (
        record.get(
            "display_name"
        )
        or record.get(
            "name"
        )
        or "Unknown University"
    )

    website = _website(
        record
    )

    logo_url = (
        record.get(
            "image_url"
        )
        or record.get(
            "logo_url"
        )
        or ""
    )

    # OpenAlex's ID may be:
    #
    # https://openalex.org/I123456
    #
    # Keep it as the source ID because it gives us
    # a stable identifier for updating records later.

    source_id = _openalex_id(
        record
    )

    return {

        # ----------------------------------------------------
        # BASIC INFORMATION
        # ----------------------------------------------------

        "name": name,

        "country": (
            country
            or "Unknown"
        ),

        "country_code": (
            country_code
            or ""
        ),

        "city": _city_name(
            record
        ),

        "website": website,

        "logo_url": logo_url,

        "description": _description(
            record,
            country,
        ),

        # ----------------------------------------------------
        # ESTIMATED RANKING
        # ----------------------------------------------------

        "ranking": (
            record.get(
                "works_count"
            )
            or 0
        ),

        # ----------------------------------------------------
        # TUITION
        # ----------------------------------------------------

        "tuition_min": tuition_min,

        "tuition_max": tuition_max,

        "tuition_currency": (
            COUNTRY_CURRENCY.get(
                country,
                "USD",
            )
        ),

        "tuition_period": "year",

        # ----------------------------------------------------
        # UNIVERSITY TYPE
        # ----------------------------------------------------

        "university_type": (
            _estimate_university_type(
                record
            )
        ),

        # ----------------------------------------------------
        # STUDENTS
        # ----------------------------------------------------

        "student_count": students,

        "international_student_count": (
            international_students
        ),

        # ----------------------------------------------------
        # MAJORS
        # ----------------------------------------------------

        "majors": "|".join(
            _estimate_majors(
                record
            )
        ),

        # ----------------------------------------------------
        # DEGREES
        # ----------------------------------------------------

        "degree_levels": "|".join(
            _estimate_degree_levels(
                record
            )
        ),

        # ----------------------------------------------------
        # ADMISSIONS
        # ----------------------------------------------------

        "admission_requirements": (
            _estimate_admission(
                country
            )
        ),

        "application_deadline": (
            _estimate_deadline(
                country
            )
        ),

        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        "source": "OpenAlex",

        "source_id": source_id,

        # ----------------------------------------------------
        # UPDATE TIME
        # ----------------------------------------------------

        "last_updated": None,
    }


# ============================================================
# IMPORT RECORDS
# ============================================================

def import_records(
    records: Iterable[Dict[str, Any]],
) -> Dict[str, int]:
    """
    Save normalized university records.

    This function is called directly by openalex.py.
    """

    init_db()

    stats = {
        "new": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    for record in records:

        if not record:

            stats["skipped"] += 1

            continue

        try:

            normalized = normalize_openalex(
                record
            )

            if not normalized.get(
                "name"
            ):

                stats["skipped"] += 1

                continue

            result = upsert_university(
                normalized
            )

            # database.py returns whether the
            # record was inserted or updated.
            #
            # Support both styles just in case
            # the database implementation changes.

            if isinstance(
                result,
                str,
            ):

                if result.lower() == "new":

                    stats["new"] += 1

                else:

                    stats["updated"] += 1

            elif result is True:

                stats["new"] += 1

            else:

                stats["updated"] += 1

        except Exception as exc:

            stats["errors"] += 1

            logger.exception(
                "Failed importing university: %s",
                record.get(
                    "display_name"
                )
                or record.get(
                    "name"
                )
                or "Unknown",
            )

    return stats


# ============================================================
# LEGACY COMPATIBILITY
# ============================================================

def enrich_openalex_record(
    record: Dict[str, Any],
) -> Dict[str, Any]:

    """
    Backwards-compatible alias.

    Older code may call this function directly.
    """

    return normalize_openalex(
        record
    )


# ============================================================
# SIMPLE IMPORT API
# ============================================================

def import_openalex_records(
    records: Iterable[Dict[str, Any]],
) -> int:

    stats = import_records(
        records
    )

    return (
        stats["new"]
        + stats["updated"]
    )


# ============================================================
# LEGACY IMPORT API
# ============================================================

def _save_record(
    record: Dict[str, Any],
) -> bool:

    try:

        normalized = normalize_openalex(
            record
        )

        upsert_university(
            normalized
        )

        return True

    except Exception:

        logger.exception(
            "Failed to save university."
        )

        return False
