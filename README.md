# InferLM
**Local AI chat and measured settings for your laptop.**

Development release **0.1.0**. Import a local GGUF, chat through llama.cpp,
benchmark the configuration, and save a tuning profile backed by measurements.

## What works
- Native Qt desktop: Chat, Models, Optimize, Benchmarks, Settings.
- Dark/light themes, keyboard controls and background jobs.
- Supported GGUF import/relinking and conservative separate RAM/VRAM planning.
- Pinned CPU runtime download from Settings.
- Streaming, stop/retry/edit, saved chats and Markdown/JSON exports.
- Token-aware shorter branches that preserve the original conversation.
- Repeated native/server benchmarks and bounded tuning with a baseline recheck.
- Hardware/model/runtime-bound profiles and a shared optional CLI.

## Native Linux download
Unzip the full package and run `./InferLM`. Keep `_internal` and `runtime`
alongside it. The CPU runtime is bundled. No Python installation is required.
If permissions were lost: `chmod +x InferLM`.

This build requires Linux x86-64 and glibc 2.39+. On X11 install
`libxcb-cursor0` if the Qt platform plugin reports it missing.
Physical Ubuntu/Mint desktop verification remains pending.
No model weights are bundled.

## Source installation
Python 3.12; initial dependency installation needs internet.

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

For a smaller non-development install, use `python -m pip install ".[gui,cli]"`.
The lockfile records tested versions with Windows-specific dependency markers.
PySide6-Essentials supplies Widgets/SVG; WebEngine is unnecessary.

## First launch
1. Settings: use bundled runtime, or Download pinned CPU runtime; Validate & save.
2. Models: add an existing single-file GGUF.
3. Chat: choose model, Load model, and send a message.
4. Benchmark before Quick Tune. Apply a measured profile, then reload.

After dependencies/runtime/model are installed, chat and tuning work offline.
Models have their own licenses. Start with a small instruct model.

## CLI
```text
inferlm doctor --json
inferlm configure ./llama-runtime-b11564
inferlm models add /path/to/model.gguf
inferlm models list
inferlm chat --model MODEL_ID
inferlm benchmark --model MODEL_ID
inferlm optimize --model MODEL_ID --mode quick --budget 900
inferlm profiles list
inferlm profiles apply PROFILE_ID
```
The optional CLI uses the Python/source installation. It shares services,
storage and an inference lease with the GUI.

## Verification and limits
**53 tests passed**, including real CPU inference tests. Ruff and mypy passed.
The standalone Linux executable passed GUI startup/exit and imported-model chat
verification with Qwen 2.5 0.5B Instruct. Real benchmarks and a tuning/profile
workflow completed. Evidence is under docs/validation.

Windows native execution, actual NVIDIA/Vulkan acceleration, physical target
laptops, 200% scaling and real Ubuntu/Mint desktop verification remain pending.
Split/IQ models are deferred. NVIDIA telemetry is implemented; other providers
are unavailable. Memory estimates are conservative and may reject practical
offloaded configurations. Tuning evaluates speed/stability, not answer quality.

See [Getting started](docs/GETTING_STARTED.md), [Testing](TESTING.md),
[Architecture](ARCHITECTURE.md), [Troubleshooting](docs/TROUBLESHOOTING.md),
[Status](PROJECT_STATUS.md) and [Release instructions](docs/RELEASE.md).

Original code is MIT. Dependencies and models retain their own licenses.
