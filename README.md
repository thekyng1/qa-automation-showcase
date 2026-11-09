# QA Automation Showcase — Closed-Loop UI → API → DB → AI Testing

**Start here if you're hiring.** This is the hiring guide and architecture
showcase for a four-layer QA automation framework built with Playwright,
the Postman runtime, MySQL, and LLM evaluation.

[![CI](https://github.com/thekyng1/qa-automation-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/thekyng1/qa-automation-framework/actions/workflows/ci.yml)
[![AI Real Eval](https://github.com/thekyng1/qa-automation-framework/actions/workflows/ai-real.yml/badge.svg)](https://github.com/thekyng1/qa-automation-framework/actions/workflows/ai-real.yml)

**Main repository:** [thekyng1/qa-automation-framework](https://github.com/thekyng1/qa-automation-framework)

---

## The problem it solves

Most UI automation answers only one question: *did the frontend react?*

A test clicks "Checkout", sees a green toast, and passes. But between the
click and the database there are two more layers where real bugs hide:

1. **The API layer** — the request may have a wrong payload, a wrong status,
   or the frontend may not even call what you think it calls.
2. **The persistence layer** — the request may succeed yet never commit,
   commit twice, or write wrong values.
3. **The AI layer** — a chatbot answer can be fluent, plausible, and still
   wrong, malformed, or over budget. Green toasts prove nothing here either.

This framework closes the loop. Every critical user flow is asserted at
all four layers, in one test:

| Layer | Technology | The assertion |
| --- | --- | --- |
| **UI** | Playwright + TypeScript, Page Object Model | The user can complete the flow in the browser |
| **API** | Postman runtime embedded via `withPostman(config)` | The real browser traffic matches the expected requests (captured live — not mocked) |
| **DB** | Custom Playwright fixture over `mysql2/promise` | The row exists in MySQL with the exact expected values |
| **AI** | LLM evals — schema, budget, grounding | The model's answer is valid JSON, inside the latency/token budget, grounded on expected facts — over 5 runs with a ≥80% pass-rate |

> **In one sentence:** what the user did in the browser must land in the
> database — and the chatbot's answer must be provably correct — and the
> tests prove both.

## AI layer — testing a non-deterministic system

LLMs don't return the same answer twice, so single-shot assertions can
never be stable. This layer applies the same closed-loop discipline to
non-deterministic output:

- **Hard assertions:** response must parse as JSON, satisfy a flat schema,
  respect a latency/token budget, and mention required grounding terms.
- **Statistical thresholds:** each case runs 5 times; pass-rate must be
  ≥80%. One lucky answer proves nothing.
- **Free, deterministic CI:** the suite runs on a scripted mock adapter —
  no network, no cost, no flakes. Real DeepSeek runs are opt-in via a
  manual GitHub Actions workflow (`ai-real.yml`) — triggered on demand,
  executed fully in the cloud; the API key lives in GitHub Secrets, never
  in code.
- **Provider-agnostic:** `LlmAdapter` is an interface — swapping DeepSeek
  for OpenAI, Groq, or Gemini is one file, zero test changes.

## Architecture at a glance

```text
browser (Playwright)
   |  user actions
   v
Page Objects (pages/)
   |
   +--> UI assertions (expect(page))
   |
   +--> network capture --> Postman runtime (pm.test on live traffic)
   |
   +--> DB fixture (fixtures/db.fixture.ts)
   |        transactional: BEGIN -> seed -> test asserts -> ROLLBACK
   |
   +--> LLM evals (ai/) — schema, budget, grounding
            statistical pass-rate; mock in CI, DeepSeek opt-in
```

## Key engineering decisions (and why)

| # | Decision | Why |
| --- | --- | --- |
| 1 | `withPostman()` in `playwright.config.ts` instead of `attachNetworkCapture()` | Captures **all** pages and contexts, including manually created ones — the officially recommended integration |
| 2 | Custom MySQL fixture instead of a third-party connector | The referenced npm connector does not exist; a fixture is small, keeps the API declarative: `expect(db).toHaveRecord(...)` |
| 3 | Hybrid data isolation | A fixture transaction alone cannot roll back rows committed by the application on its own connection. So: rollback for seeded data + unique generated keys + post-test cleanup |
| 4 | Statistical pass-rate instead of single-shot asserts for LLM output | One response can never be a stable assertion; a threshold over N runs can |

## What to look at in the main repo

| If you want to see… | Open… |
| --- | --- |
| The closed-loop test (UI → API → DB in one flow) | the `tests/` directory |
| LLM evals with statistical thresholds | the `ai/` directory and `tests/ai/` |
| Transactional DB fixture with rollback | `fixtures/db.fixture.ts` |
| Live API capture wired into Playwright | `playwright.config.ts` (`withPostman`) |
| Page Object Model, clean and reusable | `pages/` |
| CI pipeline (mock, on every push) + real-AI eval workflow (manual, cloud) | `.github/workflows/ci.yml` and `.github/workflows/ai-real.yml` |
| Design notes & limitations | `README.md` |

## CI

Every push runs the full suite on GitHub Actions — lint, type-check, and
all tests across the four layers, with reports uploaded as artifacts.
The badge above is live: it reflects the real status of the latest run
on `main`.

The **AI Real Eval** badge tracks a separate, manually triggered workflow
(`ai-real.yml`) that runs the same evals against the **live DeepSeek API**
— on demand, so cost stays under control, and fully in the cloud, so it
needs nothing from the local machine.

## Known limitations (stated honestly)

- The demo app under test is a public sandbox; the DB layer runs against a
  MySQL instance provisioned in CI.
- Rollback-based isolation covers seeded data; application-committed rows
  are handled with generated unique keys — the trade-off is documented,
  not hidden.
- LLM evals assert on structure, budget and grounding — semantic quality
  is covered by pass-rate over multiple runs, not by a single golden answer.

---

**Questions this framework answers in an interview:** How do you structure
a scalable test automation project? How do you prove persistence? How do
you isolate test data? How do you wire API assertions into UI flows
without mocks? How do you test a system that doesn't give the same answer
twice?

The answers are in the
[main repository](https://github.com/thekyng1/qa-automation-framework).
