"""Repo-root entry for the eval harness. Delegates to the installable module."""

from vendor_orchestrator.eval_harness import main

if __name__ == "__main__":
    raise SystemExit(main())
