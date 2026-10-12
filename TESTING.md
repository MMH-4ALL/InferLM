# Verification and credibility
Recorded 12 October 2026 in a Linux x86-64 / glibc 2.39 build environment.
Python 3.12.14, PySide6-Essentials 6.12.0, llama.cpp b11564 (08ffba21e).

## Direct results
- Ruff: passed. mypy on src: passed.
- **53 automated tests passed** with the optional real CPU runtime/model enabled.
- All five Qt pages inspected at 1280×720; GUI startup/exit passed.
- Real authenticated streaming, token counts, saved answers and process cleanup passed.
- Unauthorized chat request returned HTTP 401.
- Repeated real load/unload and loading cancellation passed.
- Tiny Stories fixture and Qwen 2.5 0.5B Instruct loaded and generated text.
- Native benchmarks used 3 measured repetitions at depths 0 and 1024.
- Server validation used warm-up plus 3 repetitions for each of two token-counted
  workloads, with cache_prompt=false.
- Six-candidate Quick Tune, baseline recheck and profile validation/application passed.
- Standalone PyInstaller Linux package started, exited and used its bundled
  runtime to import Qwen and complete measured chat without a Python dev environment.
- Raw reports: docs/validation/tiny-baseline.json, tiny-tuning-profile.json,
  qwen-benchmark.json and native-core-report.json.

Tests cover corrupt/truncated GGUF, metadata bounds, hardware/memory fixtures,
lease ownership, shutdown, timeouts, archive traversal, fragmented UTF-8 streams,
partial-answer persistence, context overflow/drafts, smaller branches, interruption
recovery, stale profiles and absence of Qt imports in the CLI.

The tiny fixture is not representative of useful large-model performance.
These are build-environment measurements, not physical laptop benchmarks.
No quality evaluation or universal compatibility claim is made.

## Reproduce
```bash
ruff check src tests scripts
mypy src
QT_QPA_PLATFORM=offscreen pytest -q
```
Without INFERLM_TEST_RUNTIME and INFERLM_TEST_MODEL, real tests are skipped
explicitly; simulation is not treated as real hardware.

For real tests:
```bash
INFERLM_TEST_RUNTIME=/path/to/runtime \
INFERLM_TEST_MODEL=/path/to/small-model.gguf \
QT_QPA_PLATFORM=offscreen pytest -q
```

Native checks (use a separate data directory):
```bash
QT_QPA_PLATFORM=offscreen ./InferLM --smoke-test
INFERLM_DATA_DIR=/tmp/inferlm-check ./InferLM --verify-core /path/to/model.gguf --output native-report.json
```
--verify-core is a developer verification mode; normal startup never runs it.

## Remaining release gates
| Check | Status |
| --- | --- |
| Windows 11 native build/install/chat/cleanup | Unverified |
| Ubuntu 24.04 / Mint 22 real X11 or Wayland desktop | Unverified |
| Physical 8 GB RAM / 4 GB VRAM laptop | Unverified |
| Physical 16 GB RAM / 6–8 GB VRAM laptop | Unverified |
| Actual NVIDIA CUDA offload | Unverified |
| Vulkan | Experimental, unverified |
| Screen reader and 200% scaling | Unverified manually |
| Signed installers / AppImage | Not produced |
| GitHub CI execution and public release | Not performed |

The Linux bundle requires glibc 2.39+. X11 may require libxcb-cursor0.
Physical tests should cover long chats, stop/restart, saved data, tune/cancel/
restore/profile, relinking, low-memory behavior and orphan-process checks.

## Credibility
Results above are direct execution observations and test outputs. Raw reports
retain settings and provenance. They do not prove performance on untested
hardware or answer quality. Official MLA source references are in
docs/BUILD_BRIEF.md and docs/PACKAGING_SOURCES.md.
