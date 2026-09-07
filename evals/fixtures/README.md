# Labeled eval fixtures

These rows are **hand-labeled mock cases**, not production traffic and not
model outputs.

| Field | Meaning |
| --- | --- |
| `id` | Stable fixture id |
| `subject` | Case title passed to `POST /v1/cases` |
| `payload` | JSON body stored on the case (`scenario` drives the mock vendor) |
| `expected_decision` | Human label: `escalate` or `auto_resolve` |
| `notes` | Why the label was applied |

The harness (`python -m vendor_orchestrator.eval_harness`) prints fixture
counts. Live precision appears only after `decide_case` is implemented and
wired into the harness. Do not paste invented percentages into the README
scorecard.
