"""Build the evidence index using an already downloaded embedding model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval import DEFAULT_EMBEDDING_MODEL, build_index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.json")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = config_path.parent
    manifest = build_index(
        corpus_path=root / config.get("corpus_path", "data/rag_corpus_en.jsonl"),
        index_dir=root / config.get("index_dir", "index"),
        embedding_model=config.get("embedding_model", DEFAULT_EMBEDDING_MODEL),
        cache_dir=root / config.get("embedding_cache", "models/embeddings"),
        threads=int(config.get("embedding_threads", 2)),
        batch_size=args.batch_size,
    )
    print(json.dumps({"status": "built", "index_dir": str(root / config.get("index_dir", "index")),
                      "contexts": manifest["count"], "dimensions": manifest["dimensions"],
                      "corpus_sha256": manifest["corpus_sha256"],
                      "max_reported_embedding_tokens": manifest["max_reported_embedding_tokens"]}, indent=2))


if __name__ == "__main__":
    main()
