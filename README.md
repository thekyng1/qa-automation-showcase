# QA Automation Showcase — Closed-Loop UI → API → DB Testing

**Start here if you're hiring.** This is the hiring guide and architecture
showcase for a three-layer QA automation framework built with Playwright,
the Postman runtime, and MySQL.

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

This framework closes the loop. Every critical user flow is asserted at
all three layers, in one test:

| Layer | Technology | The assertion |
| --- | --- | --- |
| **UI** | Playwright + TypeScript, Page Object Model | The user can complete the flow in the browser |
| **API** | Postman runtime embedded via `withPostman(config)` | The real browser traffic matches the expected requests (captured live — not mocked) |
| **DB** | Custom Playwright fixture over `mysql2/promise` | The row exists in MySQL with the exact expected values |

> **In one sentence:** what the user did in the browser must land in the
> database — and the test proves it.

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
          transactional: BEGIN -> seed -> test asserts -> ROLLBACK
```

## Key engineering decisions (and why)

| # | Decision | Why |
| --- | --- | --- |
| 1 | `withPostman()` in `playwright.config.ts` instead of `attachNetworkCapture()` | Captures **all** pages and contexts, including manually created ones — the officially recommended integration |
| 2 | Custom MySQL fixture instead of a third-party connector | The referenced npm connector does not exist; a fixture is small, keeps the API declarative: `expect(db).toHaveRecord(...)` |
| 3 | Hybrid data isolation | A fixture transaction alone cannot roll back rows committed by the application on its own connection. So: rollback for seeded data + unique generated keys + post-test cleanup |

## What to look at in the main repo

| If you want to see… | Open… |
| --- | --- |
| The closed-loop test (UI → API → DB in one flow) | the `tests/` directory |
| Transactional DB fixture with rollback | `fixtures/db.fixture.ts` |
| Live API capture wired into Playwright | `playwright.config.ts` (`withPostman`) |
| Page Object Model, clean and reusable | `pages/` |
| CI pipeline (GitHub Actions) | `.github/workflows/ci.yml` |
| Design notes & limitations | `README.md` |

## CI

Every push runs the full suite on GitHub Actions — lint, type-check, and
all tests across the three layers, with reports uploaded as artifacts.

## Known limitations (stated honestly)

- The demo app under test is a public sandbox; the DB layer runs against a
  MySQL instance provisioned in CI.
- Rollback-based isolation covers seeded data; application-committed rows
  are handled with generated unique keys — the trade-off is documented,
  not hidden.

---

**Questions this framework answers in an interview:** How do you structure
a scalable test automation project? How do you prove persistence? How do
you isolate test data? How do you wire API assertions into UI flows
without mocks?

The answers are in the
[main repository](https://github.com/thekyng1/qa-automation-framework).
