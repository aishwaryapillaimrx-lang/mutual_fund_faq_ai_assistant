# Implementation guide (phase-wise)
## Mutual Fund Facts-Only FAQ Assistant

**Use this file to drive Cursor.** Do one phase per chat (or per prompt). Do not skip phases.  
**Sources of truth:** [PRD.md](./PRD.md) · [architecture.md](./architecture.md)  
**Do not** use Groww pages as corpus or citations.

---

## How to use this with Cursor

1. Open a **new Agent chat** for each phase (keeps context small).
2. Paste the **Cursor prompt** block at the end of that phase.
3. After Cursor finishes, run the **Verify** steps yourself.
4. Only start the next phase when **Definition of done** is checked.
5. If Cursor drifts, reply: `Stop. Re-read architecture.md §4 and implementation.md for this phase only. Do not start the next phase.`

**Every phase — standing rules**

- Follow `architecture.md` flows and the JSON response contract (§5.3).
- Public sources only: `hdfcfund.com`, `amfiindia.com`, `sebi.gov.in` (and official subdomains).
- No PII storage, no user DB, no returns calculator, no investment advice.
- Answers: ≤ 3 sentences of body + `source_url` + `last_updated`.
- Stack (unless already created otherwise): Python 3.11+, FastAPI, Chroma (disk), one OpenAI-compatible embedding + chat API, static HTML UI.
- Secrets only in `.env` (never commit keys). Add `.env` to `.gitignore`.

---

## Target layout (create as you go; do not invent extra layers)

```text
app/
  main.py                 # FastAPI app, POST /chat, GET /
  config.py
  catalog.py              # five schemes + aliases + fallback factsheet URLs
  policy/
    pii.py
    intent.py
    scheme_resolver.py
  rag/
    ingest.py
    retrieve.py
    cite.py
    prompt.py
    generate.py
    format.py
  pipeline.py             # PII → intent → retrieve/generate → format
static/
  index.html
data/
  manifest.json           # official URLs only
  corpus/                 # downloaded files (gitignored if large)
  index/                  # Chroma persist dir (gitignored)
scripts/
  ingest.py               # CLI: python scripts/ingest.py
tests/
  test_policy.py
  test_formatter.py
  gold_set.json
  test_gold_set.py        # Phase 7
.env.example
requirements.txt
README.md                 # run instructions only
```

---

## Phase 0 — Repo bootstrap

**Goal:** Empty app that boots; config and layout exist; no RAG yet.

**Build**

- `requirements.txt`: `fastapi`, `uvicorn`, `python-dotenv`, `pydantic`, `chromadb`, `httpx`, plus the embedding/LLM client you choose.
- `app/config.py`: load `.env` — `LLM_API_KEY`, `LLM_BASE_URL` (optional), `EMBED_MODEL`, `CHAT_MODEL`, `CORPUS_SNAPSHOT_DATE`, `RETRIEVAL_SCORE_THRESHOLD`, `ALLOWED_HOSTS`.
- `app/main.py`: `GET /health` → `{"ok": true}`; `GET /` can 404 until Phase 2.
- `.env.example` with dummy keys.
- `.gitignore`: `.env`, `data/corpus/`, `data/index/`, `__pycache__/`, `.venv/`.

**Do not**

- Call the LLM.
- Download any pages.
- Build UI.

**Definition of done**

- [ ] `python -m venv .venv` + install works
- [ ] `uvicorn app.main:app --reload` and `GET /health` returns ok

**Verify:** `curl http://127.0.0.1:8000/health`

**Cursor prompt**

```text
Read architecture.md (full) and implementation.md Phase 0 only.

Implement Phase 0: Python FastAPI bootstrap for a class-demo RAG FAQ bot.
Create the folder layout stubs (empty modules with docstrings are OK except main.py and config.py which must work).
Add requirements.txt, .env.example, .gitignore as specified in implementation.md.

Do not implement ingest, RAG, UI, or policy logic.
Do not start Phase 1.

When done, list files created and how to run /health.
```

---

## Phase 1 — Catalog + policy (no LLM)

**Goal:** Deterministic PII, intent, and scheme resolution matching `architecture.md` §6.1 and §5.1.

**Build**

- `app/catalog.py` — exactly five schemes from PRD §5.1. Each: `scheme_id`, `display_name`, `category`, `aliases[]`, `factsheet_url` (placeholder official HDFC URL is OK until Phase 3; must be an allowlisted host, **not Groww**).
- `app/policy/pii.py` — detect PAN-like, 12-digit Aadhaar-like, OTP-like, email, Indian mobile, long digit account-like strings. Return `bool` (or match type). **Never log the raw question** if PII is true.
- `app/policy/intent.py` — `advice | performance | factual | out_of_scope` using keyword lists in architecture §6.1. Priority: PII is handled before intent. If advice keywords win over factual, return `advice`. Other AMC names (SBI, ICICI, Nippon, etc.) → `out_of_scope` unless it is clearly one of our five.
- `app/policy/scheme_resolver.py` — match aliases; 0 matches + factual → still `factual` with `scheme_id=None`; 2+ distinct schemes → `clarify`.
- `tests/test_policy.py` — table tests for: fake PAN, “Should I buy HDFC Small Cap?”, “best 5-year return”, “expense ratio HDFC Large Cap”, “SBI Bluechip expense ratio”, “ELSS lock-in”, “HDFC Equity Fund exit load” → flexi-cap id.

**Do not**

- Wire FastAPI `/chat`.
- Call embeddings or chat models.

**Definition of done**

- [ ] `pytest tests/test_policy.py` passes
- [ ] Groww URLs do not appear in `catalog.py`

**Verify:** pytest; spot-check alias “HDFC Equity Fund” → flexi-cap `scheme_id`.

**Cursor prompt**

```text
Read architecture.md §5.1, §6.1, §9 and implementation.md Phase 1 only.
Also read PRD.md §5.1 and §10.

Implement catalog.py, pii.py, intent.py, scheme_resolver.py and tests/test_policy.py.
Use placeholder official factsheet URLs on allowlisted hosts only — never groww.in.

Do not implement RAG, ingest, UI, or /chat.
Do not start Phase 2.

Run pytest tests/test_policy.py and fix until green.
```

---

## Phase 2 — Tiny UI + `/chat` stub

**Goal:** Demo shell (FR-9) talking to a stub API that already applies policy.

**Build**

- `static/index.html` — welcome line, three **clickable** example chips from PRD §6.1, disclaimer `Facts-only. No investment advice.`, text box, send, transcript.
- `GET /` serves this file.
- `POST /chat` body `{ "question": "..." }` returns architecture §5.3 JSON.
- `app/pipeline.py` for this phase:
  - PII → `type: pii`, canned 1–3 sentences, official education/contact URL, `last_updated` from config, `scheme_id: null`. Do not echo identifiers.
  - `advice` → `type: refusal` + SEBI/AMFI education URL (hardcode one official link).
  - `performance` → `type: refusal` (or a dedicated type still rendered the same), no numbers; `source_url` = resolved scheme `factsheet_url` or AMC factsheet hub.
  - `out_of_scope` → list the five display names; one official HDFC funds URL.
  - `clarify` → `type: clarify`, ask which of the five.
  - `factual` → **stub**: `type: not_found`, message that the index is not built yet, still include one official fallback URL and `last_updated`.

**Do not**

- Embed, retrieve, or generate with an LLM.
- Persist chat logs.

**Definition of done**

- [ ] UI shows welcome, 3 chips, disclaimer
- [ ] Clicking a chip fills/sends the question
- [ ] Advice and PII paths work in the browser without an API key
- [ ] Factual path returns stub `not_found` with a citation

**Verify:** Manual browser: chip → stub; “Should I invest?” → refusal; paste `ABCDE1234F` → PII, value not shown in the answer.

**Cursor prompt**

```text
Read architecture.md §3 (Chat UI, Chat API), §4.2, §5.3 and implementation.md Phase 2 only.
Read PRD.md §6.

Implement static/index.html, GET /, POST /chat, and pipeline.py that uses Phase 1 policy.
Factual questions must stub as not_found until RAG exists — still return source_url and last_updated.

Do not add Chroma, ingest, or LLM calls.
Do not start Phase 3.

Keep answers ≤ 3 sentences. Do not log PII.
```

---

## Phase 3 — Manifest + ingest

**Goal:** Offline corpus from official pages; host allowlist; chunks with metadata.

**Build**

- `data/manifest.json` — list of docs: `scheme_id` (or null for shared statement/education pages), `doc_type`, `source_url`. Cover all five schemes and at least: factsheet (or KIM/SID), plus one shared statements/tax-doc guide, plus one investor-education page for refusals.
- **You (Aishwarya) or Cursor with web fetch:** replace placeholder URLs with real public HDFC AMC / AMFI / SEBI URLs. If a PDF/HTML cannot be fetched automatically, save it under `data/corpus/` and point the manifest `local_path`.
- `app/rag/ingest.py` + `scripts/ingest.py`:
  - Reject URL if host not in `ALLOWED_HOSTS` (must reject `groww.in`).
  - Download or read local file; extract text (HTML + PDF).
  - Chunk ~400–800 tokens with overlap; metadata per architecture §5.2.
  - Persist Chroma to `data/index/`.
  - Write/confirm `CORPUS_SNAPSHOT_DATE`.
- Startup: if index empty, `/health` can still be ok but `/chat` factual path stays `not_found` (already stubbed).

**Do not**

- Ingest Groww, Moneycontrol, blogs, YouTube.
- Call the chat model (embeddings for ingest are allowed).

**Definition of done**

- [ ] `python scripts/ingest.py` completes
- [ ] Index has chunks for all five `scheme_id`s
- [ ] A Groww URL in manifest is skipped/rejected (add a unit test if easy)
- [ ] Each chunk has `source_url`, `snapshot_date`, `doc_type`

**Verify:** Print chunk counts by `scheme_id`. Open one `source_url` in a browser — it must be official.

**Cursor prompt**

```text
Read architecture.md §4.1, §5.2, §7, §8 and implementation.md Phase 3 only.

Implement manifest.json, ingest pipeline, and scripts/ingest.py with host allowlist.
Use official HDFC AMC / SEBI / AMFI URLs only. Never ingest groww.in.

If live download fails, support local_path files under data/corpus/.
Do not implement retriever or LLM generation.
Do not start Phase 4.

Add a test or script flag that proves groww.in URLs are rejected.
```

**Human step:** Fill real factsheet/KIM/SID URLs in the manifest if Cursor guessed wrong. Re-run ingest.

---

## Phase 4 — Retrieve, cite, retrieval gate

**Goal:** FR-2, FR-3, FR-10 without generation — return top chunks + one URL or `not_found`.

**Build**

- `app/rag/retrieve.py` — embed question; optionally filter `scheme_id`; top-k (k=4 is enough); return texts + scores + metadata.
- `app/rag/cite.py` — single `source_url` from best chunk; drop if host not allowlisted.
- Retrieval gate: if no chunks or `top_score < RETRIEVAL_SCORE_THRESHOLD` → pipeline returns `type: not_found` + fallback `factsheet_url` (or AMC hub) + `last_updated`. **Do not call chat LLM.**
- Temporary factual success path (until Phase 5): return `type: factual` with `answer` = first 2 sentences of the top chunk (truncated), plus citation — so you can demo retrieval without an LLM if needed.
- Wire this into `pipeline.py` for `intent == factual` only.

**Do not**

- Add the final system prompt / chat completion yet (optional extractive stub is OK).
- Change policy behaviour from Phase 2.

**Definition of done**

- [ ] “Expense ratio of HDFC Large Cap…” retrieves that scheme’s chunks when index is built
- [ ] Low-score query → `not_found`, no invented TER
- [ ] Exactly one `source_url` on the response

**Verify:** `POST /chat` with a scheme fact vs nonsense string (`asdfgh`) → `not_found`.

**Cursor prompt**

```text
Read architecture.md §4.2 retrieval gate, §5.2, §6.3 and implementation.md Phase 4 only.

Implement retrieve.py, cite.py, and wire factual path in pipeline.py.
If gate fails: type not_found, one fallback official URL, do not call the chat LLM.
If gate passes: you may use an extractive stub from the top chunk (no chat LLM yet).

Do not start Phase 5.
Keep one citation only. Allowlisted hosts only.
```

---

## Phase 5 — Generate + format (full RAG)

**Goal:** FR-1, FR-2, FR-4 — LLM answers **only** from chunks; formatter owns citation and date.

**Build**

- `app/rag/prompt.py` — system prompt contract from architecture §6.2.
- `app/rag/generate.py` — low temperature; timeout → architecture §9 busy message + factsheet URL.
- `app/rag/format.py` — cap body to 3 sentences (split on `. ` / `?` / `!`); append is **not** inside the model: API JSON stays `{answer, source_url, last_updated}`; UI displays:

```text
{answer}

Source: {source_url}
Last updated from sources: {last_updated}
```

- Replace extractive stub: gate pass → prompt + generate → format.
- **Never** send the user question to the LLM if PII was detected (already short-circuited).

**Do not**

- Let the model output the Source URL (ignore if it does; formatter/cite wins).
- Compute returns in code or prompt.

**Definition of done**

- [ ] Factual answers are grounded and ≤ 3 sentences
- [ ] Source and date always present
- [ ] Missing chunk still `not_found` (gate still first)

**Verify:** Three PRD example questions in the UI. Count sentences. Click the source link.

**Cursor prompt**

```text
Read architecture.md §6.2, §6.3, §9 LLM timeout and implementation.md Phase 5 only.
Read PRD.md §6.2.

Implement prompt.py, generate.py, format.py and replace the extractive stub.
Formatter/citation picker own source_url and last_updated — not the model.
Retrieval gate still skips the LLM on low score.

Do not start Phase 6.
Do not add new product features.
```

---

## Phase 6 — Edge paths + demo hardening

**Goal:** FR-6, FR-7, FR-8, FR-11 polished for the 3-minute demo.

**Build**

- Confirm advice / performance / PII / clarify copy matches PRD §6.3–6.4 (polite, facts-only, one educational or factsheet link).
- Performance: **no** CAGR math; only “see the official factsheet” + that URL.
- Empty index at startup: log error; factual path `not_found` with clear message.
- UI: show `type` only in the transcript as normal assistant text (no debug JSON in the demo view). Optional small “Facts-only” badge already on page.
- README: `cp .env.example .env`, ingest, `uvicorn`, demo script from PRD §12.

**Do not**

- Add login, history DB, or extra schemes.

**Definition of done**

- [ ] PRD §12 demo script runs locally end-to-end
- [ ] README is enough for you to start the app on demo day

**Verify:** Walk PRD §12 yourself in the browser.

**Cursor prompt**

```text
Read PRD.md §6, §12 and architecture.md §9, §11.
Read implementation.md Phase 6 only.

Harden refusal/performance/PII/clarify copy, empty-index behaviour, UI transcript (no raw JSON), and README run + demo steps.

Do not add features outside the PRD.
Do not start Phase 7 until asked.
```

---

## Phase 7 — Gold set + acceptance

**Goal:** PRD §11 metrics; stop hallucinated numbers.

**Build**

- `tests/gold_set.json` — 10 items from PRD §11 (expense ratio, exit load, min SIP, ELSS lock-in, riskometer, benchmark, statement how-to, returns question, should-I-buy, other-AMC).
- Each item: `question`, `expect_type`, optional `must_include` strings, `source_host_allowlist`.
- `tests/test_gold_set.py` — calls pipeline (mark `@pytest.mark.integration`; skip if no API key / no index).
- Manual checklist in README matching PRD §15.

**Definition of done**

- [ ] ≥ 8/10 gold items behave as expected (80%)
- [ ] 0 invented expense ratios on `not_found` / empty retrieval
- [ ] 100% responses include one URL + last_updated (PII included)

**Verify:** Run integration test or a small `scripts/eval_gold.py` that prints a table.

**Cursor prompt**

```text
Read PRD.md §11 and §15, architecture.md §10, implementation.md Phase 7 only.

Add tests/gold_set.json and an integration eval that exercises the pipeline.
Do not weaken the retrieval gate to game the score.
Do not ingest unofficial sources to pass tests.

Print a pass/fail table. Fix prompt/resolver/manifest only if a failure is a real product bug.
```

---

## Phase order (do not reorder)

| Phase | Delivers | Unlocks demo of |
|---|---|---|
| 0 | App boots | — |
| 1 | Policy unit tests | — |
| 2 | UI + refusals | Advice / PII / chips |
| 3 | Official index | — |
| 4 | Retrieval + gate | “We don’t invent numbers” |
| 5 | RAG answers | Expense ratio / lock-in |
| 6 | Copy + README | Full 3-min script |
| 7 | Gold set | Confidence for class |

---

## If Cursor gets stuck

| Symptom | Fix |
|---|---|
| Wants to scrape Groww | Remind: identifiers only; citations = AMC/SEBI/AMFI |
| Builds LangGraph / agents | Reject; keep `pipeline.py` linear |
| Adds a database | Reject |
| Long answers | Tighten `format.py`; do not only “ask the model nicely” |
| Hallucinated TER | Gate threshold; check the right `scheme_id` filter |
| Ingest blocked by site | Download PDF manually into `data/corpus/` + `local_path` |

---

## Suggested first message (whole project, only if you insist on one chat)

Prefer **one phase per chat**. If you use a single long chat, start with:

```text
You are implementing a class-demo RAG chatbot.
Read PRD.md, architecture.md, and implementation.md.
Execute Phase 0 only. Stop and wait for me to say "proceed to Phase N".
```
