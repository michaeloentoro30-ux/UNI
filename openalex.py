"""Reliable OpenAlex institution importer used by app.py on first startup."""
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from source_manager import normalize_openalex, import_records

API = "https://api.openalex.org/institutions"
DEFAULT_PER_PAGE = 200


def fetch_page(cursor="*", per_page=DEFAULT_PER_PAGE, mailto=None, timeout=90, retries=8):
    params = {
        "filter": "type:education",
        "per-page": min(max(int(per_page), 1), 200),
        "cursor": cursor,
    }
    if mailto:
        params["mailto"] = mailto
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "UniScout/2.0 (university discovery importer)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < retries:
                delay = min(30, 2 ** (attempt - 1))
                print(f"  Request failed ({attempt}/{retries}): {exc}. Retrying in {delay}s...")
                time.sleep(delay)
    raise last


def import_openalex(max_pages=None, per_page=DEFAULT_PER_PAGE, mailto=None):
    """Import the complete OpenAlex education institution dataset using cursor pagination."""
    cursor = "*"
    page = 0
    processed = 0
    totals = {"new": 0, "updated": 0, "skipped": 0, "errors": 0}
    seen_cursors = set()
    reported_count = None

    print("=" * 72)
    print("UniScout: FULL OpenAlex education institution import")
    print("Endpoint: https://api.openalex.org/institutions")
    print("Filter: type:education")
    print(f"Batch size: {per_page}")
    print("Using cursor pagination. Existing OpenAlex records are updated/deduplicated.")
    print("=" * 72)

    while True:
        page += 1
        print(f"\nDownloading page {page}...", flush=True)
        try:
            data = fetch_page(cursor, per_page, mailto)
        except Exception as exc:
            totals["errors"] += 1
            print(f"  ERROR: page {page} failed after retries: {exc}", flush=True)
            print("  Already committed records are safe. You can run app.py again to retry.", flush=True)
            break

        results = data.get("results") or []
        meta = data.get("meta") or {}
        if reported_count is None:
            reported_count = meta.get("count")
            if reported_count is not None:
                print(f"OpenAlex reports {reported_count:,} matching education institutions.", flush=True)

        if not results:
            print("  Reached the end of the dataset.", flush=True)
            break

        records = [normalize_openalex(item) for item in results]
        stats = import_records(records)
        for key in totals:
            totals[key] += stats[key]
        processed += len(records)

        print(
            f"  Processed: {processed:,} | New: {totals['new']:,} | "
            f"Updated: {totals['updated']:,} | Skipped: {totals['skipped']:,} | "
            f"Errors: {totals['errors']:,}", flush=True
        )

        next_cursor = meta.get("next_cursor")
        if not next_cursor:
            print("  OpenAlex returned no next_cursor. Import complete.", flush=True)
            break
        if next_cursor in seen_cursors or next_cursor == cursor:
            print("  ERROR: OpenAlex returned a repeated cursor. Stopping safely.", flush=True)
            totals["errors"] += 1
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor

        if max_pages and page >= max_pages:
            print(f"  Stopping after requested limit of {max_pages} pages.", flush=True)
            break

        time.sleep(0.15)

    print("\n" + "=" * 72)
    print(f"OpenAlex reported total: {reported_count:,}" if reported_count is not None else "OpenAlex reported total: unknown")
    print(f"Institutions processed: {processed:,}")
    print(f"New institutions: {totals['new']:,}")
    print(f"Updated institutions: {totals['updated']:,}")
    print(f"Skipped: {totals['skipped']:,}")
    print(f"Errors: {totals['errors']:,}")
    print("=" * 72)
    return totals


if __name__ == "__main__":
    import_openalex(mailto=os.environ.get("OPENALEX_MAILTO"))
