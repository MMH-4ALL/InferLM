# InferLM architecture
The desktop GUI and optional CLI share core.services.Services. Core modules
import no Qt. The UI owns one cancellable job at a time; background results
reach Qt through signals. Streaming UI updates are batched as plain text,
with Markdown rendered after completion.

A versioned SQLite transactional record store opens a connection per operation.
WAL permits background work without sharing connections across threads.
Record kinds: models, conversations, config, active_settings, benchmarks, profiles.
A newer schema is rejected. Interrupted "generating" messages are recovered
only when another live process does not own the inference lease.

A shared OS file lock coordinates GUI/CLI inference. A loaded model keeps its
lease until unload. Tuning uses the same reentrant lease for its full experiment.

Server and benchmark capabilities are inspected independently from help/version
output and available-device lists. A CPU build cannot claim GPU offload.
Inference runs in an owned child process, bound to 127.0.0.1 with random local
authentication. Proxy settings are disabled for HTTP requests. Ambient LLAMA_*
launch settings are removed. No model-generated command is executed.

GGUF imports read bounded metadata, verify known tensor block lengths and
fingerprint the full file. Weights remain at their original path. Split and
unvalidated quantization types are rejected. Loading/profiles recheck identity.

Memory planning separates dedicated VRAM from RAM. Dense grouped-query
attention uses full-context f16 K/V; unknown architectures have no confident
KV estimate. File-backed weights conservatively remain reserved in system RAM,
so some practical offloaded models may be rejected. Compute overhead is a
disclosed heuristic. The reserve is at least 2 GiB/20% RAM and may be raised.

Native measurements use 3 post-warm-up repetitions at two context depths.
Server validation uses warm-up plus 3 repetitions for each of two prompts,
sized by the actual tokenizer. Reports keep individual measurements, medians,
variation, timing boundaries, hardware and runtime identity.

Tuning preserves weights, cache format, context capacity and workloads.
It searches up to 6/12 candidates, enforces memory/time limits and a TTFT
regression limit, then rechecks the baseline before accepting an improvement.
The noise/5% threshold is a conservative heuristic, not a statistical proof
or a guarantee of global optimality. Answer quality is not measured.

Profiles bind model SHA-256, CPU/GPU identity, RAM capacity, GPU driver and
runtime version. Applying a profile updates saved settings; reload to apply.

Native packaging uses PyInstaller onedir, preserving shared Qt libraries.
An earlier Nuitka/PySide build failed startup validation and is not distributed.

