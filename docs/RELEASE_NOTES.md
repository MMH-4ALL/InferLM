# InferLM 0.1.0 — development release
Local GGUF desktop chat with an optional source-installed CLI.

- Five Qt screens, themes, keyboard controls and background jobs.
- GGUF validation/relinking, SHA-256 model identity and RAM/VRAM estimates.
- Authenticated loopback runtime, streaming, stop/retry/edit and saved chats.
- Shorter conversation branches that preserve original history.
- Repeated native/server benchmarks, bounded tuning and measured profiles.
- Pinned CPU runtime installer, Linux standalone package and source/wheel.
- Tests, Windows/Linux CI definitions and release documentation.

Runtime b11564 (08ffba21e). Native packaging uses PyInstaller onedir.
See TESTING.md for direct evidence and remaining release gates.

Windows, actual NVIDIA/Vulkan acceleration, physical target laptops, 200% scaling
and real Ubuntu/Mint desktop verification remain unverified. No model weights
bundled. Split/IQ formats are deferred. Speed tests do not evaluate answer quality.

