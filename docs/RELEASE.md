# Build and release
0.2.0 is a development release. Do not call it 1.0 until the target-device matrix
passes. Workflow definitions alone are not evidence that a build ran.

The existing public repository is https://github.com/MMH-4ALL/InferLM.
Clone it or download its tagged source; do not recreate the repository.

## Native packages
GitHub: open Actions → Native unsigned packages → Run workflow. Each runner
builds the package for its own OS, bundles the pinned CPU runtime, and checks
GUI startup/exit. Download the matching artifact after a successful run.
Actual imported-model chat and saved-data checks remain separate release gates.

Local build on the intended OS:
```text
python -m pip install -r requirements-lock.txt
python -m pip install -e ".[gui,cli,packaging]"
python scripts/package.py --build-runtime
```
Package filenames/version metadata now derive from inferlm.__version__.
PyInstaller onedir preserves Qt shared libraries. Packages are unsigned.
A Linux build cannot prove Windows support. No model weights are bundled.

## Releases
Create releases from a verified commit and a new version tag. Never overwrite
existing tags. Mark development builds as prereleases and attach only actually
built assets/checksums. Source downloads are automatically supplied by GitHub
for the tagged version. Preserve earlier release history.
