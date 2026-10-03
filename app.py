import os
import json
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse

from google import genai
from google.genai import types

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    abort,
)

from database import (
    init_db,
    search_universities,
    get_university,
    suggestions,
    list_distinct,
    get_db,
)


# ============================================================
# APP CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

app.config["JSON_SORT_KEYS"] = False


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

GEMINI_MODELS = [
    os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

# Remove duplicates while preserving the order above.
GEMINI_MODELS = list(dict.fromkeys(GEMINI_MODELS))

gemini_client = None

def get_gemini_client():
    global gemini_client

    if gemini_client is None:
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        gemini_client = genai.Client()

    return gemini_client

# ============================================================
# TEMPLATE FILTERS
# ============================================================

@app.template_filter("money")
def money(value):
    if value is None:
        return "Not available"

    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "Not available"


@app.template_filter("truncate")
def truncate_text(value, length=180):
    if not value:
        return ""

    value = str(value)

    if len(value) <= length:
        return value

    return value[:length].rstrip() + "..."


# ============================================================
# URL SAFETY
# ============================================================

def safe_url(url):
    if not url:
        return None

    try:
        parsed = urlparse(str(url))

        if parsed.scheme in ("http", "https") and parsed.netloc:
            return str(url)

    except Exception:
        pass

    return None


# ============================================================
# NUMBER PARSING
# ============================================================

def parse_num(name):
    raw = request.args.get(name, "").strip()

    if not raw:
        return None

    try:
        value = float(raw)

        if value < 0:
            return None

        if value > 1_000_000_000:
            return None

        return value

    except (ValueError, TypeError):
        return None


# ============================================================
# FILTERS
# ============================================================

def filter_context():

    country = request.args.get(
        "country",
        "",
    ).strip()

    city = request.args.get(
        "city",
        "",
    ).strip()

    major = request.args.get(
        "major",
        "",
    ).strip()

    min_tuition = parse_num(
        "min_tuition"
    )

    max_tuition = parse_num(
        "max_tuition"
    )

    university_type = request.args.get(
        "type",
        "",
    ).strip()

    min_ranking = parse_num(
        "min_ranking"
    )

    if (
        min_tuition is not None
        and max_tuition is not None
        and min_tuition > max_tuition
    ):
        min_tuition, max_tuition = (
            max_tuition,
            min_tuition,
        )

    return {
        "country": country,
        "city": city,
        "major": major,
        "min_tuition": min_tuition,
        "max_tuition": max_tuition,
        "university_type": university_type,
        "min_ranking": min_ranking,
    }


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

@app.before_request
def ensure_database():
    init_db()


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return (
        render_template(
            "error.html",
            code=404,
            message="We could not find that page.",
        ),
        404,
    )


@app.errorhandler(500)
def internal_error(error):

    return (
        render_template(
            "error.html",
            code=500,
            message="Something went wrong. Please try again.",
        ),
        500,
    )


# ============================================================
# HOME
# ============================================================

@app.route("/", endpoint="index")
def index():

    try:

        popular, _ = search_universities(
            limit=6
        )

        trending, _ = search_universities(
            limit=6,
            offset=6,
        )

        countries = list_distinct(
            "country"
        )[:12]

        majors = list_distinct(
            "majors"
        )[:12]

    except Exception:

        popular = []
        trending = []
        countries = []
        majors = []

    return render_template(
        "index.html",
        popular=popular,
        trending=trending,
        countries=countries,
        majors=majors,
    )


# ============================================================
# SEARCH
# ============================================================

@app.route(
    "/search",
    endpoint="search_page",
)
def search_page():

    q = request.args.get(
        "q",
        "",
    ).strip()

    filters = filter_context()

    try:

        results, total = search_universities(
            q=q,
            country=filters["country"],
            city=filters["city"],
            major=filters["major"],
            min_tuition=filters["min_tuition"],
            max_tuition=filters["max_tuition"],
            university_type=filters["university_type"],
            min_ranking=filters["min_ranking"],
        )

        countries = list_distinct(
            "country"
        )

        cities = list_distinct(
            "city",
            filters["country"],
        )

        majors = list_distinct(
            "majors"
        )

        types = list_distinct(
            "university_type"
        )

    except Exception:

        results = []
        total = 0
        countries = []
        cities = []
        majors = []
        types = []

    return render_template(
        "search.html",
        results=results,
        total=total,
        q=q,
        filters=filters,
        countries=countries,
        cities=cities,
        majors=majors,
        types=types,
    )


# ============================================================
# UNIVERSITY DETAILS
#
# Supports BOTH:
#
# url_for("university", uid=123)
#
# and:
#
# url_for("university", university_id=123)
# ============================================================

@app.route(
    "/university/<int:uid>",
    endpoint="university",
)
@app.route(
    "/university/<int:university_id>",
    endpoint="university",
)
def university(
    uid=None,
    university_id=None,
):

    actual_id = uid

    if actual_id is None:
        actual_id = university_id

    if actual_id is None:
        abort(404)

    try:

        university_data = get_university(
            actual_id
        )

    except Exception:

        abort(404)

    if not university_data:
        abort(404)

    university_data["safe_website"] = safe_url(
        university_data.get(
            "website"
        )
    )

    return render_template(
        "university.html",
        university=university_data,
    )


# ============================================================
# COMPARE
# ============================================================

@app.route(
    "/compare",
    endpoint="compare",
)
def compare():

    raw_ids = request.args.get(
        "ids",
        "",
    )

    ids = []

    for value in raw_ids.split(","):

        value = value.strip()

        if value.isdigit():

            university_id = int(value)

            if university_id > 0:
                ids.append(
                    university_id
                )

    ids = list(
        dict.fromkeys(ids)
    )

    ids = ids[:4]

    universities = []

    for university_id in ids:

        try:

            university_data = get_university(
                university_id
            )

        except Exception:

            university_data = None

        if university_data:

            university_data["safe_website"] = safe_url(
                university_data.get(
                    "website"
                )
            )

            universities.append(
                university_data
            )

    return render_template(
        "compare.html",
        universities=universities,
    )


# ============================================================
# FAVORITES
# ============================================================

@app.route(
    "/favorites",
    endpoint="favorites",
)
def favorites():

    return render_template(
        "favorites.html"
    )


# ============================================================
# MAJORS
# ============================================================

@app.route(
    "/majors",
    endpoint="majors_page",
)
def majors_page():

    try:

        majors = list_distinct(
            "majors"
        )

    except Exception:

        majors = []

    return render_template(
        "majors.html",
        majors=majors,
    )


# ============================================================
# COUNTRIES
# ============================================================

@app.route(
    "/countries",
    endpoint="countries",
)
def countries():

    try:

        country_list = list_distinct(
            "country"
        )

    except Exception:

        country_list = []

    data = []

    try:

        with get_db() as db:

            for country in country_list:

                count_row = db.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM universities
                    WHERE country = ?
                    """,
                    (country,),
                ).fetchone()

                count = (
                    count_row["count"]
                    if count_row
                    else 0
                )

                major_rows = db.execute(
                    """
                    SELECT majors
                    FROM universities
                    WHERE country = ?
                    AND majors IS NOT NULL
                    AND majors != ''
                    """,
                    (country,),
                ).fetchall()

                major_set = set()

                for row in major_rows:

                    raw = row["majors"] or ""

                    for major in raw.split("|"):

                        major = major.strip()

                        if major:
                            major_set.add(
                                major
                            )

                popular_majors = sorted(
                    major_set,
                    key=str.lower,
                )[:5]

                data.append(
                    {
                        "name": country,
                        "count": count,
                        "majors": popular_majors,
                    }
                )

    except Exception:

        data = []

    return render_template(
        "countries.html",
        countries=data,
    )


# ============================================================
# API - SUGGESTIONS
# ============================================================

@app.route(
    "/api/suggestions"
)
def api_suggestions():

    query = request.args.get(
        "q",
        "",
    ).strip()

    if len(query) < 2:
        return jsonify([])

    try:

        result = suggestions(
            query
        )

        return jsonify(result)

    except Exception:

        return jsonify([])


# ============================================================
# API - CITIES
# ============================================================

@app.route(
    "/api/cities"
)
def api_cities():

    country = request.args.get(
        "country",
        "",
    ).strip()

    try:

        cities = list_distinct(
            "city",
            country,
        )

        return jsonify(cities)

    except Exception:

        return jsonify([])


# ============================================================
# API - MAJORS
# ============================================================

@app.route(
    "/api/majors"
)
def api_majors():

    try:

        majors = list_distinct(
            "majors"
        )

        return jsonify(majors)

    except Exception:

        return jsonify([])


# ============================================================
# API - UNIVERSITIES
# ============================================================

@app.route(
    "/api/universities"
)
def api_universities():

    filters = filter_context()

    query = request.args.get(
        "q",
        "",
    ).strip()

    try:

        limit = int(
            request.args.get(
                "limit",
                60,
            )
        )

        offset = int(
            request.args.get(
                "offset",
                0,
            )
        )

    except ValueError:

        return jsonify(
            {
                "error": "Invalid pagination."
            }
        ), 400

    limit = max(
        1,
        min(
            limit,
            100,
        ),
    )

    offset = max(
        0,
        offset,
    )

    try:

        results, total = search_universities(
            q=query,
            country=filters["country"],
            city=filters["city"],
            major=filters["major"],
            min_tuition=filters["min_tuition"],
            max_tuition=filters["max_tuition"],
            university_type=filters["university_type"],
            min_ranking=filters["min_ranking"],
            limit=limit,
            offset=offset,
        )

        return jsonify(
            {
                "results": results,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    except Exception as error:

        print(
            "University API error:",
            error,
        )

        return jsonify(
            {
                "error": "Unable to search universities."
            }
        ), 500


# ============================================================
# API - SINGLE UNIVERSITY
# ============================================================

@app.route(
    "/api/university/<int:uid>"
)
def api_university(uid):

    try:

        university_data = get_university(
            uid
        )

    except Exception:

        return jsonify(
            {
                "error": "University not found."
            }
        ), 404

    if not university_data:

        return jsonify(
            {
                "error": "University not found."
            }
        ), 404

    return jsonify(
        university_data
    )


# ============================================================
# BUILD DATABASE CONTEXT FOR AI
# ============================================================

def build_db_context(
    message,
    ids=None,
):
    """
    Gives Gemma relevant UniScout data when the
    user is asking about universities.

    IMPORTANT:
    This does NOT restrict Gemma to database-only answers.

    Gemma can still answer:
        hello
        how are you
        explain AI
        what is Python
        help me write something
        etc.
    """

    results = []

    # --------------------------------------------------------
    # Search database using user's question
    # --------------------------------------------------------

    try:

        results, _ = search_universities(
            q=message,
            limit=12,
        )

    except Exception:

        results = []

    # --------------------------------------------------------
    # Add explicitly selected universities
    # --------------------------------------------------------

    if ids:

        for university_id in ids:

            try:

                university_data = get_university(
                    university_id
                )

            except Exception:

                university_data = None

            if not university_data:
                continue

            exists = any(
                str(x.get("id"))
                == str(university_id)
                for x in results
            )

            if not exists:

                results.append(
                    university_data
                )

    # --------------------------------------------------------
    # Limit context
    # --------------------------------------------------------

    results = results[:12]

    if not results:
        return ""

    # --------------------------------------------------------
    # Convert records to readable text
    # --------------------------------------------------------

    lines = []

    for university_data in results:

        tuition_min = university_data.get(
            "tuition_min"
        )

        tuition_max = university_data.get(
            "tuition_max"
        )

        tuition_currency = (
            university_data.get(
                "tuition_currency"
            )
            or "N/A"
        )

        tuition_period = (
            university_data.get(
                "tuition_period"
            )
            or "year"
        )

        ranking = university_data.get(
            "ranking"
        )

        majors = (
            university_data.get(
                "majors"
            )
            or "N/A"
        )

        university_type = (
            university_data.get(
                "university_type"
            )
            or "N/A"
        )

        student_count = (
            university_data.get(
                "student_count"
            )
            or "N/A"
        )

        international_count = (
            university_data.get(
                "international_student_count"
            )
            or "N/A"
        )

        lines.append(
            f"""
University ID: {university_data.get("id")}
University: {university_data.get("name") or "N/A"}
City: {university_data.get("city") or "N/A"}
Country: {university_data.get("country") or "N/A"}
Website: {university_data.get("website") or "N/A"}
Ranking: {ranking or "Not available"}
Tuition minimum: {tuition_min or "Not available"}
Tuition maximum: {tuition_max or "Not available"}
Tuition currency: {tuition_currency}
Tuition period: {tuition_period}
University type: {university_type}
Majors: {majors}
Degree levels: {university_data.get("degree_levels") or "Not available"}
Students: {student_count}
International students: {international_count}
Description: {university_data.get("description") or "Not available"}
Admission requirements: {university_data.get("admission_requirements") or "Not available"}
Application deadline: {university_data.get("application_deadline") or "Not available"}
Source: {university_data.get("source") or "Not available"}
""".strip()
        )

    return (
        "\n\n"
        "--- UNIVERSITY RECORD ---"
        "\n\n"
    ).join(lines)


# ============================================================
# GEMINI CHAT FUNCTION WITH AUTOMATIC FALLBACK
# ============================================================

def _error_code(error):
    """Best-effort extraction of the Gemini HTTP/API status code."""
    code = getattr(error, "code", None)
    if code is not None:
        try:
            return int(code)
        except (TypeError, ValueError):
            pass

    response = getattr(error, "response", None)
    response_code = getattr(response, "status_code", None)
    if response_code is not None:
        try:
            return int(response_code)
        except (TypeError, ValueError):
            pass

    text = str(error).lower()
    for candidate in (503, 502, 500, 429, 408, 504):
        if str(candidate) in text:
            return candidate

    return None


def _is_retryable_gemini_error(error):
    """Only retry/fallback for transient Gemini failures."""
    return _error_code(error) in {408, 429, 500, 502, 503, 504}


def ask_gemini(messages):
    """
    Send the conversation to Gemini with real status-code handling.

    The google-genai SDK already retries transient failures internally.
    If a request still fails with 408/429/500/502/503/504, UniScout
    moves to the next configured model. Non-transient errors such as
    invalid API keys or malformed requests are not retried.
    """

    system_prompt = ""
    contents = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content", "")

        if not content:
            continue

        if role == "system":
            system_prompt = str(content)
            continue

        gemini_role = "model" if role == "assistant" else "user"

        contents.append(
            types.Content(
                role=gemini_role,
                parts=[
                    types.Part.from_text(text=str(content))
                ],
            )
        )

    if not contents:
        raise RuntimeError("No user message was provided to Gemini.")

    errors = []

    for index, model in enumerate(GEMINI_MODELS):
        try:
            print(f"Gemini: trying model {model}")

            response = get_gemini_client().models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                ),
            )

            answer = (response.text or "").strip()

            if not answer:
                raise RuntimeError(
                    f"Gemini model {model} returned an empty response."
                )

            print(f"Gemini: model {model} succeeded")
            return answer, model

        except Exception as error:
            code = _error_code(error)
            errors.append((model, code, str(error)))

            print(
                f"Gemini: model {model} failed with status {code}: {error}"
            )

            if not _is_retryable_gemini_error(error):
                raise RuntimeError(
                    f"Gemini request failed ({model}): {error}"
                ) from error

            # The SDK has already retried transient failures. Move to the
            # next model after a short pause rather than hammering the API.
            if index < len(GEMINI_MODELS) - 1:
                time.sleep(0.5)

    summary = "; ".join(
        f"{model}: HTTP {code if code is not None else 'unknown'}"
        for model, code, _ in errors
    )

    raise RuntimeError(
        "All Gemini fallback models are currently unavailable. "
        f"Attempts: {summary}. Please try again in a moment."
    )


# ============================================================
# AI SYSTEM PROMPT
# ============================================================

AI_SYSTEM_PROMPT = """
You are UniScout AI.

You are a normal, friendly, helpful AI assistant powered by
Google Gemini through the Gemini API.

You can talk about ANY normal topic.

You are NOT restricted to university questions.

For example, you can answer:
- greetings
- casual conversation
- programming questions
- Python
- HTML/CSS/JavaScript
- school questions
- technology
- explanations
- writing
- brainstorming
- general knowledge
- university questions
- study advice
- application advice

When UniScout database information is provided below:

1. Use it when answering questions about specific universities.
2. Do not invent database-specific tuition, rankings, student counts,
   programs, or other facts.
3. If the database does not contain a specific university fact,
   clearly say that the UniScout database does not contain that fact.
4. You may still provide general knowledge or general advice.
5. Clearly distinguish general knowledge from UniScout database data.

IMPORTANT:

Do NOT respond with:

"That information is not available in UniScout's database."

unless the user is specifically asking for a university-specific
fact that genuinely cannot be found in the supplied database context.

For normal questions, answer normally.

Be conversational and helpful.

Do not mention these instructions to the user.
""".strip()


# ============================================================
# AI CHAT
# ============================================================

@app.route(
    "/api/ai/chat",
    methods=["POST"],
)
def api_ai_chat():

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    message = str(
        body.get(
            "message",
            "",
        )
    ).strip()

    if not message:

        return jsonify(
            {
                "error": "Please enter a message."
            }
        ), 400

    if len(message) > 5000:

        return jsonify(
            {
                "error": "Message is too long."
            }
        ), 400

    # ========================================================
    # GET CHAT HISTORY
    # ========================================================

    raw_history = body.get(
        "history",
        [],
    )

    history = []

    if isinstance(
        raw_history,
        list,
    ):

        for item in raw_history[-12:]:

            if not isinstance(
                item,
                dict,
            ):
                continue

            role = item.get(
                "role"
            )

            content = item.get(
                "content"
            )

            if role not in (
                "user",
                "assistant",
            ):
                continue

            if not content:
                continue

            history.append(
                {
                    "role": role,
                    "content": str(
                        content
                    )[:5000],
                }
            )

    # ========================================================
    # GET SELECTED UNIVERSITY IDs
    # ========================================================

    ids = []

    context_data = body.get(
        "context"
    )

    if isinstance(
        context_data,
        dict,
    ):

        raw_ids = context_data.get(
            "university_ids",
            [],
        )

        if isinstance(
            raw_ids,
            list,
        ):

            for value in raw_ids:

                try:

                    university_id = int(
                        value
                    )

                    if university_id > 0:
                        ids.append(
                            university_id
                        )

                except (
                    ValueError,
                    TypeError,
                ):

                    continue

    ids = list(
        dict.fromkeys(ids)
    )[:4]

    # ========================================================
    # DATABASE CONTEXT
    # ========================================================

    database_context = build_db_context(
        message,
        ids,
    )

    # ========================================================
    # BUILD USER MESSAGE
    # ========================================================

    if database_context:

        enhanced_message = f"""
The user asked:

{message}

Here is relevant information from the UniScout database.
Use this information for university-specific facts:

{database_context}

Answer the user's question naturally.
""".strip()

    else:

        enhanced_message = message

    # ========================================================
    # BUILD GEMINI MESSAGES
    # ========================================================

    messages = [
        {
            "role": "system",
            "content": AI_SYSTEM_PROMPT,
        }
    ]

    # Previous conversation
    messages.extend(
        history
    )

    # Current user message
    messages.append(
        {
            "role": "user",
            "content": enhanced_message,
        }
    )

    # ========================================================
    # ASK GEMINI
    # ========================================================

    try:

        response, model_used = ask_gemini(
            messages
        )

        if not response:

            response = (
                "I couldn't generate a response."
            )

        return jsonify(
            {
                "response": response,
                "model": model_used,
            }
        )

    except Exception as error:

        print(
            "AI ERROR:",
            error,
        )

        return jsonify(
            {
                "error": str(error)
            }
        ), 503


# ============================================================
# RECOMMENDATIONS
# ============================================================

@app.route(
    "/api/recommendations",
    methods=[
        "GET",
        "POST",
    ],
)
def recommendations():

    if request.method == "POST":

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

    else:

        data = request.args

    major = str(
        data.get(
            "major",
            "",
        )
    ).strip()

    country = str(
        data.get(
            "country",
            "",
        )
    ).strip()

    city = str(
        data.get(
            "city",
            "",
        )
    ).strip()

    university_type = str(
        data.get(
            "type",
            "",
        )
    ).strip()

    try:

        raw_min = str(
            data.get(
                "min_tuition",
                "",
            )
        ).strip()

        raw_max = str(
            data.get(
                "max_tuition",
                "",
            )
        ).strip()

        min_tuition = (
            float(raw_min)
            if raw_min
            else None
        )

        max_tuition = (
            float(raw_max)
            if raw_max
            else None
        )

    except (
        ValueError,
        TypeError,
    ):

        return jsonify(
            {
                "error": "Invalid tuition range."
            }
        ), 400

    if (
        min_tuition is not None
        and max_tuition is not None
        and min_tuition > max_tuition
    ):

        min_tuition, max_tuition = (
            max_tuition,
            min_tuition,
        )

    try:

        results, total = search_universities(
            major=major,
            country=country,
            city=city,
            min_tuition=min_tuition,
            max_tuition=max_tuition,
            university_type=university_type,
            limit=20,
        )

    except Exception:

        return jsonify(
            {
                "error": "Unable to generate recommendations."
            }
        ), 500

    return jsonify(
        {
            "results": results,
            "total": total,
        }
    )


# ============================================================
# DATABASE COUNTS
# ============================================================

def database_count():

    init_db()

    with get_db() as db:

        row = db.execute(
            """
            SELECT COUNT(*)
            FROM universities
            """
        ).fetchone()

        return row[0]


def openalex_count():

    init_db()

    with get_db() as db:

        row = db.execute(
            """
            SELECT COUNT(*)
            FROM universities
            WHERE source = ?
            """,
            ("OpenAlex",),
        ).fetchone()

        return row[0]


# ============================================================
# OPENALEX IMPORT
# ============================================================

def ensure_full_dataset():

    print()
    print("=" * 70)
    print("UniScout startup")
    print("=" * 70)

    try:

        init_db()

    except Exception as error:

        print(
            f"Database initialization failed: {error}"
        )

        return

    try:

        total = database_count()

    except Exception:

        total = 0

    try:

        openalex_total = openalex_count()

    except Exception:

        openalex_total = 0

    print(
        f"Database records: {total:,}"
    )

    print(
        f"OpenAlex records: {openalex_total:,}"
    )

    # Already imported
    if openalex_total >= 20_000:

        print()
        print(
            "OpenAlex dataset already exists."
        )

        print(
            f"Ready with {openalex_total:,} OpenAlex institutions."
        )

        print(
            "=" * 70
        )

        return

    print()
    print(
        "OpenAlex dataset is incomplete."
    )

    print(
        "Starting full OpenAlex education-institution import..."
    )

    print(
        "This may take several minutes."
    )

    print(
        "Please keep this terminal open."
    )

    print()

    try:

        from openalex import import_openalex

        mailto = os.environ.get(
            "OPENALEX_MAILTO"
        )

        result = import_openalex(
            mailto=mailto
        )

        final_count = openalex_count()

        print()
        print("=" * 70)
        print(
            "OpenAlex import finished."
        )

        print(
            f"OpenAlex institutions in database: {final_count:,}"
        )

        if isinstance(
            result,
            dict,
        ):

            print(
                f"Processed: {result.get('processed', 0):,}"
            )

            print(
                f"New: {result.get('new', 0):,}"
            )

            print(
                f"Updated: {result.get('updated', 0):,}"
            )

            print(
                f"Skipped: {result.get('skipped', 0):,}"
            )

            print(
                f"Errors: {result.get('errors', 0):,}"
            )

        print(
            "=" * 70
        )

    except Exception as error:

        print()
        print("=" * 70)

        print(
            "OpenAlex import failed."
        )

        print(
            f"Reason: {error}"
        )

        print()
        print(
            "Flask will still start."
        )

        print(
            "=" * 70
        )


# ============================================================
# START APPLICATION
# ============================================================

def start_app():

    init_db()

    # Import OpenAlex only when needed
    ensure_full_dataset()

    host = os.environ.get(
        "FLASK_HOST",
        "127.0.0.1",
    )

    port_raw = os.environ.get(
        "FLASK_PORT",
        "5000",
    )

    try:

        port = int(
            port_raw
        )

    except ValueError:

        port = 5000

    print()
    print("=" * 70)
    print("UniScout is running")
    print("=" * 70)

    print(
        f"http://{host}:{port}"
    )

    print(
        f"Gemini models: {', '.join(GEMINI_MODELS)}"
    )

    print("=" * 70)
    print()

    app.run(
        host=host,
        port=port,
        debug=False,
        threaded=True,
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    start_app()