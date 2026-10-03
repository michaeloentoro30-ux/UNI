# UniScout

UniScout is a Flask + SQLite university discovery application.

## One-command startup

From this folder:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Or double-click `start.bat`.

## Automatic ~27k OpenAlex import

On the first startup, if `data/uniscout.db` has no universities, `app.py` automatically starts the OpenAlex institution importer.

The importer uses:

- OpenAlex `institutions`
- `filter=type:education`
- cursor pagination
- up to 200 records per request
- retries and exponential backoff
- incremental SQLite commits
- OpenAlex source IDs for deduplication
- progress output

The exact number returned by OpenAlex can change over time. It is not hardcoded to 27,000. The importer follows the dataset until OpenAlex returns no next cursor.

Example output:

```text
UniScout: OpenAlex full institution import
Filter: type:education
Batch size: 200

Downloading page 1...
  Processed: 200 | New: 200 | Updated: 0 | Skipped: 0 | Errors: 0
Downloading page 2...
  Processed: 400 | New: 400 | Updated: 0 | Skipped: 0 | Errors: 0
...
```

After the first import, subsequent `python app.py` launches reuse the local database and do not download the dataset again.

## Re-import / refresh

If you want to rebuild the OpenAlex dataset, stop Flask and delete:

```text
data\uniscout.db
```

Then run:

```powershell
python app.py
```

The full import will start again.

## Optional OpenAlex email

You can optionally set an email for OpenAlex polite-pool identification:

```powershell
$env:OPENALEX_MAILTO="you@example.com"
python app.py
```

No paid API key is required.

## Important data limitation

OpenAlex provides institution metadata, not complete tuition, rankings, majors, admissions requirements, or student statistics for every institution. UniScout therefore leaves unavailable fields blank and displays `Not available` rather than inventing information.

## Ollama

Install/run Ollama separately and have Gemma 3 4B available. UniScout communicates through `ollama_client.py`.
\n\nIMPORTANT: If you previously ran an older UniScout build, delete data/uniscout.db once before using this build. This version automatically imports OpenAlex institutions on app.py startup until at least 20,000 OpenAlex records are present. It intentionally does not use the OpenAlex `select` parameter because unsupported selected fields can cause the API request to fail with zero imported records.\n