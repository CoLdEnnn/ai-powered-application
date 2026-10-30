# AITU Local AI Assistant

An English-language assistant for applicants and current students of Astana IT
University. FastAPI serves a browser interface, RAG retrieves university information,
and a local Qwen2.5-1.5B-Instruct model generates answers with source references.

This package contains source code, configurations, and the original project dataset.
Python environments, downloaded models, llama.cpp binaries, search indexes, trained
adapters, and previous run results are not included. Install and prepare them using
the commands below. The current interface is basic; implementing your Figma design
is a separate development task.

## 1. Open the project in VS Code

Extract the archive into a new folder, for example `D:\aitu_assistant`.
Open the folder containing `run.py` in VS Code, then select **Terminal > New Terminal**
and use **PowerShell**. Run every Windows command below from this project folder.
Keep your existing working installation in its own folder.

Install 64-bit Python from [python.org](https://www.python.org/downloads/windows/)
if needed, and enable **Add Python to PATH**. Python 3.12 is recommended for the
application; Python 3.11 is recommended for training. Check the interpreter selected
by your terminal:

```powershell
python --version
```

The commands use `python` from your PATH. If you need another installed version,
use the full path to that version's `python.exe` when creating its environment.
For example, PowerShell runs a quoted executable path using `& "C:\path\python.exe"`.
An existing compatible Python installation does not need to be installed again.

## 2. Install application dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`.venv` is the application environment. `requirements.txt` lists its dependencies.
These commands need an internet connection. Activation and PowerShell execution
policy changes are unnecessary because each command selects the environment's
Python explicitly.

## 3. Install the llama.cpp inference engine

Open the [official llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases).
For the first run, download a Windows x64 CPU build compatible with your machine.
Extract all its files, including the accompanying DLLs, into `vendor/llama/`.
Create these folders if necessary. The expected executable path is:

```text
vendor/llama/llama-server.exe
```

Keep the DLLs beside the executable. If the archive creates an extra nested folder,
move its contents to the expected location or update `llama_server_path` in
`config.json`. Record the release/build identifier for reproducibility.

## 4. Download the models and build the search index

```powershell
.\.venv\Scripts\python.exe scripts/setup_models.py
.\.venv\Scripts\python.exe scripts/build_index.py
```

The first command downloads the original Qwen GGUF model and prepares the
`BAAI/bge-small-en-v1.5` embedding model. The second creates `index/` from the data
in `data/`. This is inference preparation, not Qwen training. Downloads require
internet access.

## 5. Start the application

```powershell
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:8000 in your browser. Keep the terminal running.
Press **Ctrl+C** to stop the application and its model process.

After preparation, answers are computed locally. Each question is independent:
previous conversation turns are not sent to the model. The default configuration
serves only this computer. Access from a phone requires configuring network access;
it is not enabled by this installation procedure.

## 6. Install training dependencies (optional)

Skip this section if you only want to run the chat application. The training script
requires an NVIDIA CUDA GPU, a compatible driver, and a CUDA-enabled PyTorch build.
It does not train on the CPU. Use a separate environment to avoid conflicts with
application dependencies. llama.cpp is not needed for adapter training.

Python 3.11 is recommended for this environment. If it differs from your application
Python, use its full executable path in the first command.

```powershell
python -m venv .venv-training
.\.venv-training\Scripts\python.exe -m pip install --upgrade pip
.\.venv-training\Scripts\python.exe -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu126
.\.venv-training\Scripts\python.exe -m pip install -r training/requirements.txt
.\.venv-training\Scripts\python.exe -c "import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available())"
```

CUDA must be available before training. Installing PyTorch alone does not guarantee
GPU availability. With the environment ready, check the data and token labels:

```powershell
.\.venv-training\Scripts\python.exe training/train_lora.py --config training/config.json --preflight-only
```

Preflight may download the tokenizer and model configuration. It does not download
model weights or update parameters. Next, run a two-update smoke test:

```powershell
.\.venv-training\Scripts\python.exe training/train_lora.py --config training/config.json --output-dir runs/smoke --max-steps 2
```

Then run the full configured fine-tuning experiment:

```powershell
.\.venv-training\Scripts\python.exe training/train_lora.py --config training/config.json
```

Use a new `--output-dir` when repeating an experiment: nonempty run directories are
rejected. A 4 GB GPU needs an actual fit check; a short smoke test does not guarantee
that all training and validation batches fit.

QLoRA freezes the quantized base model and trains adapter parameters. A successful
run saves its adapter and measurements under `runs/`. It does not automatically
switch the chat to the adapted model. Follow [training/README.md](training/README.md)
for merging, GGUF export, and selecting the resulting model file.

## Dataset and updated Excel workbook

The included original dataset contains **307 training examples, 38 validation
examples, 39 test examples, and 447 RAG contexts**. It has not been replaced with
your latest 434-row Excel workbook. Existing source-review labels are preserved.
Check applicable years and source currency before practical use.
See [data/EVALUATION.md](data/EVALUATION.md) for the evaluation plan.

To import your updated workbook, put it beside `run.py`, name it `AITU.xlsx`, and
run the converter after installing the application dependencies:

```powershell
.\.venv\Scripts\python.exe prepare_excel_dataset.py --excel AITU.xlsx --reviewed-only
```

For Q&A records, `--reviewed-only` requires the `Reviewed` team-review label. It does
not verify facts itself. Calendar and contact records are retrieval material and
are subject to the converter's review filtering.

The converter creates `data/updated/`, `config.updated.json`, and
`training/config.updated.json` without replacing the original files. If these
outputs already exist, choose another output name using `--name`.
After the first import, build the new index and run with the new configuration:

```powershell
.\.venv\Scripts\python.exe scripts/build_index.py --config config.updated.json
.\.venv\Scripts\python.exe run.py --config config.updated.json
```

For training on the imported dataset, replace `--config training/config.json` with
`--config training/config.updated.json` in the training commands, starting with
preflight again. Counts for the imported dataset are recorded in its manifest;
they depend on the workbook and review filters.

## Project structure

| Path | Purpose |
|---|---|
| `run.py` | Starts the model process and application |
| `app/` | API, retrieval, prompt construction, and model client |
| `app/static/` | HTML, CSS, and JavaScript interface |
| `config.json` | Inference model paths and application settings |
| `data/` | Source contexts, references, and dataset splits |
| `scripts/` | Model preparation, indexing, and evaluation |
| `prepare_excel_dataset.py` | Excel-to-JSONL dataset conversion |
| `training/config.json` | QLoRA training settings |
| `training/train_lora.py` | Adapter training |
| `training/merge_adapter.py` | Adapter merging |
| `tests/` | Logic checks without model downloads |

## Run the code checks

After installing the application dependencies:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

These checks do not need trained weights, CUDA, or training dependencies. They do
not measure factual answer quality from a running model.

## Publish the source on GitHub

Commit the source, data, configurations, and instructions. `.gitignore` excludes
local environments, downloaded models, inference binaries, generated indexes, and
training runs. You can separately preserve small measured experiment reports under
`reports/`. Do not commit passwords or access tokens.

This source archive contains no trained adapter and makes no claim of completed
full fine-tuning or verified answer quality. The application initially uses the
original Qwen model after installation.
