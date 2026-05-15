# DeepEvals Golden Set

This folder contains the initial golden dataset for evaluating the Multi DB React Agent.

## Files

- `golden_cases.json` - curated evaluation cases for SQL, MongoDB, handbook/RAG, mixed-source, and safety behavior.

## Intended Checks

- Tool routing: expected SQL, MongoDB, handbook, or mixed tool calls.
- Answer relevance: final answer should address the user question.
- RAG faithfulness: handbook answers should be grounded in retrieved context.
- Context relevancy: retrieved handbook chunks should match the question.
- Safety: destructive SQL and server-side JavaScript MongoDB operators should be rejected.

## Run Local Golden Evals

This runner executes each case against the current agent, checks expected tools and answer keywords, and writes reports under `src/DeepEvals/results`.

```powershell
uv run python src/DeepEvals/run_golden_eval.py
```

For a quick smoke run:

```powershell
uv run python src/DeepEvals/run_golden_eval.py --limit 3
```

The latest report is written to:

```text
src/DeepEvals/results/latest_eval_results.json
```

Timestamped reports are also kept as:

```text
src/DeepEvals/results/eval_results_YYYYMMDD_HHMMSS.json
```
