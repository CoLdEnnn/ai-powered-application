"""Explicit online setup: download the baseline GGUF and embedding model."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval import DEFAULT_EMBEDDING_MODEL, make_embedder, normalise_rows, sha256_file

MODEL_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.json")
    parser.add_argument("--skip-llm", action="store_true", help="Prepare only the embedding model.")
    parser.add_argument("--skip-embeddings", action="store_true", help="Prepare only the baseline GGUF.")
    parser.add_argument("--revision", default="main", help="Hugging Face revision for the baseline GGUF.")
    args = parser.parse_args()
    if args.skip_llm and args.skip_embeddings:
        parser.error("Both downloads are disabled; remove one of the skip flags.")
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = config_path.parent
    receipt: dict = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "network_setup": True}
    if not args.skip_llm:
        model_path = root / config.get("model_path", f"models/{MODEL_FILENAME}")
        if model_path.name != MODEL_FILENAME:
            raise ValueError(
                "This command downloads the official baseline only. The configured model filename "
                "is different; use --skip-llm to preserve an adapted model, or point model_path to "
                + MODEL_FILENAME + "."
            )
        from huggingface_hub import hf_hub_download
        model_path.parent.mkdir(parents=True, exist_ok=True)
        downloaded = Path(hf_hub_download(
            repo_id=MODEL_REPO, filename=MODEL_FILENAME, revision=args.revision,
            local_dir=str(model_path.parent),
        ))
        if downloaded.resolve() != model_path.resolve():
            raise RuntimeError("The model downloader returned an unexpected local path.")
        receipt["generation_model"] = {
            "repo_id": MODEL_REPO, "filename": MODEL_FILENAME,
            "revision_requested": args.revision, "path": str(downloaded.resolve()),
            "sha256": sha256_file(downloaded), "bytes": downloaded.stat().st_size,
        }
    if not args.skip_embeddings:
        name = config.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
        cache = root / config.get("embedding_cache", "models/embeddings")
        cache.mkdir(parents=True, exist_ok=True)
        embedder = make_embedder(name, cache, int(config.get("embedding_threads", 2)), local_files_only=False)
        vectors = normalise_rows(list(embedder.query_embed("AITU model setup check")))
        receipt["embedding_model"] = {"name": name, "cache_dir": str(cache.resolve()),
                                      "dimensions": int(vectors.shape[1]), "provider": "CPUExecutionProvider"}
    receipt_dir = root / "models"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / "setup_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "models_prepared", "receipt": str(receipt_path),
                      "next_step": "python scripts/build_index.py"}, indent=2))


if __name__ == "__main__":
    main()
