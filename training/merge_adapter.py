"""Merge a completed adapter into the same unquantized HF base on CPU.

This produces a Hugging Face model folder, not GGUF. Use the official llama.cpp
converter and quantizer afterwards. The training run manifest pins the exact
base revision and verifies the adapter files before loading them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from train_lora import package_versions, project_path, sha256_file, utc_now, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, help="Adapter directory from a completed training run.")
    parser.add_argument("--output", required=True, help="A new output directory for merged HF weights.")
    parser.add_argument("--manifest", help="Defaults to run_manifest.json in the adapter's parent directory.")
    parser.add_argument("--local-files-only", action="store_true", help="Require all base/tokenizer files to be cached.")
    args = parser.parse_args()
    try:
        adapter_dir = project_path(args.adapter)
        output_dir = project_path(args.output)
        manifest_path = project_path(args.manifest) if args.manifest else adapter_dir.parent / "run_manifest.json"
        run = json.loads(manifest_path.read_text(encoding="utf-8"))
        if run.get("status") != "completed":
            raise ValueError("The adapter must come from a completed run with recorded parameter changes.")
        evidence = run.get("weight_change_evidence", {})
        if evidence.get("weight_delta_l2", 0) <= 0 or evidence.get("lora_B_l2_norm", 0) <= 0:
            raise ValueError("Run manifest does not contain positive measured adapter change evidence.")
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError(f"Output is not empty: {output_dir}. Choose a new --output directory.")
        if output_dir == adapter_dir or adapter_dir in output_dir.parents:
            raise ValueError("The merged model must be stored outside the adapter directory.")
        expected_files = run.get("adapter_files", {})
        if "adapter_model.safetensors" not in expected_files or "adapter_config.json" not in expected_files:
            raise ValueError("Manifest does not identify the adapter weights and configuration.")
        for filename, expected_hash in expected_files.items():
            # Filenames are recorded locally by the trainer; forbid traversal if a manifest was edited.
            if Path(filename).name != filename:
                raise ValueError(f"Invalid adapter filename in manifest: {filename}")
            candidate = adapter_dir / filename
            if not candidate.is_file() or sha256_file(candidate) != expected_hash:
                raise ValueError(f"Adapter file is missing or has changed since training: {filename}")
        model_id = run["model"]["id"]
        revision = run["model"]["resolved_revision"]
        config = run["config"]
        local_only = args.local_files_only or config["local_files_only"]
        if run.get("purpose") == "smoke_test":
            print("This adapter came from a smoke test, not a completed epoch-based experiment.")
        print(f"Loading unquantized {model_id}@{revision} on CPU in float16.")
        print("CPU merging needs several GB of available system RAM and disk space; it is done once.")
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        base = AutoModelForCausalLM.from_pretrained(
            model_id, revision=revision, trust_remote_code=False,
            cache_dir=str(project_path(config["cache_dir"])), local_files_only=local_only,
            torch_dtype=torch.float16, device_map={"": "cpu"}, low_cpu_mem_usage=True,
        )
        adapted = PeftModel.from_pretrained(
            base, str(adapter_dir), is_trainable=False, local_files_only=True,
        )
        merged = adapted.merge_and_unload(safe_merge=True)
        merged.config.use_cache = True
        output_dir.mkdir(parents=True, exist_ok=True)
        merged.save_pretrained(str(output_dir), safe_serialization=True, max_shard_size="2GB")
        tokenizer = AutoTokenizer.from_pretrained(
            str(adapter_dir), local_files_only=True, trust_remote_code=False,
        )
        tokenizer.save_pretrained(str(output_dir))
        merge_manifest = {
            "status": "completed", "merged_at": utc_now(), "model_id": model_id,
            "resolved_revision": revision, "dtype": "float16", "device": "cpu",
            "source_run_manifest_sha256": sha256_file(manifest_path),
            "source_adapter_sha256": expected_files["adapter_model.safetensors"],
            "source_run_purpose": run.get("purpose"), "safe_merge": True,
            "versions": package_versions(),
            "merged_files": {
                path.name: sha256_file(path) for path in sorted(output_dir.iterdir()) if path.is_file()
            },
            "quality_note": "Successful merging does not evaluate generation quality; validate the final quantized model separately.",
        }
        write_json(output_dir / "merge_manifest.json", merge_manifest)
        print(f"Merged HF model saved to {output_dir}")
        print("Next: convert this whole folder to GGUF and quantize it with llama.cpp.")
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
