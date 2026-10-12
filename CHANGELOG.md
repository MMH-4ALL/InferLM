# Changelog
## 0.2.0 — 2026-10-12
- Redesign desktop with warm neutral palettes, monospaced text, and flat surfaces.
- Consolidate navigation and searchable sessions into one toggleable sidebar.
- Center chat and integrate model controls into the composer.
- Add searchable Ctrl+P commands and Ctrl+B / Ctrl+N / Ctrl+1–5 shortcuts.
- Move secondary actions into session/message menus; preserve busy guards.
- Save theme changes immediately without requiring runtime validation.
- Improve paragraph/code rendering and ignore raw Markdown HTML.
- Scroll utility pages at smaller sizes; derive package versions from __version__.
- Preserve existing databases and inference/model/tuning services.
- Verify 57 tests, lint/type checks, five screens and 2× scale in the build environment.
  Three real-runtime tests skipped; native Windows/GPU/0.2 packages remain unverified.

## 0.1.0 — 2026-10-12
Initial development release: desktop/CLI local GGUF chat, hardware observation,
conservative memory planning, authenticated owned runtime, persistence,
token-aware shorter branches, repeated benchmarks, bounded tuning, profiles,
runtime installer, source/wheel packaging, native Linux GUI and CI definitions.

