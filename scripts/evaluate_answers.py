"""Collect local RAG answers for manual baseline-versus-adapted comparison.

Validation is the default. Select --split test only after choices are frozen.
Run baseline and adapted servers in sequence with otherwise identical settings.
This script collects evidence; it does not automatically grade answer quality.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings, require_loopback_url
from app.prompting import citation_check


RUBRIC_KEYS = (
    "factual_grounding", "applicability", "expected_behaviour",
    "evidence_citation", "practical_clarity",
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path, *, required=True):
    path = Path(path).resolve()
    if not path.is_file():
        if required:
            raise FileNotFoundError(f"Required evaluation artifact is missing: {path}")
        return {"path": str(path), "exists": False, "sha256": None}
    return {"path": str(path), "exists": True, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def string_list(value, name, example_id):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{example_id}: {name} must be a list of strings.")
    return value


def load_examples(path, split):
    examples = []
    ids = set()
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Line {line_number} must be an object.")
            example_id = row.get("id")
            if not isinstance(example_id, str) or not example_id or example_id in ids:
                raise ValueError(f"Missing or duplicate example ID at line {line_number}.")
            ids.add(example_id)
            metadata = row.get("metadata", {})
            if not isinstance(metadata, dict) or metadata.get("split") != split:
                raise ValueError(f"{example_id}: metadata.split must be {split!r}.")
            if "messages" in row:
                messages = row["messages"]
                if not isinstance(messages, list) or len(messages) != 3 or any(not isinstance(item, dict) for item in messages):
                    raise ValueError(f"{example_id}: expected system, user, assistant messages.")
                if [item.get("role") for item in messages] != ["system", "user", "assistant"]:
                    raise ValueError(f"{example_id}: expected system, user, assistant messages.")
                user = messages[1].get("content")
                if not isinstance(user, str):
                    raise ValueError(f"{example_id}: user content must be text.")
                context_text, marker, question = user.rpartition("\nQUESTION\n")
                if not marker:
                    raise ValueError(f"{example_id}: user content has no QUESTION delimiter.")
                reference = messages[2].get("content")
                reference_context = context_text
            else:
                question = row.get("question")
                reference = row.get("reference_answer")
                reference_context = row.get("contexts", [])
            if not isinstance(question, str) or not question.strip():
                raise ValueError(f"{example_id}: missing question.")
            if not isinstance(reference, str) or not reference.strip():
                raise ValueError(f"{example_id}: missing reference answer.")
            audience = metadata.get("audience", "all")
            if audience not in {"all", "shared", "applicant", "current_student"}:
                raise ValueError(f"{example_id}: unsupported audience {audience!r}.")
            examples.append({
                "id": example_id, "question": question.strip(),
                "reference_answer": reference, "reference_context": reference_context,
                "context_ids": string_list(row.get("context_ids", metadata.get("context_ids", [])), "context_ids", example_id),
                "source_ids": string_list(metadata.get("source_ids", []), "source_ids", example_id),
                "behavior": row.get("expected_behavior", metadata.get("behavior", "unknown")),
                "audience": audience, "metadata": metadata,
            })
    if not examples:
        raise ValueError("The selected evaluation file is empty.")
    return examples


def read_health(client, expected_variant):
    response = client.get("/api/health")
    response.raise_for_status()
    health = response.json()
    if not isinstance(health, dict) or health.get("status") != "ready":
        raise RuntimeError("The local application is not ready. Start the app and model before collecting answers.")
    if health.get("model_variant") != expected_variant:
        raise RuntimeError(
            f"Server variant {health.get('model_variant')!r} differs from the config's {expected_variant!r}. "
            "Restart the application with the intended configuration."
        )
    return health


def artifact_snapshot(settings, config_path, dataset_path):
    records = {
        "config": file_record(config_path), "dataset": file_record(dataset_path),
        "corpus": file_record(settings.corpus_path),
        "system_prompt": file_record(settings.system_prompt_path),
        "source_catalog": file_record(settings.source_catalog_path),
        "index_manifest": file_record(settings.index_dir / "manifest.json"),
        "model_gguf": file_record(settings.model_path, required=False),
        "collector_script": file_record(Path(__file__)),
    }
    manifest = json.loads((settings.index_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("matrix_file") != "embeddings.npy":
        raise ValueError("The index manifest has an unexpected matrix filename.")
    records["index_matrix"] = file_record(settings.index_dir / "embeddings.npy")
    if manifest.get("corpus_sha256") != records["corpus"]["sha256"]:
        raise ValueError("The corpus hash differs from the index manifest; rebuild the index.")
    if manifest.get("matrix_sha256") != records["index_matrix"]["sha256"]:
        raise ValueError("The index matrix hash differs from its manifest.")
    if manifest.get("embedding_model") != settings.embedding_model:
        raise ValueError("The configured embedding model differs from the index manifest.")
    return records, manifest


def empty_result(example, applied_audience):
    return {
        **example, "applied_audience_filter": applied_audience,
        "generation": None, "retrieved_context_ids": [], "retrieved_source_ids": [],
        "retrieved_sources": [], "citation_membership": None, "server_citation_status": None,
        "timings": {"client_round_trip_seconds": None, "server_total_seconds": None},
        "used_model": None, "model_variant": None, "input_tokens": None,
        "usage": None, "warnings": [], "error": None,
        "manual_rubric_scores": {name: None for name in RUBRIC_KEYS},
        "reviewer": None, "reviewer_notes": None,
    }


def collect_one(client, example, expected_variant, *, use_audience=False):
    audience = example["audience"] if use_audience and example["audience"] != "shared" else "all"
    result = empty_result(example, audience)
    started = time.perf_counter()
    response = None
    try:
        # Never send the reference answer or intended evidence to the application.
        response = client.post("/api/chat", json={"question": example["question"], "audience": audience})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str):
            raise ValueError("The local API did not return an answer string.")
        sources = payload.get("sources", [])
        if not isinstance(sources, list) or any(
            not isinstance(source, dict) or not isinstance(source.get("context_id"), str) for source in sources
        ):
            raise ValueError("The local API returned invalid source records.")
        result.update({
            "generation": payload["answer"], "retrieved_sources": sources,
            "retrieved_context_ids": [source["context_id"] for source in sources],
            "retrieved_source_ids": list(dict.fromkeys(
                source_id for source in sources for source_id in (source.get("source_ids") or [])
            )),
            "used_model": payload.get("used_model"), "model_variant": payload.get("model_variant"),
            "input_tokens": payload.get("input_tokens"), "usage": payload.get("usage"),
            "warnings": payload.get("warnings", []),
            "server_citation_status": payload.get("citation_status"),
            "citation_membership": {
                **citation_check(payload["answer"], sources),
                "claim_support_checked": False, "is_answer_quality_score": False,
            },
        })
        result["timings"]["server_total_seconds"] = payload.get("timing_seconds")
        if payload.get("model_variant") != expected_variant:
            result["error"] = {
                "type": "ModelVariantChanged", "message": "The response model variant differs from the evaluated configuration.",
            }
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:1000]}
        if response is not None:
            error["http_status"] = response.status_code
            try:
                detail = response.json()
                error["response_detail"] = str(detail.get("detail", detail) if isinstance(detail, dict) else detail)[:1000]
            except ValueError:
                error["response_detail"] = response.text[:1000]
        result["error"] = error
    finally:
        result["timings"]["client_round_trip_seconds"] = round(time.perf_counter() - started, 6)
    return result


def save_report(path, report):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.json", help="The same configuration used to start the running app.")
    parser.add_argument("--split", choices=("validation", "test"), default="validation", help="Test is explicit and reserved for a frozen final comparison.")
    parser.add_argument("--limit", type=int, help="Collect only the first N rows; labels the report as a smoke/subset run.")
    parser.add_argument("--use-audience", action="store_true", help="Use supplied audience labels as filters; otherwise search all audiences.")
    parser.add_argument("--server-url", help="Optional numeric-loopback app URL; defaults to the configured app host/port.")
    parser.add_argument("--output", type=Path, help="A new JSON report path; defaults to reports/answers_<variant>_<split>_<UTC>.json.")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be a positive integer.")
    try:
        import httpx

        config_path = args.config.resolve()
        settings = Settings.load(config_path)
        base_url = require_loopback_url(args.server_url or f"http://{settings.host}:{settings.port}")
        dataset_path = settings.corpus_path.parent / f"{args.split}.jsonl"
        examples = load_examples(dataset_path, args.split)
        selected = examples if args.limit is None else examples[:args.limit]
        timestamp = datetime.now(timezone.utc)
        output = (args.output or settings.root / "reports" / (
            f"answers_{settings.model_variant}_{args.split}_{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        )).resolve()
        if output.exists():
            raise FileExistsError(f"Report already exists: {output}. Choose a new --output path.")
        with httpx.Client(
            base_url=base_url, trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(settings.request_timeout_seconds + 15, connect=5.0),
        ) as client:
            health = read_health(client, settings.model_variant)
            artifacts, index_manifest = artifact_snapshot(settings, config_path, dataset_path)
            report = {
                "schema_version": 1, "status": "collecting", "started_at_utc": utc_now(),
                "split": args.split, "dataset_total_rows": len(examples), "selected_rows": len(selected),
                "limit": args.limit, "purpose": "smoke_or_subset" if args.limit is not None else "full_split_collection",
                "model_variant": settings.model_variant, "server_url": base_url, "server_status_at_start": health,
                "server_status_at_end": None, "audience_filter_from_labels": args.use_audience,
                "config": json.loads(config_path.read_text(encoding="utf-8")),
                "artifact_hashes": artifacts, "index_manifest": index_manifest,
                "versions": {"python": platform.python_version(), "httpx": importlib.metadata.version("httpx")},
                "configuration_binding_note": (
                    "The supplied local config and files are recorded. The health API confirms readiness and variant, "
                    "but does not attest every running server setting or loaded file hash. Start the app with this "
                    "config and keep artifacts unchanged during collection."
                ),
                "comparison_instructions": (
                    "Run baseline and adapted sequentially by restarting with the intended model/config. Keep corpus, "
                    "index, system prompt, question order, audience policy, context budget, decoding settings, and "
                    "hardware conditions matched. Compare the recorded hashes and settings before interpreting differences."
                ),
                "scoring_policy": (
                    "No answer-quality grading is automated. All five manual rubric scores remain null until a reviewer "
                    "assigns 0 or 1 using data/EVALUATION.md. Citation membership only checks whether a cited context ID "
                    "was supplied; it does not verify factual claims or citation support."
                ),
                "reference_limit": (
                    "Reference answers and expected behaviors were written for their supplied contexts. End-to-end RAG "
                    "may retrieve different or additional evidence. Review the actual retrieved evidence and applicability; "
                    "do not grade by exact text match or mechanically require the original reference behavior."
                ),
                "request_retry_policy": "No automatic retries; request errors are retained per row.",
                "results": [],
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation makes accidental overwrite an error, even if a file appeared after the earlier check.
            with output.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(f"Collecting {len(selected)}/{len(examples)} {args.split} questions from the {settings.model_variant} server.")
            if args.limit is not None:
                print("This is a smoke/subset collection; no full-evaluation or quality-score claim will be produced.")
            exit_code = 0
            try:
                for position, example in enumerate(selected, 1):
                    result = collect_one(client, example, settings.model_variant, use_audience=args.use_audience)
                    report["results"].append(result)
                    save_report(output, report)
                    if position % 5 == 0 or position == len(selected):
                        print(f"Collected {position}/{len(selected)} rows; errors={sum(row['error'] is not None for row in report['results'])}.")
                    if result["error"] and result["error"]["type"] == "ModelVariantChanged":
                        report["status"] = "aborted_model_variant_changed"
                        exit_code = 1
                        break
                else:
                    report["status"] = "completed_with_errors" if any(row["error"] for row in report["results"]) else "completed"
                    exit_code = int(report["status"] == "completed_with_errors")
            except KeyboardInterrupt:
                report["status"] = "interrupted"
                exit_code = 130
            except Exception as exc:
                report["status"] = "failed"
                report["collection_error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
                exit_code = 1
            try:
                report["server_status_at_end"] = read_health(client, settings.model_variant)
            except Exception as exc:
                report["server_status_at_end"] = {"error": type(exc).__name__, "message": str(exc)[:1000]}
                if report["status"] == "completed":
                    report["status"] = "completed_with_server_check_error"
                exit_code = exit_code or 1
            report["finished_at_utc"] = utc_now()
            report["collected_rows"] = len(report["results"])
            report["successful_rows"] = sum(row["error"] is None for row in report["results"])
            report["error_rows"] = len(report["results"]) - report["successful_rows"]
            report["all_split_rows_collected"] = len(report["results"]) == len(examples)
            report["all_split_rows_successful"] = report["successful_rows"] == len(examples)
            report["manual_scores_completed"] = 0
            report["behavior_counts_collected"] = dict(Counter(row["behavior"] for row in report["results"]))
            save_report(output, report)
            print(json.dumps({
                "report": str(output), "status": report["status"], "purpose": report["purpose"],
                "collected_rows": report["collected_rows"], "successful_rows": report["successful_rows"],
                "error_rows": report["error_rows"], "manual_scores_completed": 0,
            }, indent=2))
            return exit_code
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
