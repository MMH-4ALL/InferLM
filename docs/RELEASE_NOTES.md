# InferLM 0.2.0 — workspace redesign

A new desktop layout inspired by OpenCode's restrained terminal interface.

- Flat charcoal and warm light themes; monospaced text and amber accents.
- One sidebar for navigation and searchable saved sessions.
- Centered conversation with readable message spacing and a compact composer.
- Model selection, load/unload, and send together in the composer.
- Secondary chat and session actions moved into menus.
- Ctrl+P command search, Ctrl+B sidebar toggle, Ctrl+N new session, Ctrl+1–5 screens.
- Theme changes save immediately, even before a runtime is configured.
- Scrollable utility screens at smaller window sizes; busy controls and Stop preserved.
- Markdown rendering preserves code and ignores raw HTML.

The inference, GGUF, storage, benchmarks, and tuning services are unchanged.
Existing model entries, conversations, profiles, and settings remain compatible.

Validation: 57 tests passed, 3 real-runtime tests explicitly skipped; Ruff and
mypy passed. Actual Qt layouts were inspected at 1320×840, 960×620, and 2× scale.
The previous 0.1 CPU inference reports remain under docs/validation; they were
not rerun or presented as 0.2 native-package verification.

This is a development prerelease distributed as source. No 0.2 Windows/Linux
binary is attached. The repository includes a manual Native unsigned packages
workflow that builds on Windows and Linux. Physical Windows/GPU testing,
screen-reader use, and signed installers remain unverified.
