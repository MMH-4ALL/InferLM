# Build and release
0.1.0 is a development release. Do not call it 1.0 until the full target-device
matrix passes. Existing workflow definitions are not proof that CI ran.

Build natively on the intended OS:
```text
python -m pip install -e ".[gui,cli,dev,packaging]"
python scripts/package.py --build-runtime
```
PyInstaller onedir preserves Qt shared libraries. CPU runtime download is
explicit and pinned. Packages are unsigned. Windows binaries require a Windows
runner; a Linux build cannot prove Windows support.

Verify GUI startup/exit and actual imported-model chat offline. Check saved data
after restart and confirm no owned runtime is left behind. Review licenses.
Signed installer/AppImage work is deferred.

## GitHub private repository and draft release
Verify the connected account. Replace OWNER with that account. Inspect an
existing repository before setting a remote or pushing. Never overwrite tags.

Linux:
```bash
git init -b main
git add .
git commit -m "Build InferLM 0.1.0 local desktop application"
gh auth status
gh repo create OWNER/inferlm --private --source=. --remote=origin --push
git tag -a v0.1.0 -m "InferLM 0.1.0 development release"
git push origin v0.1.0
gh release create v0.1.0 dist/InferLM-* --draft --title "InferLM 0.1.0" --notes-file docs/RELEASE_NOTES.md
```

PowerShell:
```powershell
git init -b main
git add .
git commit -m "Build InferLM 0.1.0 local desktop application"
gh auth status
gh repo create OWNER/inferlm --private --source=. --remote=origin --push
git tag -a v0.1.0 -m "InferLM 0.1.0 development release"
git push origin v0.1.0
$assets = Get-ChildItem dist/InferLM-* | Select-Object -ExpandProperty FullName
gh release create v0.1.0 @assets --draft --title "InferLM 0.1.0" --notes-file docs/RELEASE_NOTES.md
```

Attach only actually built files and checksums. Public visibility/publication
is a final review step. Preserve release history.

