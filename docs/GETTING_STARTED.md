# Getting started
## Source installation
Python 3.12 is required. Unzip the source and open a terminal in the InferLM folder.

Windows PowerShell:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m inferlm
```

Linux:
```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m inferlm
```

Helper scripts in scripts/ perform these steps. Initial dependency installation
needs internet. For a smaller install use python -m pip install ".[gui,cli]".

## Workspace shortcuts
Ctrl+P opens searchable commands. Ctrl+B toggles the sidebar. Ctrl+N starts a
session; Ctrl+1–5 switch screens. Search saved sessions in the sidebar.
The composer contains model selection and Load/Unload; its ↑ button sends.
Chat/session ··· menus provide copy, retry, edit, trim, rename, export, and delete.
Appearance changes save immediately from Settings without runtime validation.

## Native Linux package
Unzip the whole folder; keep _internal and runtime alongside the InferLM executable.
Run ./InferLM. If executable permissions were lost, run chmod +x InferLM.
The packaged CPU runtime is bundled; Python development tools are unnecessary.
Linux builds require glibc 2.39 or newer. Actual Ubuntu/Mint desktop verification
is pending. X11 may require libxcb-cursor0 and the usual Qt/X11 desktop libraries.
No model is bundled.

## First chat
1. Settings: use bundled runtime, or Download pinned CPU runtime, then Validate runtime & save.
2. Models: add an existing single-file GGUF, or drag it onto the window.
3. Chat: choose the model, Load model, and send a message.
4. Enter sends; Shift+Enter adds a line. Stop preserves a partial answer.
5. Reopen saved chats, or export Markdown/JSON.

Review the model license before importing it. Example small instruct model:
https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF
Its model card states Apache-2.0; use a supported standard quantization.
A runtime license does not license model weights.

## Tuning
Run a benchmark before Quick/Thorough Tune. The context capacity stays constant.
Tuning temporarily unloads chat and attempts to restore its previous runtime.
Time budgets limit candidate work; cleanup/restoration can extend elapsed time.
Apply a saved profile, then reload. Restore baseline reverts saved launch settings.
No measured benefit means retain baseline. Results apply to the tested hardware,
runtime, model and workloads, not all computers.

The memory planner is conservative. Unknown architectures require an explicit
unverified-load choice and are not tuned automatically.

## CLI
```text
inferlm configure ./llama-runtime-b11564
inferlm doctor --json
inferlm models add /path/to/model.gguf
inferlm models list
inferlm chat --model MODEL_ID
inferlm benchmark --model MODEL_ID
inferlm optimize --model MODEL_ID --mode quick --budget 900
inferlm profiles list
inferlm profiles apply PROFILE_ID
inferlm export-benchmark RUN_ID --format json --destination report.json
```
The optional CLI is available through the Python/source installation.
GUI/CLI share a database and inference lease. INFERLM_DATA_DIR selects a separate
data directory and therefore a separate lease; use it intentionally.

After dependencies/runtime/model are installed, normal inference is offline.
No login, telemetry, cloud fallback or automatic external requests.

