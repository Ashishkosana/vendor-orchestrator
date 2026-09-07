# vendor-orchestrator

Portfolio project: a **case orchestration service**. A FastAPI app accepts a case, calls mock vendor HTTP APIs, persists case state in Postgres, and (later) lets an agent choose vendors and decide **escalate vs auto-resolve**. An eval harness scores that decision on **labeled mock fixtures**.

This is project #1 in a SWE I agent portfolio. The interview bridge is:

> orchestration + retries + case state + evals

It is **not** a KYB, AML, or sanctions product. Vendors here are mocks. There is no production traffic, no claimed vendor count, and no invented accuracy numbers.

## What works today (milestone 1)

| Piece | Status |
| --- | --- |
| `POST /v1/cases` / `GET /v1/cases/{id}` | Working |
| One mock vendor HTTP client (Alpha, in-process ASGI) | Working |
| Postgres case + vendor-call persistence | Working |
| Docker Compose (`app` + `db`) | Working |
| pytest + GitHub Actions (ruff / mypy / pytest) | Working |
| Multi-vendor fan-out, retries, idempotency reuse | **Stub** (`YOU IMPLEMENT`) |
| Agent decision / tool-use loop | **Stub** (`YOU IMPLEMENT`) |
| Eval harness + labeled fixtures | Scaffold (metrics `—` until the agent exists) |

## Architecture

```mermaid
flowchart LR
    Client[HTTP client] --> API[FastAPI case API]
    API --> PG[(Postgres\ncases + vendor_calls)]
    API --> Runner[Milestone-1 runner]
    Runner --> Alpha[Mock vendor Alpha\nHTTP client]
    Alpha --> Mock[In-process mock app]
    API -.-> Agent["Agent loop\nYOU IMPLEMENT"]
    Agent -.-> Tools[Toolbelt]
    Tools -.-> Fanout["Fan-out + retries\nYOU IMPLEMENT"]
    Fanout -.-> Alpha
    Evals[Eval harness] -.-> Agent
    Fixtures[Labeled mock fixtures] --> Evals
```

Create-case path (milestone 1): persist an `open` case → call Alpha over HTTP → persist a `vendor_calls` row → set status to `vendor_checked` (or `vendor_failed`). **`decision` stays null.** Choosing vendors and escalate/auto-resolve is the agent loop, which is unfinished on purpose.

## Repository layout

```
src/vendor_orchestrator/
  api/            # health + case routes
  vendors/        # client protocol, Alpha client, in-process mock app
  orchestration/  # working M1 runner; fan-out / retry stubs
  agent/          # YOU IMPLEMENT: decide_case
  eval_harness.py # fixture loader + precision helper
tests/
evals/fixtures/   # labeled mock cases (not production data)
```

## How to run

Python 3.12+ and Docker Compose.

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
  -d '{"subject":"Hello case","payload":{"scenario":"happy"}}'
```

OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

Local tests (Postgres must be reachable at `DATABASE_URL`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d db
export DATABASE_URL=postgresql+asyncpg://vendor:vendor@localhost:5432/vendor_orchestrator
ruff check src tests evals && ruff format --check src tests evals
mypy
pytest
```

Eval scorecard (fixture counts only until the agent exists):

```bash
python -m vendor_orchestrator.eval_harness
```

## What Ashish must implement

Search the repo for `YOU IMPLEMENT`. The three unfinished cores:

1. **`src/vendor_orchestrator/agent/loop.py` — `decide_case`**
   Read the case, pick vendors via `Toolbelt`, return `escalate` or `auto_resolve` plus a short reason. This is the piece you must be able to defend. Do not accept a ghostwritten policy you cannot explain.
2. **`src/vendor_orchestrator/orchestration/fanout.py`**
   Concurrent multi-vendor calls, retry only transient failures, reuse `build_idempotency_key` so a retry is the same logical request.
3. **`eval_harness.py` `main`**
   Run `decide_case` on each labeled fixture and pass predictions into `precision_by_label`. Until then the scorecard prints `—`.

`POST /v1/cases/{id}/run-agent` already returns **501** until `decide_case` exists.

## Eval scorecard (mock fixtures only)

| Metric | Value | Notes |
| --- | --- | --- |
| Fixture count | 3 | `evals/fixtures/labeled_cases.jsonl` |
| Labels | escalate=2, auto_resolve=1 | Human labels, not model output |
| precision(escalate) | — | Agent loop not implemented |
| precision(auto_resolve) | — | Agent loop not implemented |

These are **eval fixtures**, not production results. Do not replace `—` with a number unless it came from running the harness on these (or newer labeled) fixtures.

## Interview talking points (honest)

**Say:**

- I persist case state and every vendor attempt so a retry or a later agent pass is inspectable.
- The vendor client is a real HTTP client. The vendor itself is a mock so I can test orchestration without paid APIs.
- Idempotency keys are named per case/vendor/purpose so fan-out can skip a duplicate successful call.
- The metric I care about is precision on escalate vs auto-resolve, on labeled fixtures, because a sloppy auto-resolve is the costly mistake.
- The agent loop is mine: vendor selection and the decision rule.

**Do not say:**

- This runs 80+ real compliance vendors.
- This is a KYB / AML / sanctions platform.
- We have production precision / recall / latency numbers (we do not).
- The scaffold's empty agent is a finished model.

## Milestone checklist

- [x] M1: hello case API, one mock vendor, Postgres, Compose, pytest, CI
- [ ] M2: fan-out + retries + idempotency reuse
- [ ] M3: agent loop chooses vendors and writes a decision
- [ ] M4: harness reports precision from fixtures (only after M3)

## License

MIT. See `LICENSE`.
