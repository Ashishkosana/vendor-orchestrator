# Evals

Precision is computed on **labeled mock fixtures** for two decisions:
`escalate` vs `auto_resolve`.

Until the agent loop exists, `python -m vendor_orchestrator.eval_harness`
prints a scorecard with `—` for live metrics. That is intentional.

See `fixtures/README.md` and the scorecard section in the repository README.
