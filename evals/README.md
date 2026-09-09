# Evals

Precision, recall, and accuracy are computed by running `decide_case` on
**labeled mock fixtures** (`escalate` vs `auto_resolve`).

```bash
python -m vendor_orchestrator.eval_harness
```

The harness uses in-memory SQLite and the in-process mock vendors. It never
prints a production score. If you change the agent or the fixture file, re-run
the command and copy the printed numbers — do not invent them.

See `fixtures/README.md` and the scorecard section in the repository README.
