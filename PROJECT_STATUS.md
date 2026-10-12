# InferLM project status
Development version **0.2.0**, 12 October 2026.
Public repository: https://github.com/MMH-4ALL/InferLM

## Current change
The desktop workspace has been redesigned around one sidebar, session search,
a centered chat column, integrated model/composer controls, command search,
and independent dark/light palettes. See docs/DESIGN.md and CHANGELOG.md.
The underlying inference, models, storage, benchmark, and tuning services are
unchanged; the SQLite schema remains compatible with 0.1.

## Current verification
57 tests passed; 3 actual-runtime tests skipped because this redesign checkout
has no model/runtime fixture. Ruff and mypy passed. All five Qt screens were
inspected at 1320×840 and 960×620, with dark/light and 2× scaling captures.
Source smoke startup/exit passed. Screen-reader and physical Windows testing
remain pending. README chat previews use labeled example conversation text.

## Earlier 0.1 evidence
53 tests passed with real CPU fixtures. Tiny Stories and Qwen 2.5 0.5B Instruct
chat/benchmark and six-candidate tuning/profile checks completed. The 0.1 Linux
PyInstaller package passed startup/exit and Qwen chat. Those historical reports
remain under docs/validation; they do not verify a new 0.2 native package.

## Delivery and remaining gates
0.2 source is published in the public repository. Windows/Linux package
workflows are available; no 0.2 native package has been produced in this change.
Physical target laptops, actual NVIDIA/Vulkan offload, Windows native execution,
real X11/Wayland plugins, screen-reader use, and signed installers remain gates.
Model weights are never bundled. Do not call this 1.0 or claim universal gains.

## Resume
Inspect latest GitHub main and the current docs before further work. Prioritize
native Windows packaging and actual target-device checks. Preserve release
history and keep measurement claims tied to their exact tested build.
