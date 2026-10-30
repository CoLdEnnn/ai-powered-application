"""Measure exact-context-ID retrieval proxies; validation is the default split."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval import DEFAULT_EMBEDDING_MODEL, Retriever, sha256_file


def load_queries(path: Path, split: str) -> list[dict]:
    queries = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        raw = json.loads(line)
        if split == "test":
            query = {"id": raw["id"], "question": raw["question"],
                     "expected_context_ids": raw["expected_context_ids"],
                     "audience": raw.get("audience", "all"),
                     "behavior": raw.get("expected_behavior", "unknown")}
        else:
            if raw.get("metadata", {}).get("split") != "validation":
                raise ValueError(f"Line {number} is not labelled as validation.")
            user_messages = [m["content"] for m in raw["messages"] if m["role"] == "user"]
            if not user_messages:
                raise ValueError(f"Line {number} has no user question.")
            _, marker, question = user_messages[-1].rpartition("\nQUESTION\n")
            if not marker or not question.strip():
                raise ValueError(f"Line {number} has no QUESTION delimiter.")
            meta = raw["metadata"]
            query = {"id": raw["id"], "question": question.strip(),
                     "expected_context_ids": meta["context_ids"],
                     "audience": meta.get("audience", "all"),
                     "behavior": meta.get("behavior", "unknown")}
        if query["id"] in seen:
            raise ValueError(f"Repeated evaluation ID: {query['id']}")
        if not query["expected_context_ids"]:
            raise ValueError(f"No expected evidence IDs for {query['id']}.")
        seen.add(query["id"])
        queries.append(query)
    if not queries:
        raise ValueError("The evaluation file is empty.")
    return queries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.json")
    parser.add_argument("--split", choices=["validation", "test"], default="validation",
                        help="Choose test explicitly only for a frozen final evaluation.")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-similarity", type=float, default=None,
                        help="Optional previously calibrated cutoff; this is not a confidence probability.")
    parser.add_argument("--use-audience", action="store_true",
                        help="Filter using the supplied audience labels; shared cases search all audiences.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = config_path.parent
    corpus_path = root / config.get("corpus_path", "data/rag_corpus_en.jsonl")
    data_dir = corpus_path.parent
    query_path = data_dir / ("validation.jsonl" if args.split == "validation" else "retrieval_test.jsonl")
    queries = load_queries(query_path, args.split)
    retriever = Retriever(corpus_path, root / config.get("index_dir", "index"),
                          config.get("embedding_model", DEFAULT_EMBEDDING_MODEL),
                          root / config.get("embedding_cache", "models/embeddings"),
                          int(config.get("embedding_threads", 2)))
    known_ids = {r["context_id"] for r in retriever.records}
    results = []
    for query in queries:
        expected = set(query["expected_context_ids"])
        if not expected <= known_ids:
            raise ValueError(f"Expected context missing from corpus for {query['id']}.")
        audience = query["audience"] if args.use_audience and query["audience"] != "shared" else "all"
        found = retriever.search(query["question"], audience=audience,
                                 top_k=args.top_k, min_similarity=args.min_similarity)
        ranks = [rank for rank, item in enumerate(found, 1) if item["context_id"] in expected]
        results.append({
            **query, "applied_audience_filter": audience,
            "retrieved": [{"context_id": item["context_id"], "score": item["score"]} for item in found],
            "hit": bool(ranks), "reciprocal_rank_at_k": 1.0 / min(ranks) if ranks else 0.0,
            "exact_id_recall_at_k": len({r["context_id"] for r in found} & expected) / len(expected),
        })
    timestamp = datetime.now(timezone.utc)
    count = len(results)
    report = {
        "created_at_utc": timestamp.isoformat(), "split": args.split,
        "query_count": count, "top_k": args.top_k, "min_similarity": args.min_similarity,
        "audience_filter_from_labels": args.use_audience,
        "embedding_model": retriever.embedding_model,
        "corpus_sha256": retriever.manifest["corpus_sha256"],
        "query_file_sha256": sha256_file(query_path),
        "hits": sum(r["hit"] for r in results),
        "hit_at_k_exact_id_proxy": sum(r["hit"] for r in results) / count,
        "mrr_at_k_exact_id_proxy": sum(r["reciprocal_rank_at_k"] for r in results) / count,
        "mean_recall_at_k_exact_id_proxy": sum(r["exact_id_recall_at_k"] for r in results) / count,
        "behavior_counts": dict(Counter(r["behavior"] for r in results)),
        "interpretation": "Exact expected-context-ID proxies only. Other passages may provide equivalent evidence; review such cases manually. No answer quality, factual correctness or user-satisfaction result is measured.",
        "results": results,
    }
    output = args.output or root / "reports" / f"retrieval_{args.split}_k{args.top_k}_{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "results"} | {"report": str(output)}, indent=2))


if __name__ == "__main__":
    main()
