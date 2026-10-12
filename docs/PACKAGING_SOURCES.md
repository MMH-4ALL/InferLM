# Packaging source basis
The initial specification proposed Nuitka. Startup validation rejected that
build for this dependency combination. The delivered Linux package uses
PyInstaller onedir instead, with shared Qt libraries and a verified CPU runtime.

Credibility: the switch is supported by actual startup/core tests, not an
assumption that compilation alone proves a working application.

PyInstaller Development Team. “Using PyInstaller.” *PyInstaller Documentation*,
https://pyinstaller.org/en/stable/usage.html. Accessed 12 Oct. 2026.
