# Windows VM test checklist

Run on the Windows VM (PowerShell, repo cloned, `git pull` first). Stop at the
first failure and open an issue with the **windows-finding** template
(`gh issue create --label windows`), pasting the full output. Never attach
logs, screenshots or real `.docx` files (see `CLAUDE.md`).

## M5 — packaged app

1. **Setup**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope Process Bypass
   pip install -r requirements.txt pyinstaller
   python -m playwright install chromium
   ```
2. **Tests from source** — each must print `ok`:
   ```powershell
   python -m tests.test_pipeline
   python -m tests.test_web
   python -m tests.test_diagnostico
   ```
3. **Self-test from source** — the line to watch is `credential store (keyring)`;
   it must pass on Windows (it only fails on Linux containers):
   ```powershell
   python -m scripts.run_web --selftest
   ```
4. **Build** (several minutes, ~900 MB):
   ```powershell
   python packaging\build.py
   ```
5. **Self-test the packaged app** — all 5 checks must pass:
   ```powershell
   dist\SGA-ANATER-Bot\SGA-ANATER-Bot.exe --selftest
   ```
6. **By hand**
   - Double-click `SGA-ANATER-Bot.exe`: a console opens, then the browser
     (a SmartScreen warning is expected: the app isn't signed).
   - Save the SGA credentials in the page; an entry named `sga-anater-bot`
     must appear in Windows Credential Manager.
   - Upload a `.docx`, tick "Teste sem salvar", run against the real site.
   - Logs must appear under `%APPDATA%\SGA-ANATER-Bot\logs`.

## What to record in the issue
- Which step number, the exact command, the **full** output.
- Windows version, Python version (`python --version`).
- For step 6: what you clicked, what you saw, what you expected.
