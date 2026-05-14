# Migration from Python/Tkinter OrionSSH to Electron OrionSSH

This project is a full Electron rewrite. The old Python `src/main.py` is intentionally replaced by the Electron architecture.

## What changed

- Terminal rendering moved from Tkinter Text + pyte to xterm.js.
- SSH moved from Paramiko to ssh2.
- SFTP is handled by ssh2 SFTP streams.
- Passwords are stored through OS keyring / Windows Credential Manager when available, with encrypted Electron safeStorage fallback.
- The app uses a custom Electron titlebar instead of the native Tkinter window frame.

## Recommended Git workflow

1. Create a branch:

```bash
git checkout -b electron-rewrite
```

2. Replace the repository contents with this Electron project.
3. Commit:

```bash
git add .
git commit -m "Rewrite OrionSSH with Electron, xterm.js and ssh2"
```

4. Push and open a Pull Request:

```bash
git push -u origin electron-rewrite
```

5. After testing, merge into `main`.

## Old Python files

These files are no longer needed in the Electron version:

```text
requirements.txt
src/main.py
installer/OrionSSH.iss
```

You can keep the Python version in a separate branch such as:

```text
legacy-python-tkinter
```
