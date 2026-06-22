"""Reproducible evaluation harness for the FluxBoard multi-agent safety paper.

This package produces the quantitative tables reported in the paper:

* exp1 -- security veto attack suite (block-rate vs a naive baseline)
* exp2 -- RBAC schema-redaction correctness (viewer vs admin)
* exp3 -- schema-pruning token reduction + table recall
* exp4 -- orchestration latency (cache-cold vs cache-warm)
* exp5 -- ORM-only mutation safety guarantees

All experiments run fully offline in mock mode (no Groq key, no live TiDB),
so the numbers are deterministic and reproducible. Run with:

    python -m eval.run_experiments
"""
