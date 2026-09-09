# vendor-orchestrator

Portfolio project: a **case orchestration service**. A FastAPI app accepts a case, calls mock vendor HTTP APIs, persists case state, and lets an agent decide **escalate vs auto-resolve**. An eval harness scores that decision on **labeled mock fixtures**.

This is project #1 in a SWE I agent portfolio. The interview bridge is:

> orchestration + retries + case state + evals

It is **not** a KYB, AML, or sanctions product. Vendors here are mocks. There is no production traffic, no claimed vendor count, and no invented accuracy numbers.

## What works today

| Piece | Status |
| --- | --- |
| `POST /v1/cases` / `GET /v1/cases/{id}` | Working |
| Mock vendor HTTP clients (Alpha + Beta, in-process ASGI) | Working |
| Case + vendor-call persistence (Postgres in Compose; SQLite for tests/evals) | Working |
| Docker Compose (`app` + `db`) | Working |
| pytest + GitHub Actions (ruff / mypy / pytest / eval harness) | Working — **no Docker required** |
| Multi-vendor fan-out, retries, idempotency reuse | Working |
| Agent `decide_case` / tool-use loop | Working |
| Eval harness + labeled fixtures | Working — metrics come from fixture runs |

## Architecture

```mermaid
flowchart LR
    Client[HTTP client] --> API[FastAPI case API]
    API --> Store[(cases + vendor_calls)]
    API --> Runner[Create-path runner]
    Runner --> Fanout[Fan-out + retries + idempotency]
    API --> Agent[Agent loop]
    Agent --> Tools[Toolbelt]
    Tools --> Fanout
    Fanout --> Alpha[Mock vendor Alpha]
    Fanout --> Beta[Mock vendor Beta]
    Alpha --> Mock[In-process mock app]
    Beta --> Mock
    Evals[Eval harness] --> Agent
    Fixtures[Labeled mock fixtures] --> Evals
```

Create-case path: persist an `open` case → fan-out to Alpha → persist `vendor_calls` → set status to `vendor_checked` (or `vendor_failed`). **`decision` stays null** until `POST /v1/cases/{id}/run-agent`.

The agent reads the payload, selects a subset of mock vendors (default: Alpha only), and writes `escalate` or `auto_resolve`. Incomplete packets escalate without extra vendor spend. A non-`clear` mock signal escalates.

## Repository layout

```
src/vendor_orchestrator/
  api/            # health + case routes
  vendors/        # client protocol, Alpha/Beta HTTP clients, in-process mock app
  orchestration/  # fan-out, retries, idempotency keys, create-path runner
  agent/          # decide_case + Toolbelt
  eval_harness.py # fixture loader + live decide_case scoring
tests/            # pytest; defaults to in-memory SQLite
evals/fixtures/   # labeled mock cases (not production data)
```

## How to run

Python 3.12+. Docker Compose is only needed if you want the Postgres-backed app.

### App + Postgres (Compose)

```bash
cp .env.example .env   # optional; Compose sets DATABASE_URL for you
docker compose up --build
```

Smoke:

```bash
curl -s localhost:8000/health
curl -s localhost:8000/health/ready
curl -s -X POST localhost:8000/v1/cases \
  -H 'content-type: application/json' \
  -d '{"subject":"Hello case","payload":{"scenario":"happy","packet_complete":true}}'
curl -s -X POST localhost:8000/v1/cases/<id>/run-agent
```

OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

If you already ran the milestone-1 volume, recreate it after the portable schema change:

```bash
docker compose down -v && docker compose up --build
```

### Tests and evals (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests evals && ruff format --check src tests evals
mypy
pytest
python -m vendor_orchestrator.eval_harness
```

pytest and the eval harness use **in-memory SQLite**. They do not need Compose or Postgres.

To exercise the Postgres path instead:

```bash
docker compose up -d db
export TEST_DATABASE_URL=postgresql+asyncpg://vendor:vendor@localhost:5432/vendor_orchestrator
pytest
```

## Agent policy (what to defend)

Implemented in `src/vendor_orchestrator/agent/loop.py`:

1. If `payload.packet_complete` is explicitly `false`, escalate and do not call vendors.
2. Otherwise select vendors: honor `payload.vendors` when present; else call **Alpha only** (do not blindly hit every registered mock).
3. Fan-out goes through `Toolbelt.call_vendors` → `fan_out_vendors` (retries + idempotency reuse).
4. Any failed call or `signal != "clear"` → escalate. All clear → auto-resolve.

This is a mock-fixture policy, not a compliance product.

## Orchestration policy

Implemented in `src/vendor_orchestrator/orchestration/fanout.py`:

- Deduplicate vendor names, fan out concurrently, persist every attempt.
- Reuse a successful `vendor_calls` row with the same `build_idempotency_key` (no second mock HTTP hit).
- Retry timeouts / 429 / 5xx only, capped at 3 attempts with backoff. Do not retry ordinary 4xx.

## Eval scorecard (mock fixtures only)

Numbers below are copied from a local run of `python -m vendor_orchestrator.eval_harness` against `evals/fixtures/labeled_cases.jsonl`. They are **not** production metrics. Re-run the harness after changing the agent or fixtures; do not edit these cells by hand.

| Metric | Value | Notes |
| --- | --- | --- |
| Fixture count | 3 | `evals/fixtures/labeled_cases.jsonl` |
| Labels | escalate=2, auto_resolve=1 | Human labels, not model output |
| accuracy | *(from harness run)* | Computed on that run |
| precision(escalate) | *(from harness run)* | Computed on that run |
| precision(auto_resolve) | *(from harness run)* | Computed on that run |

These are **eval fixtures**, not production results. The README table is filled in after the harness prints real scores.

## Interview talking points (honest)

**Say:**

- I persist case state and every vendor attempt so a retry or a later agent pass is inspectable.
- The vendor client is a real HTTP client. The vendor itself is a mock so I can test orchestration without paid APIs.
- Idempotency keys are named per case/vendor/purpose so fan-out can skip a duplicate successful call.
- Retries are classified: transient 5xx/429/timeouts only.
- The metric I care about is precision on escalate vs auto-resolve, on labeled fixtures, because a sloppy auto-resolve is the costly mistake.
- The agent loop is mine: vendor selection and the decision rule. Scores come from running that loop on fixtures.

**Do not say:**

- This runs 80+ real compliance vendors.
- This is a KYB / AML / sanctions platform.
- We have production precision / recall / latency numbers (we do not).
- A 1.000 score on three hand-labeled mocks generalizes.

## Milestone checklist

- [x] M1: hello case API, one mock vendor, persistence, Compose, pytest, CI
- [x] M2: fan-out + retries + idempotency reuse
- [x] M3: agent loop chooses vendors and writes a decision
- [x] M4: harness reports precision from fixtures

## License

MIT. See `LICENSE`.
