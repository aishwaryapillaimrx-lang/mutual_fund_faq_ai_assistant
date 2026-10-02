# HDFC Mutual Fund FAQ — facts-only assistant

Answers factual questions about five HDFC schemes (Large Cap, Flexi Cap, ELSS, Small Cap, Balanced Advantage) from official HDFC AMC / AMFI / SEBI documents. Every answer is at most 3 sentences with one source link and a "Last updated from sources" date. It refuses advice and returns questions, and rejects PII.

## Run it

```powershell
# 1. Environment
uv venv                                   # or: python -m venv .venv
uv pip install -r requirements.txt        # or: .venv\Scripts\pip install -r requirements.txt

# 2. Config: copy the template, then put your key in .env
copy .env.example .env                    # set ANTHROPIC_API_KEY=sk-ant-...

# 3. Build the index (once; uses on-device embeddings, no key needed)
.venv\Scripts\python scripts\ingest.py

# 4. Start the app
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Check `GET /health` returns `{"ok": true}`.

Notes:
- `.env` is read at startup — restart after editing. A variable already set in your shell takes precedence over `.env`.
- At startup the server logs an **error** if the index is empty/missing a scheme, or if `ANTHROPIC_API_KEY` is not set. Fix these before demoing.
- Answers use `claude-sonnet-5-5` by default; override with `CHAT_MODEL` in `.env`.
- Snapshot date is `CORPUS_SNAPSHOT_DATE` (shown as "Last updated from sources"). Re-run ingest to refresh the corpus.
- Tests: `.venv\Scripts\python -m pytest`

## Demo script (3 minutes)

1. Open the UI. Point to the welcome line, the 3 example chips and "Facts-only. No investment advice."
2. Click **"What is the expense ratio of HDFC Large Cap Fund Direct Growth?"** → short fact, one source link, last-updated date.
3. Click **"What is the lock-in for HDFC ELSS Tax Saver?"** → 3-year lock-in, cited.
4. Ask **"Should I invest in HDFC Small Cap?"** → polite refusal + AMFI investor-education link.
5. Ask **"Which of these has the best 5-year return?"** → no ranking or numbers; official factsheet link only.
6. (Optional) Paste a fake PAN such as `ABCDE1234F` → "Personal identifiers are not accepted"; the value is not shown back.

Other good questions: exit load of HDFC Small Cap, benchmark of HDFC Balanced Advantage Fund.

## Known limits

- Only information present in the indexed documents is answered. If a fact is not there (e.g. a scheme-specific minimum SIP), the assistant says so and links the official page instead of guessing.
- "How do I download a capital-gains statement?" depends on `data/corpus/manual/hdfc-capital-gain-statement.html` (HDFC blocks automated download). Save the page there and re-run ingest; otherwise it falls back to the AMFI CAS page or "not found".
- No login, no chat history, no database. Questions are not logged or stored.

## Layout

See `architecture.md` for design and `implementation.md` for the phase plan. Code: `app/policy` (PII, intent, scheme resolver), `app/rag` (ingest, retrieve, cite, prompt, generate, format), `app/pipeline.py` (the linear flow), `static/index.html` (UI).

## Evaluation (PRD §11)

```powershell
.venv\Scripts\python scripts\eval_gold.py          # prints a pass/fail table for the 10 gold questions
.venv\Scripts\python -m pytest -m integration      # same check as a test (skips without key/index)
```

The gold set is `tests/gold_set.json`. Each item checks the response type, required facts, that the source host is allowlisted, a date is present, the answer is at most 3 sentences, and that `not_found` answers contain no numbers. Questions whose answer is not in the indexed text (minimum SIP, riskometer level, which is a graphic in the PDFs) are expected to return `not_found`, which proves nothing is invented.

## Acceptance checklist (PRD §15) — tick before the demo

- [ ] Corpus covers 1 AMC and 5 schemes: `python scripts/ingest.py` shows chunks for all five
- [ ] Gold set passes at 80% or better: `python scripts/eval_gold.py`
- [ ] Every answer has one source link and a last-updated line (UI)
- [ ] Advice and returns questions are refused / factsheet-linked (demo steps 4 and 5)
- [ ] UI shows welcome line, 3 example chips and "Facts-only. No investment advice."
- [ ] Pasting a fake PAN is rejected and not echoed (demo step 6)
- [ ] Answers stay at 3 sentences or fewer
