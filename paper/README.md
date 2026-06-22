# FluxBoard Q2 Paper

LNCS paper: *Defense-in-Depth for LLM Agents over Enterprise Project Databases:
A Separation-of-Duties Multi-Agent Architecture for Safe Natural-Language
Querying and Mutation.*

## Files
- `fluxboard_q2.tex` — the manuscript (Springer LNCS, `llncs` class).
- `llncs.cls` — the document class (so the source compiles standalone / on Overleaf).
- `architecture_placeholder.png` — **TODO**: add the architecture figure referenced
  as `\label{fig:arch}`. Until then the figure box renders empty/missing.

## Building
No local LaTeX is required to edit. To produce the PDF, upload this folder to
Overleaf, or run a TeX distribution locally:

```bash
pdflatex fluxboard_q2.tex && pdflatex fluxboard_q2.tex
```

## Reproducing every number in the paper
All tables are produced by the evaluation harness in `apps/api/eval/`, offline
in mock mode (no Groq key, no live TiDB). The results are deterministic.

```bash
cd ../apps/api
PYTHONPATH=. python -m eval.run_experiments
```

This prints the summary and writes per-row CSVs to `apps/api/eval/results/`:

| Experiment | Output | Paper table |
|---|---|---|
| Security veto attack suite | `exp1_attack_suite.csv` | Table 1 |
| RBAC schema redaction | `exp2_rbac_redaction.csv` | Table 2 |
| Schema-pruning token reduction | `exp3_token_reduction.csv` | Table 3 |
| Orchestration latency | `exp4_latency.csv` | Table 4 |
| ORM mutation safety | (console) | Table 5 |

Latency (Table 4) is wall-clock and will vary slightly per machine; all other
numbers are deterministic.

## Honesty notes (kept consistent with the code)
- Token reduction is measured on actual rendered DDL with the `cl100k_base`
  sub-word tokenizer — **not** the table-count ratio the codebase exposes.
- Reported numbers are measured on FluxBoard's own 10-table schema; no figures
  are imported from the literature as our own results.
- The semantic-grounding component uses a deterministic hash-based embedding
  stand-in; the paper makes no accuracy claim for it (future work).
- "Speculative branch" execution is a logical read-only session, not a physical
  copy-on-write database branch.
