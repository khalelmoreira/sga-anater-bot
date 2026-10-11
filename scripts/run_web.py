"""
Starts the local web UI and opens it in the default browser.

    python -m scripts.run_web            # http://127.0.0.1:8765
    python -m scripts.run_web --port 9000 --no-browser
"""

import argparse
import threading
import webbrowser

import uvicorn

from src.web.app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"SGA ANATER Bot: {url}  (Ctrl+C to stop)")
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
