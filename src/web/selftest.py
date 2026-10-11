"""
`SGA-ANATER-Bot.exe --selftest` (or `python -m scripts.run_web --selftest`):
checks, on the machine it runs on, the things a packaged build tends to get
wrong. No SGA login, nothing is registered. Exit code 0 = all passed.
"""

import socket
import threading
import time
import urllib.request

from src import paths


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _check_page():
    import uvicorn

    from src.web.app import create_app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    try:
        for _ in range(50):
            if server.started:
                break
            time.sleep(0.1)
        html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode("utf-8")
        assert "SGA ANATER Bot" in html and "__TOKEN__" not in html, "page not served / token not injected"
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=5)
            raise AssertionError("API answered without a token")
        except urllib.error.HTTPError as e:
            assert e.code == 403, e.code
    finally:
        server.should_exit = True
        t.join(timeout=5)
    return "served the page, API needs the token"


def _check_browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("data:text/html,<title>ok</title>")
        assert page.title() == "ok"
        version = browser.version
        browser.close()
    return f"Chromium {version} launched"


def _check_keyring():
    import keyring
    from keyring.backends import fail

    backend = keyring.get_keyring()
    assert not isinstance(backend, fail.Keyring), f"no usable keyring backend ({backend})"
    return type(backend).__module__ + "." + type(backend).__name__


def _check_docx():
    import io

    import docx

    buf = io.BytesIO()
    docx.Document().save(buf)  # needs python-docx's bundled template
    return "python-docx template found"


def _check_dirs():
    out = []
    for d in (paths.logs_dir(), paths.templates_dir()):
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".write-test"
        probe.write_text("x")
        probe.unlink()
        out.append(str(d))
    return "writable: " + ", ".join(out)


CHECKS = [
    ("web page", _check_page), ("browser (Playwright/Chromium)", _check_browser),
    ("credential store (keyring)", _check_keyring), (".docx support", _check_docx),
    ("data folders", _check_dirs),
]


def run():
    failed = 0
    for name, fn in CHECKS:
        try:
            print(f"PASS  {name}: {fn()}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print("\nAll checks passed." if not failed else f"\n{failed} check(s) failed.")
    return 1 if failed else 0
