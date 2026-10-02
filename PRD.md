# Product Requirements Document
## Mutual Fund Facts-Only FAQ Assistant (RAG Chatbot)

**Product:** Class-demo RAG chatbot  
**Milestone:** NextLeap PM — Milestone 4  
**Version:** 1.0  
**Date:** 27 September 2026  
**Owner:** Aishwarya Pillai  
**Status:** Draft for class demo  

---

## 1. Summary

Build a small Retrieval-Augmented Generation (RAG) FAQ assistant that answers **factual** questions about **five HDFC mutual fund schemes**, using **official public pages only**. Every answer must include **one source link**. The product does **not** give investment advice, compare returns, or collect personal data.

This is a **working prototype for a class demo**, not a production support bot.

---

## 2. Problem

Retail investors and support/content teams repeatedly ask the same scheme facts: expense ratio, exit load, minimum SIP, ELSS lock-in, riskometer, benchmark, and how to download statements.

Today those answers are scattered across factsheets, KIM/SID, AMC FAQs, and AMFI/SEBI pages. People either:

- Guess from unofficial blogs, or
- Wait for a human to look up the same document every time.

There is no lightweight, **citations-first** assistant that stays inside official sources and refuses advice.

---

## 3. Who this helps

| Persona | Need |
|---|---|
| **Retail user comparing schemes** | Fast, cited facts before they read a long factsheet |
| **Support / content teammate** | Consistent answers to repetitive MF FAQ questions |

**Primary demo user:** a classmate or instructor asking 3–5 scheme-fact questions and one “should I buy?” question.

---

## 4. Goals and non-goals

### Goals

1. Answer factual queries about the scoped HDFC schemes using retrieved official text.
2. Show **exactly one citation URL** on every factual answer.
3. Keep answers **≤ 3 sentences**, plus `Last updated from sources: <date>`.
4. Refuse opinion, buy/sell, and portfolio questions politely, with one educational (official) link.
5. Demo a tiny UI: welcome line, 3 example questions, and a facts-only disclaimer.

### Non-goals (out of scope for this demo)

- Personalized portfolio advice, risk profiling, or KYC flows
- Login, holdings, transaction history, or statement generation
- Computing, ranking, or comparing returns / “best fund”
- Multi-AMC coverage or live NAV charts
- Storing PAN, Aadhaar, account numbers, OTPs, emails, or phone numbers
- Using Groww, blogs, YouTube, or unofficial aggregators as **citation sources**

---

## 5. Scope

### 5.1 AMC and schemes

**AMC:** HDFC Mutual Fund (one AMC)

**Schemes (3–5 required; we include 5):**

| # | Category | Scheme (Direct Growth, as named in the brief) | Identity URL (not a citation source) |
|---|---|---|---|
| 1 | Large cap | HDFC Large Cap Fund – Direct Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 2 | Flexi cap | HDFC Equity Fund – Direct Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| 3 | ELSS | HDFC ELSS Tax Saver Fund – Direct Plan Growth | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |
| 4 | Small cap | HDFC Small Cap Fund – Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| 5 | Hybrid | HDFC Balanced Advantage Fund – Direct Growth | https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth |

Groww links in the brief **identify which schemes to cover**. The RAG corpus and on-screen citations must come from **AMC / SEBI / AMFI public pages**, not Groww.

### 5.2 Corpus (public pages only)

Ingest and index official pages such as:

- Scheme factsheets (HDFC AMC)
- KIM / SID (HDFC AMC)
- Scheme FAQs and fee / charges pages
- Riskometer and benchmark notes
- Statement / tax-document download guides (AMC or registrar)
- Relevant AMFI / SEBI investor-education pages (especially for refusals and “how to download statements”)

**Refresh expectation for demo:** corpus snapshotted before the demo; UI shows `Last updated from sources: <snapshot date>`.

---

## 6. User experience

### 6.1 Tiny UI (required)

On first load, the screen must show:

1. **Welcome line** — e.g. “Ask factual questions about five HDFC mutual fund schemes.”
2. **Three example questions** (clickable chips preferred for demo speed), for example:
   - What is the expense ratio of HDFC Large Cap Fund Direct Growth?
   - What is the lock-in for HDFC ELSS Tax Saver?
   - How do I download a capital-gains statement?
3. **Disclaimer:** “Facts-only. No investment advice.”

Plus: a single text box, send button, and a chat transcript.

### 6.2 Answer pattern (factual)

```
<1–3 sentence fact>

Source: <one official URL>
Last updated from sources: <YYYY-MM-DD>
```

### 6.3 Refusal pattern (advice / opinion)

Examples of queries to refuse: “Should I buy this?”, “Is this better than X?”, “Where should I put my money?”

```
I can only share documented scheme facts, not buy/sell or portfolio advice.

Source: <one official investor-education URL (SEBI/AMFI/AMC)>
Last updated from sources: <YYYY-MM-DD>
```

### 6.4 PII pattern

If the user pastes PAN, Aadhaar, account numbers, OTPs, emails, or phone numbers:

- Do not store or echo the values.
- Reply that personal identifiers are not accepted.
- Do not attempt account-specific lookups.

---

## 7. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Chat accepts a natural-language question and returns an answer in ≤ 3 sentences. | P0 |
| FR-2 | Factual answers are grounded in retrieved corpus chunks (RAG), not free-form model memory. | P0 |
| FR-3 | Every answer includes **one** citation link to an official public page. | P0 |
| FR-4 | Every answer includes `Last updated from sources: <date>`. | P0 |
| FR-5 | Supports the FAQ types in §8 for all five scoped schemes (where the fact exists). | P0 |
| FR-6 | Refuses opinion / advice / “which fund is best” with the refusal pattern. | P0 |
| FR-7 | Refuses performance computation; if asked for returns, point to the official factsheet link only. | P0 |
| FR-8 | Rejects PII input; does not persist PII. | P0 |
| FR-9 | UI shows welcome, 3 examples, and the facts-only note. | P0 |
| FR-10 | If retrieval is empty or low-confidence, say the fact is not in the indexed official pages and still provide a relevant official link (scheme page or factsheet). | P1 |
| FR-11 | Ambiguous scheme name → ask a one-line clarification naming the five in-scope schemes. | P1 |

---

## 8. Question types in scope

The assistant must handle these **facts-only** intents:

| Intent | Example |
|---|---|
| Expense ratio | “Expense ratio of HDFC Small Cap Direct Growth?” |
| Exit load | “Exit load on HDFC Flexi Cap / Equity Fund?” |
| Minimum SIP / min investment | “Minimum SIP for HDFC Large Cap?” |
| ELSS lock-in | “ELSS lock-in?” |
| Riskometer | “Riskometer of HDFC Balanced Advantage?” |
| Benchmark | “What is the benchmark of HDFC Large Cap?” |
| Statement / tax docs | “How to download capital-gains statement?” |

Out-of-corpus but still in product policy: advice, returns ranking, other AMCs, and PII.

---

## 9. RAG behaviour (demo architecture)

High-level flow (implementation may vary; behaviour is what we demo):

1. **Ingest** official pages for the five schemes + shared FAQ/guides.
2. **Chunk** and **embed** text; store in a vector index.
3. **Retrieve** top chunks for the user question (scheme-aware if the question names a fund).
4. **Generate** only from retrieved text + a system prompt that enforces: facts only, ≤ 3 sentences, one URL, no advice, no PII.
5. **Cite** the single best matching official URL (the page the chunk came from).

If the model cannot support a claim from retrieved text, it must not invent numbers (expense ratio, load, SIP, lock-in).

---

## 10. Constraints (hard rules)

| Constraint | Product implication |
|---|---|
| **Public sources only** | Citations = HDFC AMC / SEBI / AMFI URLs. No app-backend screenshots. No blogs. Groww is not a source. |
| **No PII** | No capture/storage of PAN, Aadhaar, account numbers, OTPs, emails, phones. |
| **No performance claims** | Do not compute or compare returns. Link the official factsheet. |
| **Clarity** | ≤ 3 sentences + source + last-updated line. |
| **No advice** | Buy/sell/allocation questions always refused. |

---

## 11. Success metrics (class demo)

| Metric | Target for demo |
|---|---|
| Citation coverage | 100% of answers include one official URL |
| Advice refusals | 100% of buy/sell/opinion questions refused with educational link |
| Answer length | 100% of answers ≤ 3 sentences (excluding source/date lines) |
| Gold-set accuracy | ≥ 80% of a 10-question gold set matches the indexed official page (numbers and lock-in) |
| Empty-hallucination | 0 invented expense ratios / exit loads when the chunk is missing |
| Demo time | End-to-end happy path + refusal + PII reject in **under 3 minutes** |

**Gold-set (suggested 10):** one expense ratio, one exit load, one min SIP, ELSS lock-in, one riskometer, one benchmark, one statement-how-to, one returns question (must link factsheet only), one “should I buy?”, one other-AMC or out-of-scope scheme.

---

## 12. Demo script

1. Open UI → point to welcome, 3 examples, “Facts-only. No investment advice.”
2. Click example: expense ratio → show 1–3 sentences + source + date.
3. Ask ELSS lock-in → cited lock-in fact.
4. Ask “Should I invest in HDFC Small Cap?” → refusal + educational link.
5. Ask “Which of these has the best 5-year return?” → no ranking; factsheet link only.
6. (Optional) Paste a fake PAN → PII rejection, value not shown back.

---

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Groww pages used as corpus (violates “official sources”) | Index HDFC AMC / AMFI / SEBI pages; treat Groww URLs as scheme identifiers only |
| Stale expense ratio / load vs live factsheet | Show snapshot date; pick pages dated as close to demo as practical |
| Model invents numbers | Prompt + retrieval gate; if no chunk, say unknown and link factsheet |
| Scheme name confusion (Equity Fund vs Flexi Cap naming) | Map aliases in metadata; clarify when ambiguous |
| Over-long answers | Hard cap in prompt and UI truncation with “see source” |

---

## 14. Open questions

1. Exact official URLs for each scheme’s latest factsheet, KIM, and SID (to be collected during corpus build).
2. Whether “HDFC Equity Fund” should be labelled **flexi-cap** in the UI copy (brief uses that mapping).
3. Hosting for demo: local laptop vs. a shared URL.

---

## 15. Acceptance checklist

- [ ] Corpus covers 1 AMC and 5 named schemes from official pages  
- [ ] Prototype answers expense ratio, exit load, min SIP, ELSS lock-in, riskometer/benchmark, statement download  
- [ ] Every answer has one source link and last-updated line  
- [ ] Advice and returns-comparison questions are refused / factsheet-linked as specified  
- [ ] UI: welcome + 3 examples + “Facts-only. No investment advice.”  
- [ ] No PII accepted or stored  
- [ ] Answers stay ≤ 3 sentences  
