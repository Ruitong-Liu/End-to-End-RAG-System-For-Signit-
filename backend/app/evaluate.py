"""Retrieval evaluation; no LLM judge or invented correctness labels."""
import argparse
import json
import statistics
import time
from pathlib import Path
from .config import Settings
from .retrieval import Retriever

def metrics(retrieved, relevant):
    relevant = set(relevant)
    if not relevant:
        return None, None
    # Document-level recall and MRR; duplicates from the same document count once.
    found = set()
    rr = 0.0
    for rank, hit in enumerate(retrieved, 1):
        matched = ({hit["source"]} | set(hit.get("aliases", []))) & relevant
        found |= matched
        if matched and not rr:
            rr = 1 / rank
    return len(found)/len(relevant), rr

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--modes", nargs="+", default=["dense", "hybrid", "hybrid_rerank"])
    p.add_argument("--allow-draft", action="store_true")
    args = p.parse_args()
    cases = [json.loads(l) for l in args.dataset.read_text().splitlines() if l.strip()]
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise SystemExit("Empty dataset or duplicate IDs")
    if not args.allow_draft and any(not c.get("reviewed") for c in cases):
        raise SystemExit("Dataset contains unreviewed candidates. Review labels or use --allow-draft for exploratory results.")
    settings = Settings(top_k=5, cache_size=0)
    retriever = Retriever(settings)
    known = {s for c in retriever.chunks for s in [c.source, *c.aliases]}
    missing = {s for c in cases for s in c["relevant_sources"]} - known
    if missing:
        raise SystemExit(f"Dataset does not match corpus: {sorted(missing)}")
    results = {"label_status": "draft" if any(not c.get("reviewed") for c in cases) else "reviewed",
        "corpus_fingerprint": retriever.fingerprint, "settings": settings.model_dump(exclude={"deepseek_api_key"}),
        "answer_correctness": None, "cost_per_query_usd": None,
        "notes": "Retrieval-only run. Document-level metrics exclude cases without relevant sources. p95 includes lazy model loading on first query. Correctness requires separate human grading.", "modes": {}}
    for mode in args.modes:
        rows = []
        for case in cases:
            start = time.perf_counter()
            hits = retriever.search(case["question"], mode)
            elapsed = (time.perf_counter()-start)*1000
            recall, rr = metrics(hits, case["relevant_sources"])
            rows.append({"id": case["id"], "category": case["category"], "recall_at_5": recall,
                "reciprocal_rank": rr, "latency_ms": elapsed, "retrieved": [h["source"] for h in hits]})
        labeled = [r for r in rows if r["recall_at_5"] is not None]
        times = sorted(r["latency_ms"] for r in rows)
        results["modes"][mode] = {"recall_at_5": statistics.mean(r["recall_at_5"] for r in labeled) if labeled else None,
            "mrr": statistics.mean(r["reciprocal_rank"] for r in labeled) if labeled else None,
            "p95_latency_ms": times[max(0, __import__('math').ceil(.95*len(times))-1)], "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"Saved measured results: {args.output}")

if __name__ == "__main__":
    main()
