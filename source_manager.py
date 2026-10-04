import logging
import time
from typing import Any, Dict, Iterable, Optional

from database import init_db, upsert_university

logger = logging.getLogger(__name__)

# Approximate annual tuition in USD.
# These are intentionally estimates, not official university fees.
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
    "South Africa": 4000,
}

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
    "Switzerland": "CHF",
    "Austria": "EUR",
    "Italy": "EUR",
    "Spain": "EUR",
    "Portugal": "EUR",
    "Ireland": "EUR",
    "Denmark": "DKK",
    "Sweden": "SEK",
    "Norway": "NOK",
    "Finland": "EUR",
    "Poland": "PLN",
    "Czechia": "CZK",
    "Czech Republic": "CZK",
    "Hungary": "HUF",
    "Romania": "RON",
    "Greece": "EUR",
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
    "South Africa": "ZAR",
}


def _first(value: Any, default: str = "") -> str:
    if isinstance(value, list):
        return str(value[0]) if value else default
    if value is None:
        return default
    return str(value)


def _country_name(record: Dict[str, Any]) -> str:
    country = record.get("country")

    if isinstance(country, dict):
        return (
            country.get("display_name")
            or country.get("name")
            or ""
        )

    return _first(country)


def _city_name(record: Dict[str, Any]) -> str:
    return (
        record.get("city")
        or record.get("city_name")
        or record.get("location_city")
        or ""
    )


def _website(record: Dict[str, Any]) -> str:
    return (
        record.get("website")
        or record.get("homepage")
        or record.get("homepage_url")
        or ""
    )


def _estimate_tuition(country: str) -> int:
    return COUNTRY_TUITION_USD.get(country, 7000)


def _estimate_students(record: Dict[str, Any]) -> int:
    """
    OpenAlex doesn't provide a reliable enrollment number for every
    institution, so generate a stable estimate from the institution id.
    """

    institution_id = str(record.get("id", ""))

    seed = sum(ord(c) for c in institution_id)

    values = [
        2500,
        5000,
        8000,
        12000,
        18000,
        25000,
        35000,
        50000,
        75000,
    ]

    return values[seed % len(values)]


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
        "Japan": 0.08,
        "South Korea": 0.08,
        "China": 0.05,
        "India": 0.05,
        "Indonesia": 0.04,
    }

    rate = rates.get(country, 0.08)

    return max(0, int(students * rate))


def _estimate_majors(record: Dict[str, Any]) -> list:
    """
    OpenAlex institutions don't expose a complete list of undergraduate
    majors. These are broad estimated fields suitable for UniScout's
    discovery interface.
    """

    concepts = record.get("x_concepts") or []

    names = []

    for concept in concepts:
        if isinstance(concept, dict):
            name = concept.get("display_name")
            if name:
                names.append(name)

    majors = []

    mapping = {
        "computer": "Computer Science",
        "software": "Software Engineering",
        "engineering": "Engineering",
        "biology": "Biology",
        "medicine": "Medicine",
        "business": "Business",
        "economics": "Economics",
        "psychology": "Psychology",
        "chemistry": "Chemistry",
        "physics": "Physics",
        "mathematics": "Mathematics",
        "law": "Law",
        "education": "Education",
        "political": "Political Science",
        "sociology": "Sociology",
        "history": "History",
        "arts": "Arts",
        "environment": "Environmental Science",
        "agriculture": "Agriculture",
        "communication": "Communications",
    }

    for name in names:
        lower = name.lower()

        for keyword, major in mapping.items():
            if keyword in lower and major not in majors:
                majors.append(major)

    defaults = [
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

    for major in defaults:
        if len(majors) >= 8:
            break

        if major not in majors:
            majors.append(major)

    return majors[:8]


def _estimate_degree_levels() -> list:
    return [
        "Bachelor's",
        "Master's",
        "Doctorate",
    ]


def _estimate_admission(country: str) -> str:
    if country == "United States":
        return "High school qualification, transcripts, English proficiency, and university-specific requirements."

    if country == "United Kingdom":
        return "Secondary school qualification, academic grades, English proficiency, and course-specific requirements."

    if country == "Canada":
        return "Secondary school qualification, transcripts, English/French proficiency, and program requirements."

    if country == "Australia":
        return "Secondary school qualification, academic results, English proficiency, and program-specific requirements."

    if country == "Germany":
        return "Recognized secondary qualification, academic records, language requirements, and program-specific requirements."

    return (
        "Recognized secondary qualification, academic transcripts, "
        "language proficiency, and program-specific requirements."
    )


def _estimate_deadline(country: str) -> str:
    if country == "United States":
        return "Typically November–January for fall admission."

    if country == "United Kingdom":
        return "Typically January for most undergraduate applications."

    if country == "Canada":
        return "Typically January–March for fall admission."

    if country == "Australia":
        return "Typically several months before the semester begins."

    if country == "Japan":
        return "Typically late summer through winter depending on the institution."

    return "Typically several months before the academic term begins."


def _description(record: Dict[str, Any], country: str) -> str:
    name = record.get("display_name") or record.get("name") or "This university"
    city = _city_name(record)

    if city:
        return (
            f"{name} is a higher-education institution located in "
            f"{city}, {country}. UniScout provides estimated information "
            f"to help students compare study options."
        )

    return (
        f"{name} is a higher-education institution in {country}. "
        "UniScout provides estimated information to help students "
        "compare study options."
    )


def enrich_openalex_record(record: Dict[str, Any]) -> Dict[str, Any]:
    country = _country_name(record)

    students = _estimate_students(record)
    international_students = _estimate_international_students(
        students,
        country,
    )

    return {
        "name": record.get("display_name") or record.get("name") or "Unknown University",
        "country": country or "Unknown",
        "city": _city_name(record),
        "website": _website(record),
        "logo_url": record.get("image_url") or record.get("logo_url") or "",

        "description": _description(record, country),

        "tuition": _estimate_tuition(country),
        "tuition_currency": COUNTRY_CURRENCY.get(country, "USD"),

        "students": students,
        "international_students": international_students,

        "majors": _estimate_majors(record),
        "degree_levels": _estimate_degree_levels(),

        "admission_requirements": _estimate_admission(country),
        "application_deadline": _estimate_deadline(country),

        # Estimated UniScout score, NOT an official ranking.
        "ranking": record.get("works_count", 0) or 0,

        # IMPORTANT:
        # Keep this EXACTLY "OpenAlex" because app.py searches for it.
        "source": "OpenAlex",
    }


def _save_record(record: Dict[str, Any]) -> bool:
    data = enrich_openalex_record(record)

    try:
        upsert_university(data)
        return True
    except Exception:
        logger.exception("Failed to save university: %s", data.get("name"))
        return False


def import_openalex_records(records: Iterable[Dict[str, Any]]) -> int:
    init_db()

    count = 0

    for record in records:
        if _save_record(record):
            count += 1

    logger.info("Imported %s universities.", count)

    return count


def import_openalex():
    """
    Uses the existing OpenAlex module in the project.
    """

    init_db()

    try:
        from openalex import fetch_universities
    except ImportError:
        logger.exception("Could not import fetch_universities from openalex.py")
        return 0

    total = 0

    try:
        records = fetch_universities()

        for record in records:
            if _save_record(record):
                total += 1

            if total % 100 == 0:
                logger.info("Imported %s universities...", total)

    except Exception:
        logger.exception("OpenAlex import failed.")

    logger.info("OpenAlex import complete: %s universities.", total)

    return total
