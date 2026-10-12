# Troubleshooting
- Runtime not found: choose the folder containing both llama-server and
  llama-bench, with the accompanying shared libraries.
- Linux X11 plugin error: install libxcb-cursor0, libxkbcommon-x11-0 and
  libxcb-xinerama0 where needed. Offscreen tests do not verify a physical desktop.
- Memory too high: close other programs, reduce context or choose a smaller model.
  InferLM never alters swap, clocks, drivers, BIOS or power plans.
- No accelerator: the chosen runtime may be CPU-only even with a detected GPU.
  Choose a compatible accelerated build or use GPU layers 0.
- Missing telemetry: initial GPU memory observation supports NVIDIA nvidia-smi.
  AMD/Intel/shared memory providers are not yet implemented.
- Split/IQ/unvalidated quantization: use a single-file standard supported GGUF.
- Context full: Trim older turns creates a smaller branch while preserving the
  original chat, system instruction and latest draft. No automatic summary.
- Stale profile: benchmark again after model/runtime/driver/hardware changes.
- Another InferLM owns the runtime: unload or exit the other instance.
- Runtime failure: Settings → Show runtime troubleshooting log.
- No gain: keep baseline; a larger thread count can be slower.

Local data lives in the platform's user data directory (for example
~/.local/share/InferLM). Removing a library entry preserves its model file.
Uninstalling the app does not automatically remove chats or profiles.

