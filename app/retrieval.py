"""Local evidence retrieval with FastEmbed and a small exact cosine index."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import threading
from typing import Any
import uuid

import numpy as np

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
INDEX_SCHEMA_VERSION = 1
# BGE-small accepts 512 tokens. Leave room for special tokens/model prefixes.
SAFE_EMBEDDING_TOKENS = 480


class IndexValidationError(RuntimeError):
    """An index is missing, stale, corrupt or incompatible with its corpus."""


class RetrievalInputError(ValueError):
    """A question cannot be embedded without losing part of its text."""


class RetrievalUnavailable(RuntimeError):
    """The local embedding runtime is missing or cannot produce valid vectors."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_corpus(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"Corpus line {number} must be a JSON object.")
            cid = record.get("context_id")
            if not isinstance(cid, str) or not cid or cid in seen:
                raise ValueError(f"Missing or duplicate context_id on line {number}.")
            if not isinstance(record.get("text"), str) or not record["text"].strip():
                raise ValueError(f"Context {cid} has no evidence text.")
            if record.get("audience") not in {"applicant", "current_student", "shared"}:
                raise ValueError(f"Context {cid} has an unsupported audience.")
            seen.add(cid)
            records.append(record)
    if not records:
        raise ValueError("The retrieval corpus is empty.")
    return records


def make_embedder(model_name: str, cache_dir: Path, threads: int = 2,
                  *, local_files_only: bool = True) -> Any:
    """Import the embedding runtime only when needed; app calls stay offline."""
    if not isinstance(threads, int) or threads < 1:
        raise ValueError("Embedding threads must be a positive integer.")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    if local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError("Install the project's inference dependencies first.") from exc
    try:
        return TextEmbedding(
            model_name=model_name,
            cache_dir=str(Path(cache_dir).resolve()),
            threads=threads,
            providers=["CPUExecutionProvider"],
            local_files_only=local_files_only,
        )
    except Exception as exc:
        if local_files_only:
            raise RuntimeError(
                "The local embedding model could not be loaded. Run "
                "python scripts/setup_models.py while online, then try again. "
                "Normal retrieval never downloads a missing model."
            ) from exc
        raise


def check_embedding_length(embedder: Any, text: str, label: str) -> int:
    """Reject near-limit text rather than silently embedding a truncated tail."""
    if not hasattr(embedder, "token_count"):
        raise RuntimeError("This project requires FastEmbed with the token_count API (0.9 series).")
    count = int(embedder.token_count(text))
    # A tokenizer that truncates at 512 still returns a value above this boundary.
    if count >= SAFE_EMBEDDING_TOKENS:
        raise ValueError(
            f"{label} reaches {count} embedding tokens; the safe limit is "
            f"{SAFE_EMBEDDING_TOKENS - 1}. No text was truncated by this project. "
            "Review the evidence segmentation or use a suitable longer-context model."
        )
    return count


def normalise_rows(values: np.ndarray) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("Embedding output must be a nonempty two-dimensional matrix.")
    if not np.isfinite(matrix).all():
        raise ValueError("Embedding output contains non-finite values.")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms <= 1e-12):
        raise ValueError("Embedding output contains a zero-length vector.")
    return np.asarray(matrix / norms, dtype=np.float32)


def build_index(corpus_path: Path, index_dir: Path, embedding_model: str,
                cache_dir: Path, threads: int = 2, batch_size: int = 16,
                *, embedder: Any = None) -> dict[str, Any]:
    """Build the index from complete evidence texts, preserving their row order."""
    if batch_size < 1:
        raise ValueError("Batch size must be positive.")
    corpus_path, index_dir = Path(corpus_path), Path(index_dir)
    before_hash = sha256_file(corpus_path)
    records = read_corpus(corpus_path)
    embedder = embedder if embedder is not None else make_embedder(
        embedding_model, cache_dir, threads, local_files_only=True
    )
    lengths = [check_embedding_length(embedder, r["text"], r["context_id"]) for r in records]
    vectors = list(embedder.passage_embed([r["text"] for r in records], batch_size=batch_size))
    matrix = normalise_rows(np.asarray(vectors, dtype=np.float32))
    if matrix.shape[0] != len(records):
        raise ValueError("The embedding runtime did not return one vector per context.")
    if sha256_file(corpus_path) != before_hash:
        raise RuntimeError("The corpus changed while indexing. Run the command again.")
    index_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    matrix_tmp = index_dir / f"embeddings-{token}.tmp"
    manifest_tmp = index_dir / f"manifest-{token}.tmp"
    try:
        with matrix_tmp.open("wb") as handle:
            np.save(handle, matrix, allow_pickle=False)
        try:
            version = importlib.metadata.version("fastembed")
        except importlib.metadata.PackageNotFoundError:
            version = "test-double"
        manifest = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "embedding_model": embedding_model,
            "fastembed_version": version,
            "embedding_method": "passage_embed",
            "normalisation": "l2",
            "corpus_sha256": before_hash,
            "context_ids": [r["context_id"] for r in records],
            "count": len(records),
            "dimensions": int(matrix.shape[1]),
            "matrix_file": "embeddings.npy",
            "matrix_sha256": sha256_file(matrix_tmp),
            "max_reported_embedding_tokens": max(lengths),
            "safe_embedding_token_limit_exclusive": SAFE_EMBEDDING_TOKENS,
        }
        manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        matrix_tmp.replace(index_dir / "embeddings.npy")
        manifest_tmp.replace(index_dir / "manifest.json")
        return manifest
    finally:
        matrix_tmp.unlink(missing_ok=True)
        manifest_tmp.unlink(missing_ok=True)


class Retriever:
    def __init__(self, corpus_path: Path, index_dir: Path, embedding_model: str,
                 cache_dir: Path, threads: int = 2, *, embedder: Any = None):
        self.corpus_path = Path(corpus_path)
        self.index_dir = Path(index_dir)
        self.embedding_model = embedding_model
        self.cache_dir = Path(cache_dir)
        self.threads = threads
        self._embedder = embedder
        self._embedding_lock = threading.Lock()
        self.records = read_corpus(self.corpus_path)
        try:
            self.manifest = json.loads((self.index_dir / "manifest.json").read_text(encoding="utf-8"))
            if self.manifest.get("schema_version") != INDEX_SCHEMA_VERSION:
                raise ValueError("Unsupported index schema.")
            if self.manifest.get("embedding_model") != embedding_model:
                raise ValueError("The configured embedding model differs from the index model.")
            if self.manifest.get("corpus_sha256") != sha256_file(self.corpus_path):
                raise ValueError("The corpus has changed since this index was built.")
            if self.manifest.get("context_ids") != [r["context_id"] for r in self.records]:
                raise ValueError("Context order does not match the index manifest.")
            if self.manifest.get("normalisation") != "l2" or self.manifest.get("embedding_method") != "passage_embed":
                raise ValueError("Unsupported embedding normalisation or method.")
            if self.manifest.get("matrix_file") != "embeddings.npy":
                raise ValueError("Unexpected index matrix filename.")
            matrix_path = self.index_dir / "embeddings.npy"
            if sha256_file(matrix_path) != self.manifest.get("matrix_sha256"):
                raise ValueError("The embedding matrix does not match its recorded hash.")
            self.matrix = np.load(matrix_path, allow_pickle=False)
            expected = (len(self.records), self.manifest.get("dimensions"))
            if self.matrix.shape != expected or self.manifest.get("count") != len(self.records):
                raise ValueError("Embedding shape or row count does not match the manifest.")
            if self.matrix.dtype != np.float32 or not np.isfinite(self.matrix).all():
                raise ValueError("The matrix must contain finite float32 embeddings.")
            if not np.allclose(np.linalg.norm(self.matrix, axis=1), 1.0, atol=1e-4):
                raise ValueError("The stored vectors are not L2-normalised.")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise IndexValidationError(
                f"Cannot use the retrieval index: {exc} "
                "Run python scripts/build_index.py to rebuild it."
            ) from exc

    def _embed_question(self, question: str) -> np.ndarray:
        with self._embedding_lock:
            try:
                if self._embedder is None:
                    self._embedder = make_embedder(
                        self.embedding_model, self.cache_dir, self.threads, local_files_only=True
                    )
            except Exception as exc:
                raise RetrievalUnavailable(str(exc)) from exc
            try:
                check_embedding_length(self._embedder, question, "Question")
            except ValueError as exc:
                raise RetrievalInputError(
                    "The question is too long for the embedding model. "
                    "Please ask a shorter question; no text was truncated."
                ) from exc
            except Exception as exc:
                raise RetrievalUnavailable("The local embedding tokenizer is unavailable.") from exc
            try:
                vectors = list(self._embedder.query_embed(question))
                if len(vectors) != 1:
                    raise ValueError("Expected one query vector.")
                query = normalise_rows(np.asarray(vectors, dtype=np.float32))[0]
                if query.shape[0] != self.matrix.shape[1]:
                    raise ValueError("Query dimensions differ from the stored index.")
                return query
            except Exception as exc:
                raise RetrievalUnavailable(
                    "The local embedding runtime could not produce a valid query vector. "
                    "Check the model cache and rebuild the index if its model changed."
                ) from exc

    def warm_up(self) -> None:
        """Fail startup clearly if the offline model cannot serve this index."""
        self._embed_question("University information")

    def search(self, question: str, audience: str = "all", top_k: int = 3,
               min_similarity: float | None = None) -> list[dict[str, Any]]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Enter a nonempty question.")
        if audience not in {"all", "applicant", "current_student"}:
            raise ValueError("Audience must be all, applicant or current_student.")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k must be a positive integer.")
        if min_similarity is not None and (
            not math.isfinite(min_similarity) or not -1 <= min_similarity <= 1
        ):
            raise ValueError("min_similarity must be between -1 and 1, or None.")
        indices = [i for i, record in enumerate(self.records)
                   if audience == "all" or record["audience"] in {audience, "shared"}]
        if not indices:
            return []
        query = self._embed_question(question.strip())
        scores = np.clip(self.matrix[indices] @ query, -1.0, 1.0)
        order = np.argsort(-scores, kind="stable")
        output: list[dict[str, Any]] = []
        for position in order:
            score = float(scores[position])
            if min_similarity is not None and score < min_similarity:
                continue
            item = copy.deepcopy(self.records[indices[int(position)]])
            item["score"] = score
            output.append(item)
            if len(output) >= top_k:
                break
        return output
