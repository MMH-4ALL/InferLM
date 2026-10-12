# InferLM — ChatGPT Work master build prompt

Act as the lead software engineer, desktop application designer, and test engineer for **InferLM**.

Build a real local AI desktop application for Windows and Linux, with an optional terminal CLI. Its main purpose is to help people with ordinary laptops choose a suitable local model, run it, chat with it, and find settings that improve performance through measured tests.

**Actually create the project files, implement the application, run the checks available to you, fix problems, and deliver a runnable project. Do not stop at a plan, screenshots, snippets, or a web mockup.**

Use the exact branding **InferLM**. Use `inferlm` for the Python package, CLI command, and proposed repository name. Treat this as the chosen working name; do not claim trademark or name clearance.

## 1. Work within ChatGPT Work

Inspect the tools, workspace, operating system, network access, and available repository connections before choosing execution steps.

- If a project already exists, inspect its current files, Git status, and instructions. Continue from it and preserve unrelated work.
- If no project exists, create a clean modular project.
- Use the shell, file editing, dependency installation, and testing tools available in this session. Do not assume you can control my personal laptop, access its GPU, or run Windows binaries in a Linux workspace.
- Use relevant installed skills where they improve the result. Explain meaningful design decisions briefly.
- Continue through the milestones without requesting permission for routine implementation choices.
- If an external connection or dependency is unavailable, finish all independent work and identify the exact blocker.
- A preview may demonstrate the design, but the deliverable must be a desktop application.
- Never substitute cloud inference for local inference.
- Keep progress updates short and useful.

Maintain `PROJECT_STATUS.md` throughout the build. Record implemented features, actual test results, unresolved problems, runtime versions, and the next concrete action. If I say “continue,” inspect that file and the current project before proceeding. Never restart from scratch just because the conversation has continued.

## 2. Product promise and limits

The product promise is:

**“Run local AI with settings chosen for your laptop, and see whether tuning actually helps.”**

Target laptops:

- 8–16 GB system RAM.
- 4–8 GB dedicated GPU memory when a dedicated GPU is present.
- CPU-only operation as a supported fallback.
- Windows 11 x86-64 and Linux x86-64 initially.
- Ubuntu 24.04 and Linux Mint 22 as initial Linux validation targets. Document other distributions as unverified until tested.

Prioritize small and medium quantized text models. Use larger models only when their actual memory needs and measured performance make them practical.

Do not promise that a 32B or 70B model becomes fast on a low-memory laptop. Do not present file size as the complete memory requirement. Do not combine RAM and VRAM into a universal “model capacity” number.

Label information consistently:

- **Estimated:** calculated before execution, with assumptions.
- **Measured:** observed in a real run, with test conditions.
- **Unavailable:** the platform could not provide it.
- **Unverified:** implemented but not tested on the relevant hardware.

No invented speeds, compatibility claims, savings percentages, or performance charts.

## 3. Version 1.0 scope

Deliver one reliable end-to-end workflow:

**Inspect hardware → import a GGUF model → choose safe settings → load it → chat → benchmark → tune → save a profile → reuse it.**

Include:

1. Native desktop GUI.
2. Hardware inspection and backend detection.
3. Import and management of existing local GGUF models.
4. A managed local inference process.
5. Streaming chat and saved conversations.
6. Conservative memory planning.
7. Repeatable benchmarking and bounded automatic tuning.
8. Saved settings and optimization profiles.
9. Optional CLI using the same application services.
10. Windows and Linux build scripts, tests, documentation, and release preparation.

Defer the model download catalog, cloud accounts, RAG/document ingestion, voice, image generation, agents, remote servers, training, custom quantization, and multiple inference engines to later versions. Do not add these before the core workflow works.

A complete local app can begin with imported models. Provide clear instructions for obtaining a compatible model, including its license, without bundling model weights.

## 4. Technology and architecture

Use this default stack:

- Python 3.12, subject to verified dependency compatibility.
- PySide6 with Qt Widgets for the desktop GUI.
- llama.cpp standalone `llama-server` for inference.
- llama.cpp standalone `llama-bench` for controlled throughput measurements.
- psutil for CPU, RAM, and process monitoring.
- Optional supported NVIDIA telemetry for dedicated VRAM.
- httpx for local HTTP requests and streaming.
- SQLite for models, conversations, profiles, and benchmark records.
- platformdirs for platform-specific storage locations.
- Typer and Rich for the optional CLI.
- pytest, pytest-qt, Ruff, and a practical type checker for validation.
- pyside6-deploy/Nuitka standalone packaging as the initial packaging approach.

Verify the current official documentation before implementation. Pin dependency versions and the tested llama.cpp build. Do not copy runtime flags from memory and assume they are supported.

Keep the inference runtime in a separate process. Do not require users to compile CUDA code, install the full PyTorch stack, or rebuild llama.cpp merely to use a packaged application.

Use one application service layer shared by GUI and CLI. Keep Qt imports out of the core services and CLI execution path.

Suggested structure; adjust only when there is a clear reason:

```text
inferlm/
  pyproject.toml
  src/inferlm/
    __init__.py
    __main__.py
    app.py
    core/
      types.py
      services.py
      jobs.py
    hardware/
      detect.py
      memory.py
      providers/
    models/
      registry.py
      gguf.py
      compatibility.py
    runtime/
      capabilities.py
      manager.py
      client.py
      manifests.py
    chat/
      service.py
      context.py
    optimization/
      planner.py
      benchmark.py
      search.py
      profiles.py
    storage/
      database.py
      migrations/
      repositories/
    gui/
      window.py
      theme.py
      components/
      screens/
    cli/
      app.py
      commands/
    assets/
  tests/
    unit/
    integration/
    gui/
    fixtures/
  scripts/
  packaging/
  docs/
  .github/workflows/
  README.md
  ARCHITECTURE.md
  TESTING.md
  CHANGELOG.md
  THIRD_PARTY_NOTICES.md
  PROJECT_STATUS.md
```

Use typed records for hardware snapshots, model metadata, runtime capabilities, launch settings, chat events, benchmark samples, and optimization results.

Use cancellable background jobs for hardware queries, parsing, loading, chat, benchmarks, and tuning. Perform Qt updates on its main thread through signals. Bound queues and log buffers. Do not block the interface with inference work.

Avoid unnecessary services and abstractions. Build only modules with working responsibilities.

## 5. Runtime installation and management

Support a bundled CPU runtime or a clearly guided runtime setup. Allow selection of an existing compatible local runtime folder.

Provide a reproducible route for installing a pinned official runtime. Record platform, architecture, backend, upstream version, source URL, and checksums. Validate downloaded archives and prevent extraction outside the chosen directory.

Initial backend priority:

- CPU: required and tested.
- NVIDIA CUDA: include where the pinned build and device support it.
- Vulkan: optional and explicitly experimental until validated.
- Do not claim that every AMD or Intel GPU supports acceleration.

Inspect the binaries' version and help output. Map supported server and benchmark settings separately; their flags may differ. Reject or hide unsupported settings.

Bind the server to loopback only. Use authentication supported by the pinned runtime and protect secrets from logs. Handle occupied ports, startup readiness, timeouts, crashes, and incompatible runtime versions.

Launch with argument arrays, without shell interpolation. Support paths with spaces and non-English characters.

Track and stop only processes started by InferLM. Use platform-appropriate process ownership and shutdown methods. On unload, cancellation, application exit, or startup failure, clean up owned processes and recover the UI.

Keep runtime logs available through an expandable troubleshooting panel. Show a useful explanation and next step instead of dumping a traceback into the main interface.

Use one loaded model and one active generation or tuning job at a time in version 1.0. Prevent simultaneous chat and tuning from competing for memory.

## 6. Hardware inspection and memory planning

Detect:

- OS, architecture, CPU identity, physical/logical cores.
- Total and currently available RAM.
- Swap information where available.
- GPU devices and backend availability.
- Dedicated total/free VRAM where reliable.
- Integrated/shared memory as a distinct category.
- Storage free space.
- AC/battery state where available.

Give observations a timestamp. Recheck available memory before loading or benchmarking.

Missing GPU telemetry must produce “Unavailable,” never an invented value or a false “No GPU.” Detecting a GPU is separate from confirming a usable runtime backend.

Read GGUF metadata with a maintained reader or a bounded, well-tested parser. Validate file headers and lengths without loading entire weights into Python memory. Identify architecture, tensor information, quantization, context metadata, and chat-template availability when present.

Reject corrupted files safely. Recognize split models and either support all shards correctly or explain that the initial release does not support them.

Memory estimates must account for:

- Actual tensor/weight sizes and their expected placement.
- Context/KV cache where the architecture allows a meaningful estimate.
- Backend compute buffers and runtime overhead.
- Application and operating-system headroom.
- Uncertainty, memory mapping, and shared-memory behavior.

Use a configurable conservative reserve. Start with at least the larger of 2 GiB or 20% of total system RAM, and a separate dedicated-VRAM margin where applicable; treat these as initial product heuristics, not guarantees.

Do not use one KV-cache formula for every architecture. Unsupported architectures should receive a limited-confidence estimate or an unsupported result.

Classify a configuration as “Likely to fit,” “Close to memory limits,” “Unlikely to fit,” or “Not enough information.” Explain why. Successful loading alone does not prove smooth performance.

Avoid recommending configurations that depend on sustained disk swapping. Do not change OS swap settings, drivers, clocks, BIOS settings, or power plans.

## 7. Desktop UI requirements

Create a polished, restrained desktop interface that feels like a useful personal tool.

Visual direction:

- Dark charcoal surfaces, readable off-white text, muted blue accents.
- One clear type hierarchy, consistent spacing, and restrained rounded corners.
- Proper icons, clear labels, and generous reading space.
- A light theme using the same design rules.
- No neon gradients, fake terminal effects, meaningless charts, or oversized marketing panels.
- Use lightweight bundled or system fonts and properly licensed assets.

Sidebar screens:

- Chat.
- Models.
- Optimize.
- Benchmarks.
- Settings.

Hardware summary belongs in the model and optimization flows rather than requiring another dashboard.

Chat screen:

- Model selector and load/unload control.
- Persistent loading/ready/generating/error status.
- Conversation list and new-chat action.
- Streaming Markdown text and readable code blocks with copy buttons.
- Multiline composer: Enter sends, Shift+Enter inserts a newline.
- Stop, retry, and edit/resend behavior that preserves a coherent conversation.
- Optional generation speed, context usage, and available memory details.
- Clear empty states and actionable errors.

Models screen:

- Add model through a file picker and drag-and-drop.
- Show name, path, file size, quantization, architecture, and compatibility status.
- “Remove from library” removes the registry entry only. Any disk deletion must be a separate explicit action.
- Display missing or moved files and allow relinking.

Optimize screen:

- Hardware snapshot, model selection, requested context, and current profile.
- Quick Tune and Thorough Tune with candidate/time budgets.
- Visible progress, candidate results, cancel action, and last stable profile.
- Compare baseline and selected configuration.
- “Apply profile” and “Restore baseline.”
- Explain setting changes in simple language.

Support keyboard navigation, visible focus, readable contrast, accessible labels, scaling at 100–200%, and usable layouts at 1280×720. Respect reduced-motion settings.

The UI must remain interactive during model loading and inference. Stream updates in batches so that long responses do not trigger expensive full-document rendering for every token.

## 8. Chat and local persistence

Use the pinned server's supported streaming chat endpoint and model chat template.

Implement new, rename, delete, reopen, and export conversation actions. Export Markdown and JSON. Store messages, roles, timestamps, model identity, generation settings, and interrupted/error state.

Handle fragmented streaming events, partial UTF-8 data, cancellations, timeouts, and runtime failures. Preserve partial answers when generation stops.

Use backend-aware token counting where available. Mark fallback counts as approximate. Reserve room for the answer. Before exceeding context, explain the limit and offer a transparent history-trimming strategy that preserves the system instruction and latest request. Do not silently remove important messages.

Provide basic system-prompt and sampling controls with safe defaults. Do not claim that unsupported models understand every role or template.

Use transactional SQLite writes, schema migrations, and recovery-friendly exports. Store data in the user's application directory. Do not write model files or user data into the installation directory.

Chats and diagnostics stay local. Do not log prompt text by default. No telemetry or automatic external requests. Explicit runtime downloads and user-opened links are the permitted network exceptions.

Do not automatically execute model-generated commands or tools.

## 9. Benchmarking and automatic tuning

The optimizer is the distinguishing feature. Make it an evidence-based search rather than a renamed launch preset.

Create a stable baseline first. Define its exact settings in the report.

Tune only settings supported by the pinned runtime, such as:

- GPU offloaded layers.
- CPU thread counts.
- Batch and microbatch sizes.
- Supported attention and KV-cache options.

Hold the model weights, requested context capacity, and workload constant for baseline-versus-tuned comparisons. Smaller context is a separate trade-off recommendation, not proof of an equivalent optimization. Cache-format changes must be disclosed; throughput tests do not establish unchanged answer quality.

Use a bounded staged search, not an exhaustive Cartesian sweep. Quick Tune should screen up to 6 candidates; Thorough Tune up to 12 by default. Let the user set a time budget and cancel.

For each candidate:

1. Refresh memory observations and check conservative eligibility.
2. Start an owned runtime or benchmark process.
3. Apply timeouts and memory-pressure guards.
4. Warm up before collecting samples.
5. Collect repeated measurements.
6. Validate the candidate in real server chat, not only llama-bench.
7. Stop its processes and record the result.

Measure separately:

- Prompt processing throughput.
- Generated tokens per second.
- Time from request submission to the first generated token.
- Model load time.
- Sampled process RAM and dedicated VRAM where available.
- Errors, timeouts, and detected memory pressure.

Define units and timing boundaries. Do not infer token counts from character counts. Distinguish total GPU usage from process-attributable usage. Label sampled peaks as sampled; brief peaks may be missed.

Use at least three measured repetitions for finalist and baseline comparisons, with warm-up excluded. Keep inference cache conditions consistent. Include a short workload and a longer workload that exercises the chosen context depth. Randomize or interleave comparisons where practical to reduce thermal and background-load bias.

Report individual samples, median, variation, and exact test conditions. Record model fingerprint, runtime build, backend, hardware, driver details where available, requested/actual settings, workload, date, and AC/battery state.

Choose a stable winner using a documented objective: generation speed with memory and latency limits. If no convincing improvement is measured, retain the baseline and say so.

Never advertise a global best configuration. Profiles apply to the tested model, runtime, hardware, and workload. Revalidate when those change.

Do not unload a working chat model for tuning without explaining the transition. After cancelled or failed tuning, restore the last stable configuration when resources permit.

## 10. Optional CLI

Use the same services and database as the GUI.

Implement:

```text
inferlm doctor
inferlm models add PATH
inferlm models list
inferlm chat --model MODEL_ID
inferlm benchmark --model MODEL_ID
inferlm optimize --model MODEL_ID --mode quick
inferlm profiles list
inferlm profiles apply PROFILE_ID
inferlm export-benchmark RUN_ID --format json
```

Provide useful help, exit codes, Ctrl+C cleanup, styled human-readable output, and JSON output for suitable commands. The CLI must work without loading Qt. Coordinate GUI/CLI access so they cannot unintentionally run competing inference jobs.

## 11. Implementation milestones and acceptance gates

Complete these in order. Start implementing milestone 0 in the first response.

### Milestone 0 — Foundation

Create the project, shared types, storage, GUI shell, CLI entry point, configuration, test setup, and status file.

Acceptance: the GUI opens, the CLI help works, application directories are correct, and tests run. Any demonstration data is explicitly labelled and separate from production behavior.

### Milestone 1 — Hardware and model import

Implement hardware providers, GGUF validation, model registry, and initial memory planning.

Acceptance: import a valid fixture, reject malformed files, handle missing telemetry, relink a moved model, and inspect hardware without freezing the interface. Test 8 GB and 16 GB hardware fixtures, including dedicated and shared-memory cases.

### Milestone 2 — Real inference and chat

Implement runtime capabilities, process management, streaming chat, cancellation, context handling, and persistence.

Acceptance: load an actual compatible GGUF model, generate a real response, stop generation, reopen the conversation, unload the model, and verify no owned runtime is left behind. Use a small appropriately licensed model for a real CPU smoke test when downloads are available.

### Milestone 3 — Benchmarking

Implement structured llama-bench parsing, server timing, memory sampling, reports, and exports.

Acceptance: save real benchmark samples with provenance; distinguish load time, prompt processing, and generation; handle invalid output, crash, timeout, and cancellation. Fake runtime tests must be labelled as such.

### Milestone 4 — Optimization

Implement bounded search, safety checks, candidate ranking, profile application, and rollback.

Acceptance: never promote failed candidates; retain baseline when improvements are inconclusive; preserve requested context for equivalent comparisons; cancel cleanly; invalidate stale profiles. Verify the actual selected configuration through server chat.

### Milestone 5 — Desktop quality

Finish themes, accessibility, conversation actions, model management, troubleshooting, and CLI coordination.

Acceptance: validate keyboard use, scaling, narrow layouts, long chats, database migrations, missing runtime, occupied ports, corrupted files, and repeated load/unload cycles.

### Milestone 6 — Packaging and release readiness

Build available platform packages, add CI, write documentation, produce release notes and checksums, and inspect packaged startup.

Acceptance: a clean supported test machine can launch the app without a Python development environment; use an imported model; chat offline; restart without losing data; and exit without orphaned processes. Record separately which operating systems and GPU backends were actually verified.

Use development versions before 1.0. Do not label the release 1.0 merely because files exist. Unavailable hardware tests remain explicit release limitations.

## 12. Test strategy

Use meaningful tests for the risky behavior:

- Hardware-provider failures and stale observations.
- Invalid, truncated, and unsupported GGUF files.
- Different server and benchmark capability maps.
- Process ownership, port conflicts, startup failure, and shutdown.
- Streaming data fragmented across arbitrary boundaries.
- Interrupted chat persistence and context limits.
- SQLite migrations, transactions, and shared-service access.
- Candidate rejection, cancellation, rollback, and no-improvement results.
- Profile invalidation and honest measurement labels.
- Paths with spaces and non-English characters.
- Offline operation and unexpected network requests.
- Packaged resource paths and runtime discovery.

Use deterministic fake runtimes for repeatable failure tests, plus real CPU integration tests. Neither mocked GPU telemetry nor a configured CI workflow proves real GPU performance or successful execution.

Run lint, type checks, unit tests, integration tests, and available GUI tests. Keep a Windows/Linux test matrix. Clearly separate passed, failed, skipped, and manual checks.

Create a concise manual hardware checklist for 8 GB RAM/4 GB VRAM and 16 GB RAM/6–8 GB VRAM systems. Do not fill it with fabricated results.

## 13. Packaging

Provide:

- Windows standalone portable ZIP first.
- An installer only after the portable build is verified.
- Linux standalone archive first; AppImage only after it is validated.
- Python source installation for developers.
- Separate documented CPU and accelerated runtime options.

Build on the intended operating system using CI runners where available. Do not imply that creating a Windows workflow in Linux produces a tested Windows executable.

Bundle required Qt plugins, assets, runtime licenses, and notices. Do not bundle model weights. Document Linux system-library requirements and supported hardware instructions.

Pin the runtime and dependencies; record build metadata and SHA-256 checksums. Include GPU runtime requirements and permitted redistribution notices. Keep user data across upgrades and uninstallations unless the user explicitly requests removal.

If signing credentials are absent, label binaries as unsigned. Do not claim signing, notarization, or a reproducible binary build without verification.

## 14. GitHub and release instructions

Prepare a GitHub-ready project. Use the connected account only after verifying ownership and repository access. Do not overwrite an existing unrelated repository.

Include:

- README with installation, model import, local chat, optimization, CLI examples, limitations, and troubleshooting.
- ARCHITECTURE.md and TESTING.md.
- CHANGELOG.md and PROJECT_STATUS.md.
- MIT license for original code, plus correct third-party notices.
- CONTRIBUTING.md, issue templates, and release checklist.
- Windows/Linux CI for checks and packaging.
- Release notes describing features, supported platforms, runtime version, evidence, and known limitations.

Keep model weights, personal chats, tokens, local databases, and generated build files out of source control.

Prepare a draft release where authorized tools allow it. Otherwise provide exact PowerShell and Linux commands for repository creation, first push, tag creation, and draft release upload. Preserve release history; never overwrite an existing tag or asset silently.

Attach only artifacts that were actually built, with checksums. Prepare public publication for review; do not claim it is published without a returned release URL.

## 15. Delivery and immediate next action

Deliver the complete source project and a convenient source archive. Save deliverables using the persistent file mechanism available in ChatGPT Work, except repository-backed work that already has durable Git storage.

At completion, report:

1. What is implemented.
2. Exact setup and launch commands.
3. Packages actually produced.
4. Tests passed and checks still unverified.
5. Any genuine hardware measurements.
6. Known limitations and remaining release gates.
7. Repository or draft-release links if created.

Do not call an untested scaffold production-ready. Do not stop after proposing the directory structure. Do not hide unfinished features behind buttons that appear to work.

**Begin now: inspect the environment, establish the project, write a short milestone plan, and implement milestone 0. Continue to the next milestone as soon as its acceptance checks pass.**

---

## Source basis and credibility

This specification is an engineering plan grounded in official runtime and desktop deployment documentation. It is not a benchmark report, a completed application, or proof of performance on any laptop. Architecture choices, safety reserves, candidate limits, and milestone gates are design recommendations. Recheck the pinned versions during implementation.

Official sources, in MLA style:

ggml-org. “llama.cpp/tools/llama-bench.” *GitHub*, https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md. Accessed 12 Oct. 2026.

ggml-org. “llama.cpp/tools/server.” *GitHub*, https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md. Accessed 12 Oct. 2026.

The Qt Company. “pyside6-deploy: The Deployment Tool for Qt for Python.” *Qt for Python*, https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html. Accessed 12 Oct. 2026.

