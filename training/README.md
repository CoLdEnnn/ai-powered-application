# Real QLoRA training for the English AITU assistant

This directory implements actual supervised parameter training for
`Qwen/Qwen2.5-1.5B-Instruct`. The base model is loaded in 4-bit NF4, its original
weights are frozen, and trainable LoRA matrices are added to attention projection
layers. Gradient updates change the adapter weights. At deployment, the adapter
can be merged into the original base model and converted to a local GGUF model.

This is a source-only package. No trained adapter, GPU environment, model weights,
or previous run reports are included. A two-update smoke run was shown in the
original Windows project during development, but its files are not bundled here.
It does not establish full-training completion or answer quality. Run the checks
below in your own environment and preserve the measured results.

## 1. Hardware and deployment plan

Train once on a suitable NVIDIA CUDA machine. Give teammates the resulting
quantized model for local inference; they do not each need the training packages
or a training GPU. Keep training and application environments separate.

An RTX 3050 Ti with 4 GB VRAM is a constrained **candidate**, not a guaranteed
training target. Quantization reduces base-weight memory, but activations,
embedding/output layers, gradients, optimizer state, CUDA kernels, and other GPU
applications also consume memory. CPU RAM does not simply add to VRAM. This script
uses one CUDA device and never silently offloads training to CPU.

Start with batch size 1, rank 8, and the validated sequence limit. Gradient
accumulation gives a larger effective batch without increasing the microbatch;
increasing it further does not reduce the memory of a batch already of size 1.
If this configuration runs out of memory, use a larger training GPU. Reducing
sequence length is useful only when every example still fits; the preflight
rejects examples that would otherwise be silently truncated. A larger GPU is a
training requirement only: teammates can still use the exported local model.

The pinned bitsandbytes release includes CUDA support for Windows x86-64 and
Linux. Windows 11 is not automatically disqualified. Use a clean environment,
an appropriate NVIDIA driver, and CUDA-enabled PyTorch. Linux or WSL2 can be a
practical alternative if your Windows installation encounters package issues.
Official requirements: [bitsandbytes 0.48.1 installation](https://huggingface.co/docs/bitsandbytes/v0.48.1/installation).

## 2. Install a separate training environment

Python 3.11 is the recommended version. From the project root on Windows
PowerShell:

```powershell
py -3.11 -m venv .venv-training
.venv-training\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r training/requirements.txt
python -c "import torch; print(torch.__version__, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No CUDA device')"
```

On Linux, create/activate the environment with:

```bash
python3.11 -m venv .venv-training
source .venv-training/bin/activate
```

Then use the same `python -m pip` commands. The CUDA 12.6 wheel is an official
PyTorch 2.8.0 option; select a wheel compatible with your driver using the
[official PyTorch instructions](https://pytorch.org/get-started/previous-versions/).
This text model does not need torchvision or torchaudio. A CPU-only PyTorch build
can run the tokenization preflight but cannot run this training script.

The requirements pin the principal training libraries. After a successful local
run, preserve the complete environment as well:

```bash
python -m pip freeze > runs/aitu_lora/environment.txt
```

Use a different path if you chose a different run directory. Do not install the
training requirements in every teammate's inference environment.

## 3. Review the data before treating the model as authoritative

The script reads only `data/train.jsonl` and `data/validation.jsonl`. Each line
must have this shape; additional top-level metadata fields are allowed:

```json
{"id":"example-001","messages":[{"role":"system","content":"Answer in English using the supplied context."},{"role":"user","content":"Context: [S1] An example office opens at 09:00.\nQuestion: When does the example office open?"},{"role":"assistant","content":"The example office opens at 09:00. [S1]"}],"metadata":{"split":"train"}}
```

That line is an illustrative schema example, not an AITU fact. Training examples
must contain checked answers supported by their own source context. Include
examples that ask for missing details and examples that say the source does not
provide the answer. Keep documents, prompts, reference answers, and the UI in
English for the intended project.

Draft examples derived from workbook summaries still need review against the
original official sources. Tokenization checks do not verify factual accuracy,
source currency, or institutional approval. Preserve source IDs and the review
status in your data records. Do not replace pending review labels with claims of
human verification until that review actually happens.

Related paraphrases or questions from the same fact family should stay in one
split. The script rejects overlapping IDs, identical train/validation
conversations, and overlapping `source_family_id` metadata when supplied, but
semantic leakage also requires dataset review. It never reads
the test set; reserve that set for the final comparison after training choices
are fixed. Validation loss is used for checkpoint selection, not the held-out
test questions.

## 4. Tokenize and inspect before loading weights

```bash
python training/train_lora.py --config training/config.json --preflight-only
```

The first run may download the public model's configuration and tokenizer from
Hugging Face. It does not download the model weights, call a hosted generation
API, or train any parameters. Subsequent runs can use the local cache:

```bash
python training/train_lora.py --config training/config.json --preflight-only --local-files-only
```

`--local-files-only` needs the necessary files to be cached already. The default
cache is `models/hf_cache`. A full offline training run additionally requires
the base model weights to have been downloaded in that cache.

Preflight performs these checks:

- Exactly one system, user, and assistant message per example.
- Correct split metadata when supplied, no overlapping IDs or source fact family
  IDs, and no identical conversations across train and validation.
- The prompt including the assistant role header is an exact token prefix of the
  full conversation under Qwen's own chat template.
- System/user/header tokens receive label `-100`; only the assistant continuation
  including its end-of-message token contributes to the loss.
- Every full conversation fits `max_seq_length`. There is no automatic truncation
  or removal of long rows. Token counts and target-token totals are printed.

The dynamic collator right-pads each batch and gives padding label `-100` as well.
Ordinary whole-sequence language-model labels would also train on the supplied
documents and prompts; this implementation preserves the assistant-only mask.
Qwen's template is taken from the downloaded tokenizer rather than hard-coded
special-token strings.

## 5. Run an actual training experiment

Review `training/config.json`, then:

```bash
python training/train_lora.py --config training/config.json
```

The script resolves the requested base revision to an immutable Hub commit SHA,
uses that revision for all model/tokenizer loads, and records it in the manifest.
The default output is `runs/aitu_lora`. A nonempty run directory is rejected to
avoid overwriting an experiment. Start another run with a new directory:

```bash
python training/train_lora.py --config training/config.json --output-dir runs/rank8_second_run
```

An optional two-update smoke run checks whether model loading and training can
actually execute on your GPU:

```bash
python training/train_lora.py --config training/config.json --output-dir runs/smoke --max-steps 2
```

The manifest labels this as a smoke test. It is not evidence that the model is
well trained or that all longer examples fit in GPU memory: other batches and
validation may still use more memory. Complete the full intended experiment
before reporting its results.

### What the configurable parameters mean

| Setting | Default | Meaning |
| --- | --- | --- |
| `lora_r` | 8 | Rank of the trainable low-rank matrices; controls adapter capacity and size. |
| `lora_alpha` | 16 | LoRA update scaling; with standard LoRA the multiplier is alpha/r. |
| `lora_dropout` | 0.05 | Dropout on the adapter input during training. |
| `target_modules` | `q_proj`, `v_proj` | Attention projections that receive trainable adapters. |
| `learning_rate` | 0.0001 | Size of optimizer updates; tune using validation, not test answers. |
| `num_train_epochs` | 3 | Initial experimental choice, not a promise that three epochs are optimal. |
| `batch_size` | 1 | Training microbatch size on one GPU. |
| `gradient_accumulation_steps` | 8 | Effective batch of 8 examples on one device, apart from a final partial batch. |
| `max_seq_length` | 1024 | Maximum full prompt-plus-answer length, checked before loading weights. |
| `precision` | `fp16` | Compute precision. `bf16` is accepted only on a supported CUDA device. |

The base uses 4-bit NF4 with double quantization, while training precision and
adapter tensors are separate concerns. `prepare_model_for_kbit_training`
prepares the frozen quantized base and enables gradient checkpointing; some
nonquantized components may remain in higher precision. The base quantization
does not mean every tensor or activation occupies four bits.

This is real parameter adaptation. A changed prompt, temperature, top-k retrieval,
or system instruction alone would not provide the same evidence. Whether this
specific LoRA experiment satisfies the instructor's marking rubric is determined
by that rubric; the project can demonstrate the actual weight updates explicitly.

### Outputs and honest evidence

A completed run writes:

- `adapter/adapter_model.safetensors`, `adapter_config.json`, and tokenizer files.
- `run_manifest.json`: resolved base SHA, effective configuration, source dataset
  SHA-256 hashes, versions, hardware, trainable parameter count, and actual peak
  CUDA allocated/reserved memory.
- `weight_change_evidence` inside the manifest: initial/final tensor hashes,
  number of changed adapter tensors, L2/max absolute weight change, and the
  measured LoRA B-matrix norm. A zero or nonfinite effective update is rejected.
- `metrics.json` and `loss_history.json`: losses and measurements from that run.
- `checkpoints/`: checkpoints and Trainer state; the best checkpoint is selected
  by validation loss using matching epoch evaluation/save schedules.

The selected best-validation adapter is compared to its initial state. The
initial tensor hash is recorded before optimization. Adapter file hashes then
let the merge step detect accidental changes. A failed run records a failed
status rather than manufacturing successful metrics.

Seeds, versions, and hashes support reproducibility; they do not guarantee
bit-for-bit equality across GPU models and CUDA kernels. Weight changes prove
that learning updates occurred. They do not by themselves prove better answers.

## 6. Merge once, then convert to local GGUF

First reload the exact original base revision **without** 4-bit quantization on
CPU, attach the adapter, and merge with PEFT's finite-value check:

```bash
python training/merge_adapter.py --adapter runs/aitu_lora/adapter --output models/aitu_merged
```

The merge uses CPU float16 weights and needs several GB of free system RAM and
disk space. It verifies the completed run manifest and adapter file hashes. The
output contains a standard merged Hugging Face model plus `merge_manifest.json`.
The script does not merge into the 4-bit training model. It does not require a
second training run.

Use the official [llama.cpp repository](https://github.com/ggml-org/llama.cpp).
For conversion, make a separate conversion environment and install the
repository's own requirements for the checked-out version. Keep the full clone:
the converter imports supporting modules from it.

```bash
git clone https://github.com/ggml-org/llama.cpp.git tools/llama.cpp
python -m venv .venv-convert
```

Activate `.venv-convert` using the appropriate command for your OS, then:

```bash
python -m pip install -r tools/llama.cpp/requirements.txt
python tools/llama.cpp/convert_hf_to_gguf.py models/aitu_merged --outfile models/aitu-f16.gguf --outtype f16
```

Obtain or build the matching `llama-quantize` binary using the repository's
instructions. If the binary is on your PATH:

```bash
llama-quantize models/aitu-f16.gguf models/aitu-q4_k_m.gguf Q4_K_M
```

On Windows the executable is `llama-quantize.exe`; use its actual installed path
if it is not on PATH. Record the llama.cpp commit/build version and final GGUF
SHA-256 alongside the experiment. The converter output in float16 is an
intermediate file; the Q4_K_M GGUF is the smaller inference artifact to distribute.

Loading a previously downloaded stock Qwen GGUF will not activate this adapter.
Point the application to `models/aitu-q4_k_m.gguf` after conversion. Keep the
baseline model too, and compare baseline+RAG versus adapted+RAG using the same
retriever, source corpus, prompt structure, context budget, decoding settings,
and held-out questions. Test the **final quantized GGUF**, since merging and
quantization can affect behavior.

For the controlled final comparison, also export an unadapted baseline from the
same immutable base revision in `run_manifest.json`, using the same converter,
quantizer and Q4_K_M settings. Keep it in a separate output file. The official
downloadable GGUF is useful for the initial prototype, but its conversion
history is not automatically identical to your new adapted export; otherwise a
measured difference could include export differences as well as LoRA training.

## Official references

- [Qwen2.5-1.5B-Instruct model card and chat example](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
- [Transformers 4.57.1 Trainer and TrainingArguments](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/trainer)
- [Chat templating](https://huggingface.co/docs/transformers/en/chat_templating)
- [PEFT quantization guide](https://huggingface.co/docs/peft/developer_guides/quantization)
- [Transformers bitsandbytes quantization](https://huggingface.co/docs/transformers/en/quantization/bitsandbytes)
- [PEFT checkpoint formats and merging](https://huggingface.co/docs/peft/en/developer_guides/checkpoint)
- [bitsandbytes 0.48.1 platform requirements](https://huggingface.co/docs/bitsandbytes/v0.48.1/installation)
- [PyTorch official wheel versions](https://pytorch.org/get-started/previous-versions/)
- [llama.cpp quantization instructions](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md)
- [llama.cpp HF-to-GGUF converter](https://github.com/ggml-org/llama.cpp/blob/master/convert_hf_to_gguf.py)

