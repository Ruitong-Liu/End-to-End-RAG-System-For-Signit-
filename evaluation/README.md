# Synthetic Evaluation Examples

`demo.jsonl` contains eight hand-checked questions for the synthetic document in `data/demo/`. They cover factual, procedural, ambiguous, and unanswerable cases. This small dataset is a smoke fixture, not a business benchmark. Internal evaluation datasets and results are not distributed.

## Run retrieval checks

```sh
cd backend
../.venv/bin/python -m app.evaluate --dataset ../evaluation/demo.jsonl --modes bm25 --output ../evaluation/results/demo-bm25.json
# Requires the optional model dependencies and downloaded BGE weights:
../.venv/bin/python -m app.evaluate --dataset ../evaluation/demo.jsonl --output ../evaluation/results/demo-full.json
```

The evaluator fixes retrieval depth of the returned results to five passages for metric calculation. Document Recall@5 measures the fraction of relevant source documents represented in those passages, including duplicate-source aliases. MRR uses the rank of the first relevant passage. Cases without relevant-document labels are excluded from retrieval aggregates and require separate refusal/clarification assessment.

Answer correctness requires human judgments against reference answers and evidence; the evaluator does not invent correctness scores. The output leaves unavailable correctness/cost values unset. Citation-number validation is not a substitute for semantic correctness.

Cold model loading is included in applicable CLI requests. Single-process p95 values from a small run are not a production SLA or a fair comparison between differently warmed modes. Use appropriately controlled experiments for latency and cost analysis. Default provider prices are unset.

For other datasets, provide JSONL records with `id`, `question`, `category`, `relevant_sources`, `reference_answer`, and `reviewed`. Gold source paths must match the selected corpus. Review labels before setting `reviewed: true`; draft labels are rejected unless explicitly allowed. Local datasets and generated results are ignored by Git.
