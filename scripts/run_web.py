"""
Starts the local web UI and opens it in the default browser.

    python -m scripts.run_web            # http://127.0.0.1:8765
    python -m scripts.run_web --port 9000 --no-browser
    python -m scripts.run_web --selftest # checks the environment, then exits

This is also the entry point of the packaged Windows app (packaging/build.py).
"""

import argparse
import os
import socket
import sys
import threading
import webbrowser

# The packaged app ships Chromium inside the playwright package (built with
# PLAYWRIGHT_BROWSERS_PATH=0); point Playwright at it before it is imported.
if getattr(sys, "frozen", False):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

import uvicorn  # noqa: E402

from src.web.app import create_app  # noqa: E402


def _pick_port(preferred):
    """The preferred port if free, otherwise the next free one."""
    for port in range(preferred, preferred + 20):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(f"No free port between {preferred} and {preferred + 19}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--selftest", action="store_true", help="check browser, credential store and files, then exit")
    args = parser.parse_args()

    if args.selftest:
        from src.web.selftest import run
        sys.exit(run())

    port = _pick_port(args.port)
    url = f"http://127.0.0.1:{port}/"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"SGA ANATER Bot: {url}")
    print("Deixe esta janela aberta enquanto usa o programa. Feche-a para encerrar.")
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
