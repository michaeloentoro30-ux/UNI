
"""
UniScout source manager + data enrichment.

This module keeps the existing OpenAlex importer compatible while adding
estimated university data for records that OpenAlex does not provide.

IMPORTANT:
- Tuition, student counts, majors, admissions and deadlines are ESTIMATES.
- They are generated from country-level education patterns plus OpenAlex
  institution metadata. They are not official university fee schedules.
- Existing non-empty values are not available to this function, so this
  module is intended for a fresh OpenAlex import.
"""

from datetime import datetime, timezone
import hashlib
import math
import re

from database import upsert_university


COUNTRY_PROFILES = {
    "United States": {
        "currency": "USD", "tuition": (10000, 55000), "intl": 0.10,
        "deadline": "Usually Nov–Apr for the following academic year; varies by university and program.",
        "requirements": "Typical requirements: secondary-school or prior-degree transcripts, proof of English for many international applicants, recommendation letters and a personal statement; SAT/ACT or other tests may be required by some institutions.",
    },
    "United Kingdom": {
        "currency": "GBP", "tuition": (11000, 35000), "intl": 0.24,
        "deadline": "Common undergraduate cycle: applications open in September and the main equal-consideration deadline is usually January; Oxford/Cambridge and many medicine courses use an October deadline.",
        "requirements": "Typical requirements: academic qualifications, English-language evidence for international applicants, personal statement and references. Course-specific tests or portfolios may apply.",
    },
    "Canada": {
        "currency": "CAD", "tuition": (15000, 45000), "intl": 0.20,
        "deadline": "Commonly Oct–Mar for September entry; exact deadlines vary by institution and program.",
        "requirements": "Typical requirements: academic transcripts, proof of English or French where required, identification documents and program-specific prerequisites. Some programs require portfolios or tests.",
    },
    "Australia": {
        "currency": "AUD", "tuition": (20000, 50000), "intl": 0.30,
        "deadline": "Common intakes are around February and July; application deadlines vary by institution and program.",
        "requirements": "Typical requirements: academic transcripts, English-language evidence, passport/identity documents and program-specific prerequisites. Some programs require portfolios or interviews.",
    },
    "New Zealand": {
        "currency": "NZD", "tuition": (18000, 45000), "intl": 0.22,
        "deadline": "Common intakes are February and July; exact deadlines vary by university and program.",
        "requirements": "Typical requirements: academic transcripts, English-language evidence for many international applicants and program-specific prerequisites.",
    },
    "Germany": {
        "currency": "EUR", "tuition": (0, 12000), "intl": 0.16,
        "deadline": "Common application windows are roughly May–July for winter entry and Dec–Jan for summer entry, but university/program deadlines differ.",
        "requirements": "Typical requirements: recognized prior qualifications, transcripts, language proof (German or English depending on program), and program-specific documents. International applicants may need visa and credential-verification documents.",
    },
    "France": {
        "currency": "EUR", "tuition": (300, 18000), "intl": 0.15,
        "deadline": "Many undergraduate applications follow national/centralized timelines, commonly beginning in the preceding academic year; master's deadlines vary by institution.",
        "requirements": "Typical requirements: academic records, language evidence, identity documents and program-specific materials. Public and private institutions can have substantially different requirements and fees.",
    },
    "Netherlands": {
        "currency": "EUR", "tuition": (2500, 25000), "intl": 0.20,
        "deadline": "Many programs use deadlines between January and May for September entry; numerus-fixus programs often close earlier.",
        "requirements": "Typical requirements: recognized prior qualification, transcripts, English-language proof for English-taught programs and program-specific prerequisites.",
    },
    "Belgium": {
        "currency": "EUR", "tuition": (1000, 10000), "intl": 0.18,
        "deadline": "Often spring or early summer for the following academic year, but deadlines vary substantially by institution and applicant nationality.",
        "requirements": "Typical requirements: recognized academic qualification, transcripts, language proof and program-specific prerequisites.",
    },
    "Austria": {
        "currency": "EUR", "tuition": (0, 8000), "intl": 0.18,
        "deadline": "Often several months before the semester begins; exact deadlines depend on the institution and program.",
        "requirements": "Typical requirements: recognized qualification, transcripts, language evidence and identity/immigration documents where applicable.",
    },
    "Switzerland": {
        "currency": "CHF", "tuition": (1500, 30000), "intl": 0.25,
        "deadline": "Commonly winter/spring deadlines for autumn entry; exact dates vary by institution.",
        "requirements": "Typical requirements: academic transcripts, language proof and program-specific prerequisites. Some institutions have separate international deadlines.",
    },
    "Italy": {
        "currency": "EUR", "tuition": (500, 20000), "intl": 0.10,
        "deadline": "Often spring to summer for autumn entry, with earlier deadlines for some international and limited-enrollment programs.",
        "requirements": "Typical requirements: academic qualification, transcripts, language evidence, identity documents and program-specific prerequisites.",
    },
    "Spain": {
        "currency": "EUR", "tuition": (800, 20000), "intl": 0.08,
        "deadline": "Commonly spring to early summer for autumn entry; some international and private programs accept applications earlier or later.",
        "requirements": "Typical requirements: academic records, language proof and program-specific admission documents.",
    },
    "Portugal": {
        "currency": "EUR", "tuition": (1000, 12000), "intl": 0.12,
        "deadline": "Usually spring to summer for autumn entry, varying by institution and program.",
        "requirements": "Typical requirements: academic qualification, transcripts, language evidence and identification documents.",
    },
    "Ireland": {
        "currency": "EUR", "tuition": (3000, 30000), "intl": 0.25,
        "deadline": "Many undergraduate applications use a centralized cycle with a February equal-consideration deadline; international and postgraduate deadlines vary.",
        "requirements": "Typical requirements: academic records, English-language evidence, references/personal statement where applicable and program-specific prerequisites.",
    },
    "Sweden": {
        "currency": "SEK", "tuition": (0, 220000), "intl": 0.15,
        "deadline": "Autumn applications commonly close in January; exact dates depend on the national application cycle and program.",
        "requirements": "Typical requirements: academic qualification, transcripts, English-language evidence for many international programs and program-specific prerequisites.",
    },
    "Denmark": {
        "currency": "DKK", "tuition": (0, 135000), "intl": 0.12,
        "deadline": "Often January–March for autumn entry; exact deadlines vary by program and applicant group.",
        "requirements": "Typical requirements: recognized qualification, transcripts, language proof and program-specific prerequisites.",
    },
    "Finland": {
        "currency": "EUR", "tuition": (0, 20000), "intl": 0.12,
        "deadline": "Many English-taught programs have a joint application period around January; some programs use separate deadlines.",
        "requirements": "Typical requirements: academic records, language evidence, identity documents and program-specific criteria.",
    },
    "Norway": {
        "currency": "NOK", "tuition": (0, 350000), "intl": 0.12,
        "deadline": "Often December–March for autumn entry; deadlines vary by institution and applicant category.",
        "requirements": "Typical requirements: recognized qualification, transcripts, language proof and program-specific prerequisites.",
    },
    "Poland": {
        "currency": "PLN", "tuition": (8000, 40000), "intl": 0.10,
        "deadline": "Often spring through summer for autumn entry; some programs have earlier deadlines.",
        "requirements": "Typical requirements: academic records, language evidence and program-specific documents.",
    },
    "Czechia": {
        "currency": "EUR", "tuition": (0, 10000), "intl": 0.08,
        "deadline": "Many programs close applications in winter or early spring for the following academic year.",
        "requirements": "Typical requirements: prior qualification, transcripts, language proof and sometimes entrance examinations.",
    },
    "Hungary": {
        "currency": "EUR", "tuition": (3000, 12000), "intl": 0.15,
        "deadline": "Often February–June for autumn entry, with scholarship schemes sometimes closing earlier.",
        "requirements": "Typical requirements: transcripts, language proof, identity documents and program-specific prerequisites.",
    },
    "Greece": {
        "currency": "EUR", "tuition": (0, 10000), "intl": 0.08,
        "deadline": "Usually spring/summer for autumn entry, varying by institution and program.",
        "requirements": "Typical requirements: academic records, language proof and program-specific documentation.",
    },
    "Romania": {
        "currency": "EUR", "tuition": (2000, 10000), "intl": 0.10,
        "deadline": "Often spring through summer for autumn entry.",
        "requirements": "Typical requirements: academic records, language proof and program-specific documents.",
    },
    "Bulgaria": {
        "currency": "EUR", "tuition": (2000, 10000), "intl": 0.10,
        "deadline": "Usually spring through summer for autumn entry.",
        "requirements": "Typical requirements: recognized qualification, transcripts and language/entrance requirements where applicable.",
    },
    "Croatia": {
        "currency": "EUR", "tuition": (1000, 8000), "intl": 0.10,
        "deadline": "Often spring/summer for autumn entry.",
        "requirements": "Typical requirements: prior qualification, transcripts, language evidence and program-specific requirements.",
    },
    "Slovenia": {
        "currency": "EUR", "tuition": (0, 8000), "intl": 0.10,
        "deadline": "Often February–May for autumn entry.",
        "requirements": "Typical requirements: academic records, language evidence and program-specific documents.",
    },
    "Slovakia": {
        "currency": "EUR", "tuition": (0, 10000), "intl": 0.08,
        "deadline": "Often February–May for autumn entry.",
        "requirements": "Typical requirements: academic records, language evidence and program-specific documents.",
    },
    "Estonia": {
        "currency": "EUR", "tuition": (1500, 7500), "intl": 0.20,
        "deadline": "Many international programs close between January and April for autumn entry.",
        "requirements": "Typical requirements: academic records, language proof and program-specific prerequisites.",
    },
    "Lithuania": {
        "currency": "EUR", "tuition": (2500, 9000), "intl": 0.15,
        "deadline": "Often spring through early summer for autumn entry.",
        "requirements": "Typical requirements: academic records, language evidence and program-specific documents.",
    },
    "Latvia": {
        "currency": "EUR", "tuition": (2500, 11000), "intl": 0.15,
        "deadline": "Often spring through summer for autumn entry.",
        "requirements": "Typical requirements: academic records, language evidence and program-specific prerequisites.",
    },
    "Iceland": {
        "currency": "EUR", "tuition": (0, 8000), "intl": 0.15,
        "deadline": "Often winter/spring for autumn entry.",
        "requirements": "Typical requirements: academic qualification, transcripts and language evidence.",
    },
    "Japan": {
        "currency": "JPY", "tuition": (535800, 2500000), "intl": 0.10,
        "deadline": "Many universities recruit for spring entry, with applications often months in advance; some programs also offer autumn entry.",
        "requirements": "Typical requirements: academic transcripts, proof of completed secondary/previous degree, language proficiency and sometimes entrance examinations. EJU may apply to some international applicants.",
    },
    "South Korea": {
        "currency": "KRW", "tuition": (3000000, 12000000), "intl": 0.08,
        "deadline": "Common admissions occur for March and September entry; applications are usually several months before the semester.",
        "requirements": "Typical requirements: academic records, passport/identity documents, language proof and sometimes entrance or portfolio requirements.",
    },
    "China": {
        "currency": "CNY", "tuition": (15000, 60000), "intl": 0.08,
        "deadline": "Many international applications run from winter through late spring for autumn entry.",
        "requirements": "Typical requirements: academic transcripts, passport, language evidence and program-specific materials; some programs require entrance tests.",
    },
    "Hong Kong": {
        "currency": "HKD", "tuition": (90000, 180000), "intl": 0.20,
        "deadline": "Many undergraduate applications open in autumn and close between December and spring.",
        "requirements": "Typical requirements: academic qualifications, English-language proof and program-specific documents.",
    },
    "Singapore": {
        "currency": "SGD", "tuition": (10000, 50000), "intl": 0.25,
        "deadline": "Most undergraduate applications for the next academic year are submitted months in advance, commonly between autumn and early spring.",
        "requirements": "Typical requirements: academic records, English-language evidence where needed and program-specific prerequisites.",
    },
    "India": {
        "currency": "INR", "tuition": (50000, 600000), "intl": 0.05,
        "deadline": "Many undergraduate admissions occur in spring/summer for the academic year; competitive programs can have earlier test/application deadlines.",
        "requirements": "Typical requirements: school or prior-degree records, entrance examinations for many competitive programs and identity documents.",
    },
    "Indonesia": {
        "currency": "IDR", "tuition": (10000000, 80000000), "intl": 0.04,
        "deadline": "Common intake periods are around mid-year, with some universities offering multiple intakes.",
        "requirements": "Typical requirements: academic transcripts, identity documents, language evidence and program-specific requirements; entrance tests may apply.",
    },
    "Malaysia": {
        "currency": "MYR", "tuition": (10000, 60000), "intl": 0.25,
        "deadline": "Many institutions offer several intakes, commonly around January, May and September.",
        "requirements": "Typical requirements: academic records, passport, English-language evidence and program-specific prerequisites.",
    },
    "Thailand": {
        "currency": "THB", "tuition": (50000, 300000), "intl": 0.08,
        "deadline": "Common admissions are concentrated around the first half of the year for the academic cycle.",
        "requirements": "Typical requirements: academic records, identity documents, language evidence and program-specific requirements.",
    },
    "Philippines": {
        "currency": "PHP", "tuition": (40000, 250000), "intl": 0.04,
        "deadline": "Often several months before the academic year begins; exact deadlines vary.",
        "requirements": "Typical requirements: academic records, entrance examination where applicable and identity documents.",
    },
    "Vietnam": {
        "currency": "VND", "tuition": (20000000, 150000000), "intl": 0.05,
        "deadline": "Often spring through summer for the main academic year.",
        "requirements": "Typical requirements: academic records, passport/identity documents, language proof and program-specific materials.",
    },
    "Taiwan": {
        "currency": "TWD", "tuition": (60000, 180000), "intl": 0.10,
        "deadline": "Spring and autumn admission cycles are common; applications are usually several months before entry.",
        "requirements": "Typical requirements: transcripts, language evidence, passport and program-specific requirements.",
    },
    "United Arab Emirates": {
        "currency": "AED", "tuition": (30000, 120000), "intl": 0.75,
        "deadline": "Many universities have multiple intakes, commonly autumn and spring.",
        "requirements": "Typical requirements: academic records, passport, English-language evidence and program-specific documents.",
    },
    "Saudi Arabia": {
        "currency": "SAR", "tuition": (0, 100000), "intl": 0.10,
        "deadline": "Usually several months before the academic year; dates vary by university.",
        "requirements": "Typical requirements: academic records, identification documents and language/entrance requirements where applicable.",
    },
    "Turkey": {
        "currency": "TRY", "tuition": (20000, 250000), "intl": 0.08,
        "deadline": "Often spring through summer for autumn entry, with earlier deadlines for some programs.",
        "requirements": "Typical requirements: academic records, passport, language proof and program-specific requirements.",
    },
    "South Africa": {
        "currency": "ZAR", "tuition": (30000, 180000), "intl": 0.08,
        "deadline": "Often several months before the academic year, with many undergraduate applications closing in the second half of the preceding year.",
        "requirements": "Typical requirements: academic records, proof of language proficiency and program-specific prerequisites.",
    },
    "Brazil": {
        "currency": "BRL", "tuition": (0, 60000), "intl": 0.03,
        "deadline": "Often aligned with semester admissions; private institutions may have multiple intakes.",
        "requirements": "Typical requirements: academic records, identity documents and entrance examination or selection process where applicable.",
    },
    "Mexico": {
        "currency": "MXN", "tuition": (20000, 180000), "intl": 0.05,
        "deadline": "Often several months before semester start; private institutions may have multiple intakes.",
        "requirements": "Typical requirements: academic records, identity documents and program-specific entrance requirements.",
    },
    "Argentina": {
        "currency": "ARS", "tuition": (0, 5000000), "intl": 0.03,
        "deadline": "Commonly before the start of the academic year; exact dates vary.",
        "requirements": "Typical requirements: academic records, identification and program-specific admission documents.",
    },
    "Chile": {
        "currency": "CLP", "tuition": (1500000, 8000000), "intl": 0.05,
        "deadline": "Usually late in the preceding year or early in the academic year.",
        "requirements": "Typical requirements: academic records, identity documents and program-specific requirements.",
    },
    "Colombia": {
        "currency": "COP", "tuition": (3000000, 30000000), "intl": 0.04,
        "deadline": "Often several months before semester start.",
        "requirements": "Typical requirements: academic records, identity documents and program-specific entrance requirements.",
    },
}

DEFAULT_PROFILE = {
    "currency": "USD",
    "tuition": (3000, 30000),
    "intl": 0.08,
    "deadline": "Usually several months before the start of the academic term; exact dates vary by university and program.",
    "requirements": "Typical requirements: academic transcripts, proof of language proficiency where applicable, identification documents and program-specific prerequisites.",
}


def clean_text(value):
    return (value or "").strip() or None


def _profile(country):
    return COUNTRY_PROFILES.get(country, DEFAULT_PROFILE)


def _stable_int(text, minimum, maximum):
    digest = hashlib.sha256(str(text).encode("utf-8")).hexdigest()
    number = int(digest[:16], 16)
    return minimum + (number % (maximum - minimum + 1))


def _detect_major_focus(name):
    text = (name or "").lower()
    groups = []

    keyword_groups = [
        (("technology", "technological", "informatics", "computer", "computing",
          "software", "digital", "it institute", "polytechnic"), "Computer Science"),
        (("engineering", "institute of technology", "technical", "polytechnic"),
         "Engineering"),
        (("business", "commerce", "management", "finance", "accounting"),
         "Business & Management"),
        (("economics", "economic"), "Economics"),
        (("medical", "medicine", "health", "nursing", "dental", "pharmacy"),
         "Medicine & Health Sciences"),
        (("science", "scientific", "natural"), "Natural Sciences"),
        (("social science", "sociology", "psychology"), "Social Sciences"),
        (("arts", "humanities", "liberal arts", "music", "fine arts"),
         "Arts & Humanities"),
        (("law", "legal"), "Law"),
        (("education", "teacher", "pedagog"), "Education"),
        (("architecture", "design"), "Architecture"),
        (("environment", "agriculture", "forestry", "earth", "ecology"),
         "Environmental Sciences"),
    ]

    for keywords, major in keyword_groups:
        if any(keyword in text for keyword in keywords):
            groups.append(major)

    return groups


def estimate_majors(name, country):
    focused = _detect_major_focus(name)

    baseline = [
        "Computer Science",
        "Engineering",
        "Business & Management",
        "Economics",
        "Social Sciences",
        "Arts & Humanities",
        "Natural Sciences",
    ]

    if country in {"India", "Indonesia", "Malaysia", "Thailand", "Philippines", "Vietnam"}:
        baseline.append("Education")

    if country in {"Germany", "France", "Italy", "Spain", "Netherlands", "Sweden", "Switzerland"}:
        baseline.append("Environmental Sciences")

    if country in {"United States", "Canada", "United Kingdom", "Australia"}:
        baseline.extend(["Law", "Medicine & Health Sciences"])

    result = []
    for major in focused + baseline:
        if major not in result:
            result.append(major)

    return " | ".join(result[:10])


def estimate_degree_levels(name):
    text = (name or "").lower()

    if any(x in text for x in ("community college", "college of further", "junior college")):
        return "Bachelor"

    return "Bachelor | Master | Doctorate"


def estimate_type(name):
    text = (name or "").lower()

    if any(x in text for x in ("private", "international school", "business school")):
        return "Private University / Higher Education Institution"

    if any(x in text for x in ("national", "state university", "public university", "federal university")):
        return "Public University"

    if any(x in text for x in ("polytechnic", "institute of technology", "technical university")):
        return "University / Polytechnic"

    return "University"


def estimate_student_count(item, name):
    """
    OpenAlex does not provide a universal enrollment field for institutions.
    Publication volume is therefore used only as a weak size signal.
    """

    works = item.get("works_count") or 0
    cited = item.get("cited_by_count") or 0

    try:
        works = max(0, int(works))
    except (TypeError, ValueError):
        works = 0

    try:
        cited = max(0, int(cited))
    except (TypeError, ValueError):
        cited = 0

    signal = math.log1p(works) * 350 + math.log1p(cited) * 25
    baseline = _stable_int(name, 3500, 18000)
    estimate = int(max(1000, min(120000, baseline + signal)))

    if any(word in (name or "").lower() for word in ("community college", "college")):
        estimate = min(estimate, 30000)

    return estimate


def estimate_international_count(student_count, country, name):
    ratio = _profile(country)["intl"]
    adjustment = _stable_int(name, -20, 20) / 1000.0
    ratio = max(0.01, min(0.65, ratio + adjustment))
    return max(50, int(student_count * ratio))


def estimate_ranking(item, name, country):
    """
    Produces a rough UniScout discovery rank from OpenAlex research signals.

    This is NOT QS, THE, ARWU, US News, or any official ranking.
    """

    works = item.get("works_count") or 0
    cited = item.get("cited_by_count") or 0
    stats = item.get("summary_stats") or {}
    mean_cited = stats.get("2yr_mean_citedness") or 0

    try:
        works = max(0, float(works))
    except (TypeError, ValueError):
        works = 0

    try:
        cited = max(0, float(cited))
    except (TypeError, ValueError):
        cited = 0

    try:
        mean_cited = max(0, float(mean_cited))
    except (TypeError, ValueError):
        mean_cited = 0

    research_score = (
        math.log1p(works) * 7.0
        + math.log1p(cited) * 5.0
        + min(mean_cited, 30.0) * 2.0
    )

    country_bonus = {
        "United States": 180,
        "United Kingdom": 160,
        "Germany": 120,
        "Canada": 110,
        "Australia": 100,
        "France": 100,
        "Netherlands": 95,
        "Japan": 90,
        "Switzerland": 90,
        "Sweden": 85,
        "Singapore": 80,
        "South Korea": 75,
    }.get(country, 20)

    rank = int(5200 - research_score * 35 - country_bonus)
    rank = max(1, min(5000, rank))

    rank += _stable_int(name, -15, 15)

    return max(1, min(5000, rank))


def estimate_description(name, city, country, majors, university_type):
    location = ", ".join([x for x in (city, country) if x]) or "its region"
    major_list = majors.split(" | ")[:5]

    if len(major_list) > 1:
        focus = ", ".join(major_list[:-1]) + " and " + major_list[-1]
    else:
        focus = major_list[0]

    return (
        f"{name} is a {university_type.lower()} located in {location}. "
        f"UniScout estimates that its academic offering includes areas such as "
        f"{focus}. University-specific details can vary by campus, faculty and program. "
        f"Tuition, enrollment and ranking figures shown by UniScout are estimates "
        f"when official institution-level data is unavailable."
    )


def enrich_openalex_record(item):
    """
    Convert one raw OpenAlex institution into the UniScout schema.
    """

    geo = item.get("geo") or {}

    country = clean_text(geo.get("country"))
    country_code = clean_text(geo.get("country_code"))
    city = clean_text(geo.get("city"))

    name = clean_text(
        item.get("display_name") or item.get("name")
    ) or "Unnamed institution"

    website = clean_text(
        item.get("homepage_url") or item.get("website_url")
    )

    ids = item.get("ids") or {}
    source_id = str(
        item.get("id") or ids.get("openalex") or ""
    )

    profile = _profile(country)
    tuition_min, tuition_max = profile["tuition"]

    majors = estimate_majors(name, country)
    degree_levels = estimate_degree_levels(name)
    university_type = estimate_type(name)

    student_count = estimate_student_count(
        item,
        name,
    )

    international_count = estimate_international_count(
        student_count,
        country,
        name,
    )

    ranking = estimate_ranking(
        item,
        name,
        country,
    )

    description = estimate_description(
        name=name,
        city=city,
        country=country,
        majors=majors,
        university_type=university_type,
    )

    return {
        "name": name,
        "country": country,
        "country_code": country_code,
        "city": city,
        "website": website,
        "logo_url": clean_text(item.get("image_url")),

        "description": description,
        "ranking": ranking,

        "tuition_min": tuition_min,
        "tuition_max": tuition_max,
        "tuition_currency": profile["currency"],
        "tuition_period": "year",

        "university_type": university_type,

        "student_count": student_count,
        "international_student_count": international_count,

        "majors": majors,
        "degree_levels": degree_levels,

        "admission_requirements": profile["requirements"],
        "application_deadline": profile["deadline"],

        "source": "OpenAlex + UniScout estimates",
        "source_id": source_id,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def normalize_openalex(item):
    return enrich_openalex_record(item)


def import_records(records):
    stats = {
        "new": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    for record in records:
        try:
            status, _ = upsert_university(record)
            stats[status] += 1
        except Exception as exc:
            stats["errors"] += 1
            print("Import error:", exc)

    return stats
