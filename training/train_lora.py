"""Train a real QLoRA adapter on English source-grounded assistant examples.

Run from the project root. Only train and validation files are read. The test
set is reserved for the separate final evaluation. No training is performed
by --preflight-only, which downloads only tokenizer/config files if uncached.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_KEYS = {
    "model_id", "revision", "train_file", "validation_file", "output_dir",
    "cache_dir", "local_files_only", "max_seq_length", "precision", "lora_r",
    "lora_alpha", "lora_dropout", "target_modules", "batch_size",
    "gradient_accumulation_steps", "num_train_epochs", "learning_rate",
    "warmup_ratio", "max_grad_norm", "logging_steps", "seed",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def project_path(value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = REQUIRED_KEYS - config.keys()
    unknown = config.keys() - REQUIRED_KEYS
    if missing or unknown:
        raise ValueError(f"Invalid config keys: missing={sorted(missing)}, unknown={sorted(unknown)}")
    for name in (
        "max_seq_length", "lora_r", "lora_alpha", "batch_size",
        "gradient_accumulation_steps", "logging_steps",
    ):
        if type(config[name]) is not int or config[name] <= 0:
            raise ValueError(f"{name} must be a positive integer.")
    if config["max_seq_length"] < 32 or config["max_seq_length"] > 32768:
        raise ValueError("max_seq_length must be between 32 and 32768.")
    for name in ("learning_rate", "num_train_epochs", "max_grad_norm"):
        if not isinstance(config[name], (int, float)) or config[name] <= 0:
            raise ValueError(f"{name} must be positive.")
    if not 0 <= config["lora_dropout"] < 1 or not 0 <= config["warmup_ratio"] < 1:
        raise ValueError("lora_dropout and warmup_ratio must be in [0, 1).")
    if config["precision"] not in ("fp16", "bf16"):
        raise ValueError("precision must be fp16 or bf16.")
    if not isinstance(config["target_modules"], list) or not config["target_modules"]:
        raise ValueError("target_modules must be a nonempty list of module names.")
    if type(config["local_files_only"]) is not bool or type(config["seed"]) is not int:
        raise ValueError("local_files_only must be boolean and seed must be integer.")
    if config["model_id"] != "Qwen/Qwen2.5-1.5B-Instruct":
        raise ValueError("This starter is configured and preflighted for Qwen/Qwen2.5-1.5B-Instruct.")
    return config


def read_examples(path, expected_split):
    """Validate the single-turn training schema without interpreting document text."""
    path = Path(path)
    if path.stem.lower() in {"test", "test_set", "test_questions"}:
        raise ValueError("The held-out test set must never be used for training or selection.")
    examples = []
    seen_ids = set()
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{line_number}: expected a JSON object.")
            row_id = str(row.get("id", row.get("example_id", f"{expected_split}:{line_number}")))
            if row_id in seen_ids:
                raise ValueError(f"Duplicate example ID in {path.name}: {row_id}")
            seen_ids.add(row_id)
            messages = row.get("messages")
            if not isinstance(messages, list) or len(messages) != 3:
                raise ValueError(f"{row_id}: expected exactly system, user, assistant messages.")
            if any(not isinstance(message, dict) for message in messages):
                raise ValueError(f"{row_id}: each message must be an object.")
            if [message.get("role") for message in messages] != ["system", "user", "assistant"]:
                raise ValueError(f"{row_id}: roles must be system, user, assistant, in that order.")
            for message in messages:
                if not isinstance(message.get("content"), str) or not message["content"].strip():
                    raise ValueError(f"{row_id}: every message must have nonempty text content.")
            metadata = row.get("metadata", {})
            if not isinstance(metadata, dict):
                raise ValueError(f"{row_id}: metadata must be an object when present.")
            for split in (row.get("split"), metadata.get("split")):
                if split is not None and split != expected_split:
                    raise ValueError(f"{row_id}: split={split!r}, expected {expected_split!r}.")
            examples.append({"id": row_id, "messages": messages, "metadata": metadata})
    if not examples:
        raise ValueError(f"No examples found in {path}.")
    return examples


def check_split_overlap(train_rows, validation_rows):
    train_ids = {row["id"] for row in train_rows}
    common_ids = train_ids & {row["id"] for row in validation_rows}
    if common_ids:
        raise ValueError(f"Train/validation IDs overlap: {sorted(common_ids)[:5]}")
    def message_key(row):
        return json.dumps(row["messages"], ensure_ascii=False, sort_keys=True)
    train_content = {message_key(row) for row in train_rows}
    if any(message_key(row) in train_content for row in validation_rows):
        raise ValueError("Identical conversations occur in both train and validation.")
    train_families = {
        row["metadata"].get("source_family_id") for row in train_rows
        if row["metadata"].get("source_family_id")
    }
    validation_families = {
        row["metadata"].get("source_family_id") for row in validation_rows
        if row["metadata"].get("source_family_id")
    }
    if train_families & validation_families:
        raise ValueError("Source fact families overlap across train and validation.")


def resolve_model_revision(config):
    """Resolve a branch/tag to the actual cached Hub snapshot SHA without weights."""
    from huggingface_hub import hf_hub_download

    cached_config = hf_hub_download(
        repo_id=config["model_id"], filename="config.json", revision=config["revision"],
        cache_dir=str(project_path(config["cache_dir"])),
        local_files_only=config["local_files_only"],
    )
    # Do not resolve the symlink: its parent snapshot directory contains the SHA.
    parts = Path(cached_config).parts
    for index, part in enumerate(parts[:-1]):
        if part == "snapshots" and re.fullmatch(r"[0-9a-f]{40}", parts[index + 1]):
            return parts[index + 1]
    raise RuntimeError(
        "Cannot identify the resolved Hugging Face snapshot SHA. Use the normal Hub "
        "cache layout and a repository revision; do not substitute an untracked model folder."
    )


def encode_example(tokenizer, row):
    """Mask the whole prompt and train only on the assistant continuation."""
    messages = row["messages"]
    prompt_ids = tokenizer.apply_chat_template(
        messages[:-1], tokenize=True, add_generation_prompt=True,
    )
    input_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=False,
    )
    if input_ids[:len(prompt_ids)] != prompt_ids:
        raise ValueError(
            f"{row['id']}: the prompt template is not an exact prefix of the full "
            "conversation. Stop and review the tokenizer/template before training."
        )
    if len(input_ids) <= len(prompt_ids):
        raise ValueError(f"{row['id']}: no assistant tokens to supervise.")
    labels = [-100] * len(prompt_ids) + input_ids[len(prompt_ids):]
    return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}


def tokenize_split(tokenizer, rows, maximum, split):
    encoded = []
    too_long = []
    for row in rows:
        item = encode_example(tokenizer, row)
        if len(item["input_ids"]) > maximum:
            too_long.append((row["id"], len(item["input_ids"])))
        encoded.append(item)
    if too_long:
        examples = ", ".join(f"{key}={length}" for key, length in too_long[:8])
        raise ValueError(
            f"{split}: {len(too_long)} examples exceed max_seq_length={maximum}; "
            f"largest={max(length for _, length in too_long)} tokens. {examples}. "
            "Nothing was truncated or dropped. Shorten/review source snippets and "
            "answers, or increase the limit only if GPU memory permits."
        )
    lengths = sorted(len(row["input_ids"]) for row in encoded)
    return encoded, {
        "examples": len(encoded), "min_tokens": lengths[0],
        "median_tokens": statistics.median(lengths),
        "p95_tokens": lengths[max(0, math.ceil(0.95 * len(lengths)) - 1)],
        "max_tokens": lengths[-1],
        "assistant_target_tokens": sum(sum(label != -100 for label in row["labels"]) for row in encoded),
        "truncated_examples": 0,
    }


class AssistantOnlyCollator:
    """Right-pad variable lengths while preserving the assistant loss mask."""

    def __init__(self, pad_token_id):
        self.pad_token_id = pad_token_id

    def __call__(self, features):
        import torch

        maximum = max(len(item["input_ids"]) for item in features)
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for item in features:
            padding = maximum - len(item["input_ids"])
            batch["input_ids"].append(item["input_ids"] + [self.pad_token_id] * padding)
            batch["attention_mask"].append(item["attention_mask"] + [0] * padding)
            batch["labels"].append(item["labels"] + [-100] * padding)
        return {name: torch.tensor(values, dtype=torch.long) for name, values in batch.items()}


def package_versions():
    result = {"python": platform.python_version(), "platform": platform.platform()}
    for package in (
        "torch", "transformers", "peft", "accelerate", "datasets",
        "bitsandbytes", "huggingface-hub", "safetensors", "numpy",
    ):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "not installed"
    return result


def tensor_state_hash(state):
    digest = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().float().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(tuple(tensor.shape)).encode("ascii"))
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def parameter_change_evidence(before, model):
    import torch

    after = {
        name: parameter.detach().cpu().float().clone()
        for name, parameter in model.named_parameters() if parameter.requires_grad
    }
    if after.keys() != before.keys():
        raise RuntimeError("The trainable parameter set changed during training.")
    changed = 0
    squared_delta = 0.0
    max_delta = 0.0
    b_squared_norm = 0.0
    for name, current in after.items():
        if not torch.isfinite(current).all():
            raise RuntimeError(f"Nonfinite adapter weights found: {name}")
        delta = current - before[name]
        squared_delta += delta.double().square().sum().item()
        max_delta = max(max_delta, delta.abs().max().item())
        changed += int(not torch.equal(current, before[name]))
        if ".lora_B." in name:
            b_squared_norm += current.double().square().sum().item()
    evidence = {
        "trainable_tensor_count": len(after), "changed_tensor_count": changed,
        "weight_delta_l2": math.sqrt(squared_delta), "max_absolute_weight_delta": max_delta,
        "lora_B_l2_norm": math.sqrt(b_squared_norm),
        "before_tensor_sha256": tensor_state_hash(before),
        "after_tensor_sha256": tensor_state_hash(after),
        "comparison": "initial adapters versus selected best-validation checkpoint",
    }
    if changed == 0 or squared_delta == 0 or b_squared_norm == 0:
        raise RuntimeError(f"No effective adapter update detected: {evidence}")
    return evidence


def train(config, tokenizer, train_data, validation_data, manifest, output_dir, max_steps):
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, Trainer, TrainingArguments, set_seed

    if not torch.cuda.is_available():
        raise RuntimeError(
            "QLoRA training requires an available NVIDIA CUDA device in this script. "
            "Check your NVIDIA driver and CUDA-enabled PyTorch installation; run "
            "python -c \"import torch; print(torch.__version__, torch.cuda.is_available())\". "
            "Use --preflight-only without a GPU, or train on a stronger CUDA machine "
            "and distribute the resulting GGUF for CPU inference. No CPU offload was attempted."
        )
    torch.cuda.set_device(0)
    if config["precision"] == "bf16" and not torch.cuda.is_bf16_supported():
        raise RuntimeError("This CUDA device does not support bf16; use precision=fp16.")
    dtype = torch.bfloat16 if config["precision"] == "bf16" else torch.float16
    properties = torch.cuda.get_device_properties(0)
    manifest["hardware"] = {
        "device": "cuda:0", "name": properties.name,
        "total_vram_bytes": properties.total_memory, "cuda_runtime": torch.version.cuda,
        "compute_capability": f"{properties.major}.{properties.minor}",
    }
    write_json(output_dir / "run_manifest.json", manifest)
    print(f"Using {properties.name}: {properties.total_memory / 1024 ** 3:.2f} GiB VRAM")
    print("4 GiB VRAM is not a guaranteed fit. This run uses one CUDA device without CPU offload.")
    set_seed(config["seed"])
    torch.cuda.reset_peak_memory_stats()
    quantization = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype,
    )
    model = AutoModelForCausalLM.from_pretrained(
        config["model_id"], revision=manifest["model"]["resolved_revision"],
        cache_dir=str(project_path(config["cache_dir"])),
        local_files_only=config["local_files_only"], trust_remote_code=False,
        quantization_config=quantization, torch_dtype=dtype,
        device_map={"": 0}, attn_implementation="sdpa",
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(
        r=config["lora_r"], lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"], target_modules=config["target_modules"],
        bias="none", task_type="CAUSAL_LM",
    ))
    if any(parameter.device.type != "cuda" for parameter in model.parameters()):
        raise RuntimeError("A model parameter is outside CUDA; unexpected offload is not supported.")
    trainable_count, total_count = model.get_nb_trainable_parameters()
    if trainable_count == 0:
        raise RuntimeError("LoRA created no trainable parameters.")
    before = {}
    for name, parameter in model.named_parameters():
        if parameter.requires_grad:
            if "lora_" not in name:
                raise RuntimeError(f"Unexpected non-LoRA trainable parameter: {name}")
            before[name] = parameter.detach().cpu().float().clone()
    manifest["parameters"] = {
        "trainable": trainable_count, "total_as_reported_by_peft": total_count,
        "trainable_percent": 100 * trainable_count / total_count,
        "initial_trainable_tensor_sha256": tensor_state_hash(before),
    }
    write_json(output_dir / "run_manifest.json", manifest)
    model.print_trainable_parameters()
    arguments = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        per_device_train_batch_size=config["batch_size"], per_device_eval_batch_size=1,
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        num_train_epochs=config["num_train_epochs"], max_steps=max_steps,
        learning_rate=config["learning_rate"], warmup_ratio=config["warmup_ratio"],
        max_grad_norm=config["max_grad_norm"], optim="adamw_torch",
        gradient_checkpointing=True, fp16=config["precision"] == "fp16",
        bf16=config["precision"] == "bf16",
        eval_strategy="epoch", save_strategy="epoch", save_total_limit=2,
        load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
        prediction_loss_only=True, logging_strategy="steps", logging_steps=config["logging_steps"],
        logging_first_step=True, logging_nan_inf_filter=False,
        report_to="none", push_to_hub=False, dataloader_num_workers=0,
        seed=config["seed"], data_seed=config["seed"], label_names=["labels"],
    )
    trainer = Trainer(
        model=model, args=arguments, processing_class=tokenizer,
        train_dataset=Dataset.from_list(train_data), eval_dataset=Dataset.from_list(validation_data),
        data_collator=AssistantOnlyCollator(tokenizer.pad_token_id),
    )
    result = trainer.train()
    selected_metrics = trainer.evaluate()
    for name, value in {**result.metrics, **selected_metrics}.items():
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise RuntimeError(f"Nonfinite training metric {name}={value}; adapter is not accepted.")
    evidence = parameter_change_evidence(before, model)
    adapter_dir = output_dir / "adapter"
    model.save_pretrained(str(adapter_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(adapter_dir))
    trainer.save_state()
    metrics = {"training": result.metrics, "selected_checkpoint_validation": selected_metrics}
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "loss_history.json", trainer.state.log_history)
    manifest.update({
        "status": "completed", "finished_at": utc_now(),
        "optimizer_steps": trainer.state.global_step,
        "best_validation_loss": trainer.state.best_metric,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "weight_change_evidence": evidence,
        "adapter_files": {
            path.name: sha256_file(path) for path in sorted(adapter_dir.iterdir()) if path.is_file()
        },
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(),
        "peak_cuda_reserved_bytes": torch.cuda.max_memory_reserved(),
        "metrics": metrics,
    })
    write_json(output_dir / "run_manifest.json", manifest)
    print(json.dumps({"adapter": str(adapter_dir), "evidence": evidence, "metrics": metrics}, indent=2))
    print("Actual parameter updates were saved. Validation loss alone does not establish answer quality.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="training/config.json")
    parser.add_argument("--preflight-only", action="store_true", help="Validate/tokenize data without loading model weights.")
    parser.add_argument("--local-files-only", action="store_true", help="Use cached HF files; do not download.")
    parser.add_argument("--output-dir", help="Use a fresh run directory, relative to project root.")
    parser.add_argument("--max-steps", type=int, default=-1, help="Optional short smoke run; -1 uses configured epochs.")
    args = parser.parse_args()
    if args.max_steps == 0 or args.max_steps < -1:
        parser.error("--max-steps must be -1 or a positive integer.")
    manifest = None
    output_dir = None
    try:
        config_path = project_path(args.config)
        config = load_config(config_path)
        if args.local_files_only:
            config["local_files_only"] = True
        if args.output_dir:
            config["output_dir"] = args.output_dir
        train_path = project_path(config["train_file"])
        validation_path = project_path(config["validation_file"])
        if train_path == validation_path:
            raise ValueError("Train and validation must be different files.")
        train_rows = read_examples(train_path, "train")
        validation_rows = read_examples(validation_path, "validation")
        check_split_overlap(train_rows, validation_rows)
        from transformers import AutoTokenizer
        revision = resolve_model_revision(config)
        tokenizer = AutoTokenizer.from_pretrained(
            config["model_id"], revision=revision, trust_remote_code=False,
            cache_dir=str(project_path(config["cache_dir"])),
            local_files_only=config["local_files_only"],
        )
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right"
        train_data, train_stats = tokenize_split(tokenizer, train_rows, config["max_seq_length"], "train")
        validation_data, validation_stats = tokenize_split(tokenizer, validation_rows, config["max_seq_length"], "validation")
        preflight = {
            "status": "preflight_passed", "checked_at": utc_now(),
            "model_id": config["model_id"], "resolved_revision": revision,
            "train": train_stats, "validation": validation_stats,
            "train_sha256": sha256_file(train_path), "validation_sha256": sha256_file(validation_path),
            "test_set_read": False, "model_weights_loaded": False,
            "source_accuracy_verified_by_this_script": False,
        }
        print(json.dumps(preflight, indent=2))
        if args.preflight_only:
            print("Preflight finished. No model weights were loaded and no parameters were trained.")
            return 0
        output_dir = project_path(config["output_dir"])
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError(f"Run directory is not empty: {output_dir}. Choose a fresh --output-dir.")
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "status": "started", "started_at": utc_now(), "config": config,
            "config_file_sha256": sha256_file(config_path),
            "training_script_sha256": sha256_file(Path(__file__)),
            "purpose": "smoke_test" if args.max_steps > 0 else "training",
            "max_steps_override": args.max_steps,
            "model": {"id": config["model_id"], "requested_revision": config["revision"], "resolved_revision": revision},
            "preflight": preflight, "versions": package_versions(),
            "reproducibility_note": "Seed and input hashes are recorded; bitwise CUDA reproducibility is not guaranteed.",
        }
        write_json(output_dir / "run_manifest.json", manifest)
        train(config, tokenizer, train_data, validation_data, manifest, output_dir, args.max_steps)
        return 0
    except Exception as exc:
        is_oom = "out of memory" in str(exc).lower() or type(exc).__name__ == "OutOfMemoryError"
        if manifest is not None and output_dir is not None:
            manifest.update({"status": "failed", "finished_at": utc_now(), "error_type": type(exc).__name__, "error": str(exc)})
            write_json(output_dir / "run_manifest.json", manifest)
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        if is_oom:
            print(
                "CUDA ran out of memory. Close other GPU applications. Batch size is already 1 by default. "
                "Lower sequence length only after rechecking every example; this script never truncates silently. "
                "Gradient accumulation does not reduce memory further when the microbatch is already 1. "
                "Use a larger CUDA GPU if necessary, then distribute the trained GGUF to weaker laptops.",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
