"""
UniScout OpenAlex institution importer.

Downloads education institutions from OpenAlex using cursor pagination
and passes each institution through source_manager.normalize_openalex()
before saving it with source_manager.import_records().

The normalized records are expected to contain:
- university name
- country
- country code
- city
- website
- logo
- description
- estimated ranking
- estimated tuition
- tuition currency
- tuition period
- university type
- estimated student count
- estimated international student count
- estimated majors
- degree levels
- admission requirements
- application deadline
- OpenAlex source ID
"""

import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

from source_manager import normalize_openalex, import_records


API = "https://api.openalex.org/institutions"

DEFAULT_PER_PAGE = 200

MAX_RETRIES = 8

REQUEST_TIMEOUT = 90

REQUEST_DELAY = 0.15


# ============================================================
# OPENALEX REQUEST
# ============================================================

def fetch_page(
    cursor="*",
    per_page=DEFAULT_PER_PAGE,
    mailto=None,
    timeout=REQUEST_TIMEOUT,
    retries=MAX_RETRIES,
):
    """
    Download one page of OpenAlex institutions.

    OpenAlex uses cursor pagination. The cursor returned by one
    request is used to request the next page.
    """

    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE

    per_page = min(
        max(per_page, 1),
        200,
    )

    params = {
        "filter": "type:education",
        "per-page": per_page,
        "cursor": cursor,
    }

    if mailto:
        params["mailto"] = mailto

    url = (
        API
        + "?"
        + urllib.parse.urlencode(params)
    )

    last_error = None

    for attempt in range(1, retries + 1):

        try:

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "UniScout/2.0 "
                        "(university discovery importer)"
                    ),
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response:

                raw = response.read()

                text = raw.decode(
                    "utf-8"
                )

                data = json.loads(
                    text
                )

                if not isinstance(
                    data,
                    dict,
                ):
                    raise ValueError(
                        "OpenAlex returned an invalid response."
                    )

                return data

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:

            last_error = exc

            if attempt >= retries:
                break

            delay = min(
                30,
                2 ** (attempt - 1),
            )

            print(
                f"  OpenAlex request failed "
                f"({attempt}/{retries}): {exc}",
                flush=True,
            )

            print(
                f"  Retrying in {delay}s...",
                flush=True,
            )

            time.sleep(
                delay
            )

    raise last_error


# ============================================================
# IMPORT
# ============================================================

def import_openalex(
    max_pages=None,
    per_page=DEFAULT_PER_PAGE,
    mailto=None,
):
    """
    Import the OpenAlex education institution dataset.

    Returns a dictionary containing:
        new
        updated
        skipped
        errors
    """

    cursor = "*"

    page = 0

    processed = 0

    totals = {
        "new": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    seen_cursors = set()

    reported_count = None

    print()

    print(
        "=" * 72
    )

    print(
        "UniScout: FULL OpenAlex education institution import"
    )

    print(
        "Endpoint:",
        API,
    )

    print(
        "Filter: type:education"
    )

    print(
        f"Batch size: {per_page}"
    )

    print(
        "Using cursor pagination."
    )

    print(
        "Estimated data will be generated during normalization."
    )

    print(
        "=" * 72
    )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    while True:

        page += 1

        print(
            f"\nDownloading page {page}...",
            flush=True,
        )

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        try:

            data = fetch_page(
                cursor=cursor,
                per_page=per_page,
                mailto=mailto,
            )

        except Exception as exc:

            totals["errors"] += 1

            print(
                f"  ERROR: page {page} failed "
                f"after retries: {exc}",
                flush=True,
            )

            print(
                "  Already imported records are safe.",
                flush=True,
            )

            print(
                "  Run the importer again to continue.",
                flush=True,
            )

            break

        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

        results = (
            data.get("results")
            or []
        )

        meta = (
            data.get("meta")
            or {}
        )

        # ----------------------------------------------------
        # TOTAL COUNT
        # ----------------------------------------------------

        if reported_count is None:

            reported_count = meta.get(
                "count"
            )

            if reported_count is not None:

                try:
                    display_count = int(
                        reported_count
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    display_count = reported_count

                print(
                    "OpenAlex reports "
                    f"{display_count:,} matching "
                    "education institutions.",
                    flush=True,
                )

        # ----------------------------------------------------
        # END OF DATASET
        # ----------------------------------------------------

        if not results:

            print(
                "  Reached the end of the dataset.",
                flush=True,
            )

            break

        # ----------------------------------------------------
        # NORMALIZE RECORDS
        # ----------------------------------------------------

        normalized_records = []

        for item in results:

            try:

                normalized = normalize_openalex(
                    item
                )

                if not normalized:

                    totals["skipped"] += 1

                    continue

                normalized_records.append(
                    normalized
                )

            except Exception as exc:

                totals["errors"] += 1

                institution_name = (
                    item.get(
                        "display_name"
                    )
                    or item.get(
                        "id"
                    )
                    or "Unknown institution"
                )

                print(
                    "  Normalization error:",
                    institution_name,
                    "|",
                    exc,
                    flush=True,
                )

        # ----------------------------------------------------
        # SAVE RECORDS
        # ----------------------------------------------------

        if normalized_records:

            try:

                stats = import_records(
                    normalized_records
                )

                if not isinstance(
                    stats,
                    dict,
                ):
                    stats = {}

                for key in totals:

                    value = stats.get(
                        key,
                        0,
                    )

                    try:
                        totals[key] += int(
                            value
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

            except Exception as exc:

                totals["errors"] += len(
                    normalized_records
                )

                print(
                    "  Database batch error:",
                    exc,
                    flush=True,
                )

        processed += len(
            results
        )

        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------

        print(
            f"  Processed: {processed:,} | "
            f"New: {totals['new']:,} | "
            f"Updated: {totals['updated']:,} | "
            f"Skipped: {totals['skipped']:,} | "
            f"Errors: {totals['errors']:,}",
            flush=True,
        )

        # ----------------------------------------------------
        # NEXT CURSOR
        # ----------------------------------------------------

        next_cursor = meta.get(
            "next_cursor"
        )

        if not next_cursor:

            print(
                "  OpenAlex returned no next_cursor.",
                flush=True,
            )

            print(
                "  Import complete.",
                flush=True,
            )

            break

        # ----------------------------------------------------
        # PROTECT AGAINST REPEATED CURSOR
        # ----------------------------------------------------

        if (
            next_cursor in seen_cursors
            or next_cursor == cursor
        ):

            print(
                "  ERROR: OpenAlex returned "
                "a repeated cursor.",
                flush=True,
            )

            print(
                "  Stopping safely.",
                flush=True,
            )

            totals["errors"] += 1

            break

        seen_cursors.add(
            next_cursor
        )

        cursor = next_cursor

        # ----------------------------------------------------
        # OPTIONAL PAGE LIMIT
        # ----------------------------------------------------

        if (
            max_pages
            and page >= max_pages
        ):

            print(
                f"  Stopping after "
                f"{max_pages} pages.",
                flush=True,
            )

            break

        # ----------------------------------------------------
        # SMALL DELAY
        # ----------------------------------------------------

        time.sleep(
            REQUEST_DELAY
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()

    print(
        "=" * 72
    )

    if reported_count is not None:

        try:

            print(
                "OpenAlex reported total: "
                f"{int(reported_count):,}"
            )

        except (
            TypeError,
            ValueError,
        ):

            print(
                "OpenAlex reported total:",
                reported_count,
            )

    else:

        print(
            "OpenAlex reported total: unknown"
        )

    print(
        f"Institutions processed: {processed:,}"
    )

    print(
        f"New institutions: {totals['new']:,}"
    )

    print(
        f"Updated institutions: {totals['updated']:,}"
    )

    print(
        f"Skipped: {totals['skipped']:,}"
    )

    print(
        f"Errors: {totals['errors']:,}"
    )

    print(
        "=" * 72
    )

    return totals


# ============================================================
# COMMAND LINE
# ============================================================

if __name__ == "__main__":

    import_openalex(
        mailto=os.environ.get(
            "OPENALEX_MAILTO"
        )
    )
