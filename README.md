# NYC 311 Scout

A small chat agent for New Yorkers comparing the everyday nuisances reported in
two ZIP codes. It uses live NYC 311 data to summarize reports, compare concerns,
and calculate changes over time. Its personal angle is **“what would bother me?”**:
users choose the issues they care about, and the agent explains those tradeoffs.

Built from `project1/scratch/gemini-web-tool-calling`, with the same basic structure:

- `app.py`: Gemini tool loop → in-memory session store → FastAPI routes.
- `tools.py`: three Python functions, JSON tool descriptions, and a dispatcher.
- `index.html`: a single page with plain HTML, CSS, and JavaScript.
- `pyproject.toml` / `uv.lock`: dependencies managed with uv. No requirements.txt.

## Run locally

Use this folder as the repository root.

```bash
uv sync --locked
```

The existing `.env` is for local settings. Set `VERTEXAI_PROJECT` there to
your GCP project ID. If you clone the repo elsewhere, create a `.env` file with
`VERTEXAI_PROJECT=YOUR_PROJECT_ID`, `VERTEXAI_LOCATION=global`, and
`MODEL=vertex_ai/gemini-3.5-flash-lite`. The default model matches the starter.
Enable Vertex AI and billing in that project, then authenticate locally:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
uv run app.py
```

Open http://localhost:8000. If another app is already using port 8000, stop it or
run `PORT=8001 uv run app.py` and open http://localhost:8001.

Alternatively, set `MODEL=gemini/gemini-3.5-flash-lite` and `GEMINI_API_KEY` in `.env`
to use Gemini's API-key provider. Select a Gemini model available to your account
if the starter's model is unavailable. A Google Places key is not a Gemini key.

Public 311 queries do not require a key. An optional `SOCRATA_APP_TOKEN` gives
your application its own request quota. Neither credentials nor `.env` are
included in Git.

## Three sample queries for the grader

1. **“Summarize 311 reports in 10027 over the last 30 days.”**
   Uses `get_zip_report`; returns totals, leading complaint types, and dates.
2. **“Compare 10027 and 10025 over the last 30 days. I care about noise and rodents.”**
   Uses `compare_zip_priorities`; compares counts and shares for those concerns.
3. **“Has noise reporting in 10027 increased over the last 30 days compared with the previous 30?”**
   Uses `get_concern_trend`; returns both windows, counts, and the change.

Follow up with “What about parking in that ZIP?” to exercise session memory.
Open a separate fresh browser session and ask “Which ZIP did I choose?” to check
that conversations are separate. “New chat” clears the current conversation.

## Tools and the assignment

All three tools query NYC Open Data via HTTP. Each has named parameters, JSON
descriptions, and actionable errors for bad inputs or unavailable services.

- `get_zip_report(zip_code, days=30)` groups all reports by complaint type.
- `compare_zip_priorities(zip_a, zip_b, concerns, days=30)` is the intended original
  tool: it translates personal nuisance priorities into a comparison of report
  counts, shares, and percentage-point differences. It exposes which complaint
  types matched and deliberately makes no overall quality-of-life score.
- `get_concern_trend(zip_code, concern, days=30)` calculates changes across two
  adjacent periods of equal length, with a defined zero-baseline case.

The agent decides which function to call and reads its result before answering.
The UI does not bypass the agent by calling tools directly. `/chat` preserves the
starter's response shape: `response`, `session_id`, and `tool_calls`, with `name`,
`args`, and `result` for every executed call. Each result is a JSON string, as in
the starter. Expand a tool underneath an answer to inspect it.

The frontend has ZIP and date-window controls, example questions, a distinct
visual design, and the interpretation caveats. There are no frontend libraries.

Originality relative to classmates cannot be guaranteed. The rubric requires one
original tool per team member: confirm team size and add another substantive
original tool if necessary.

## Understanding the numbers

Source: [NYC 311 Service Requests from 2020 to Present](https://data.cityofnewyork.us/d/erm2-nwe9).
API: `https://data.cityofnewyork.us/resource/erm2-nwe9.json`.
Queries group and count on the server instead of downloading individual records.

- Windows cover complete calendar days in New York, ending at today's midnight.
  `end_exclusive` is the first date excluded. The dataset updates daily and can lag.
- `latest_report_in_window` is the latest submitted report in the selected ZIP
  and window; it is not the dataset's last refresh time.
- A concern's share is `matching reports / all reports in that ZIP × 100`.
  Comparison differences are percentage points; trend percentages use the earlier
  period's count as their baseline. A zero denominator returns `null`.
- Concerns use the small, editable keyword dictionary at the top of `tools.py`.
  Rodents includes complaint types containing “rodent”; housing includes heat,
  plumbing, leaks, and the other listed types. The tool reports matching types.
  These are approximate groups, can overlap, and do not cover every issue.
- Reports may describe the same incident, and submission time is not necessarily
  incident time. They are not verified noise, safety, or cleanliness measurements.
- Counts are not population-adjusted. Shares describe report mix, not personal
  risk. Population, reporting habits, and ZIP boundaries affect comparisons.
- No matches mean no records returned, not proof of no problems. The app cannot
  distinguish an invalid NYC ZIP from a ZIP with zero reports in the period.
- No street addresses or individual complainant data are needed for this app.
