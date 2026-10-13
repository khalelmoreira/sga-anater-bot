"""
Builds the double-click app with PyInstaller (one folder, Chromium inside).

    python packaging/build.py

Run it ON Windows to get a Windows build (PyInstaller doesn't cross-compile);
on Linux/macOS it builds a native binary, which is only useful to check the
bundling. Output: dist/SGA-ANATER-Bot/ (and dist/SGA-ANATER-Bot.zip).

Requires: pip install -r requirements-dev.txt
Then check the build with:  dist/SGA-ANATER-Bot/SGA-ANATER-Bot --selftest
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "SGA-ANATER-Bot"


def run(cmd, **kw):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def main():
    # Chromium goes inside the playwright package (PLAYWRIGHT_BROWSERS_PATH=0),
    # so --collect-all playwright below bundles it with the driver.
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": "0"}
    run([sys.executable, "-m", "playwright", "install", "chromium"], env=env)

    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", NAME,
        "--add-data", f"src/web/static{sep}src/web/static",
        "--collect-all", "playwright",
        "--collect-data", "docx",
        "--collect-submodules", "uvicorn",
        "--collect-submodules", "keyring",
        "--copy-metadata", "keyring",
    ]
    if sys.platform == "win32":
        cmd += ["--hidden-import", "keyring.backends.Windows"]
    cmd.append("scripts/run_web.py")
    run(cmd, env=env)

    out = ROOT / "dist" / NAME
    shutil.make_archive(str(ROOT / "dist" / NAME), "zip", ROOT / "dist", NAME)
    print(f"\nBuilt {out}\nZip:   {out}.zip\nCheck: {out / NAME} --selftest")


if __name__ == "__main__":
    main()
