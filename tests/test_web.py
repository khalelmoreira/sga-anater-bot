"""
Offline checks for the web UI (src/web): FastAPI TestClient + a fake runner
standing in for the pipeline, so no browser and no OS keyring are involved.
Run with:

    python -m tests.test_web
"""

import os
import tempfile
import threading
import time

from fastapi.testclient import TestClient

from src.fill.action_gate import AbortRun
from src.fill.review import SKIP
from src.schema.gate import BlockingIssue, MissingKeyDataError
from src.web.app import create_app

EX = os.path.join(os.path.dirname(__file__), "..", "examples")
DOCX = open(os.path.join(EX, "example.docx"), "rb").read()


class MemCreds:
    def __init__(self, pair=None):
        self.pair = pair

    def load(self):
        return self.pair

    def save(self, u, s):
        self.pair = (u, s)

    def clear(self):
        self.pair = None


class Field:
    panel, field, value, review_reason, confidence = "ufpa", "Nome da UFPA", "Maria", "check it", "low"


def _client(runner, creds=None):
    app = create_app(runner=runner, work_dir=tempfile.mkdtemp(), credentials=creds or MemCreds(("12345678900", "pw")))
    c = TestClient(app)
    token = c.get("/").text.split('const TOKEN = "')[1].split('"')[0]
    c.headers["X-Token"] = token
    return c


def _wait(c, cond, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        s = c.get("/api/state").json()
        if cond(s):
            return s
        time.sleep(0.02)
    raise AssertionError(f"timeout; last state: {s}")


def _upload(c):
    r = c.post("/api/upload?name=a.docx", content=DOCX)
    assert r.status_code == 200, r.text
    return r.json()


def test_token_required_and_credentials():
    creds = MemCreds()
    c = _client(lambda i, u: None, creds)
    assert TestClient(c.app).get("/api/state").status_code == 403
    s = c.get("/api/state").json()
    assert s["credentials"] is False and s["status"] == "idle"
    assert c.post("/api/credentials", json={"usuario": "123", "senha": "x"}).status_code == 400
    assert c.post("/api/credentials", json={"usuario": "123.456.789-00", "senha": "pw"}).status_code == 200
    assert creds.pair == ("12345678900", "pw")
    assert "pw" not in c.get("/api/state").text
    c.delete("/api/credentials")
    assert creds.pair is None
    r = c.post("/api/run", json={"upload_id": "x", "municipio": "Claudia"})
    assert r.status_code == 400  # no credentials


def test_upload_reads_pa_and_rejects_non_docx():
    c = _client(lambda i, u: None)
    assert c.post("/api/upload?name=a.pdf", content=b"x").status_code == 400
    assert c.post("/api/upload?name=a.docx", content=b"").status_code == 400
    assert "upload_id" in _upload(c)


def test_full_run_with_prompts():
    seen = {}

    def runner(inputs, ui):
        seen["inputs"] = inputs
        ui.progress("Lendo o arquivo")
        seen["review"] = ui.review(Field())
        seen["pick"] = ui.pick_option("ufpa/Município", "Claudiaa", ["Claudia", "Feliz Natal"])
        seen["skip"] = ui.pick_option("x", "y", ["a"])
        seen["save"] = ui.confirm_save("registration", "Revise.")
        ui.report({"registration": {"fields": 1, "per_panel": {"ufpa": 1}, "rows": {}, "reviewed": 1,
                                    "options_picked": 1, "skipped": 0, "saved": seen["save"]}, "diagnostico": None})

    c = _client(runner)
    up = _upload(c)
    assert c.post("/api/run", json={"upload_id": up["upload_id"], "municipio": "Nope"}).status_code == 400
    assert c.post("/api/run", json={"upload_id": up["upload_id"], "municipio": "Claudia", "dry_run": True,
                                    "whatsapp_text": "  "}).status_code == 200
    assert c.post("/api/run", json={"upload_id": up["upload_id"], "municipio": "Claudia"}).status_code == 409

    p = _wait(c, lambda s: s["prompt"])["prompt"]
    assert p["kind"] == "review" and p["value"] == "Maria" and p["choices"] is None
    assert c.post("/api/answer", json={"id": p["id"] + 99, "answer": {}}).status_code == 409  # stale id
    assert c.post("/api/answer", json={"id": p["id"], "answer": {"action": "value", "value": "Maria S."}}).status_code == 200

    p = _wait(c, lambda s: s["prompt"] and s["prompt"]["kind"] == "pick")["prompt"]
    assert p["options"][0] == "Claudia"  # best match first
    c.post("/api/answer", json={"id": p["id"], "answer": {"action": "pick", "value": "Claudia"}})

    p = _wait(c, lambda s: s["prompt"] and s["prompt"]["kind"] == "pick")["prompt"]
    c.post("/api/answer", json={"id": p["id"], "answer": {"action": "skip"}})

    p = _wait(c, lambda s: s["prompt"] and s["prompt"]["kind"] == "save")["prompt"]
    c.post("/api/answer", json={"id": p["id"], "answer": {"action": "nosave"}})

    s = _wait(c, lambda s: s["status"] == "done")
    assert s["summary"]["registration"]["saved"] is False
    assert s["events"][0]["step"] == "Lendo o arquivo"
    assert seen["review"].value == "Maria S." and seen["pick"] == "Claudia" and seen["skip"] is SKIP
    i = seen["inputs"]
    assert i.dry_run and i.whatsapp_text is None and i.auto_allow and i.credentials == ("12345678900", "pw")

    c.post("/api/reset")
    assert c.get("/api/state").json()["status"] == "idle"


def test_diagnostico_review_offers_choices():
    class Ans:
        panel, field, value, review_reason = "diagnostico_t0 / UCM - X", "1. Pergunta?", "( x ) Sim ( x ) Não", "two marked"

    got = {}
    c = _client(lambda i, u: got.update(r=u.review(Ans())))
    c.post("/api/run", json={"upload_id": _upload(c)["upload_id"], "municipio": "Claudia"})
    p = _wait(c, lambda s: s["prompt"])["prompt"]
    assert p["choices"] == ["Sim", "Não", "Não se Aplica"]
    c.post("/api/answer", json={"id": p["id"], "answer": {"action": "value", "value": "Não"}})
    _wait(c, lambda s: s["status"] == "done")
    assert got["r"].value == "Não"


def test_preflight_error_is_plain_language():
    def runner(inputs, ui):
        raise MissingKeyDataError([BlockingIssue("integrantes[1]", "CPF", "required but empty")])

    c = _client(runner)
    c.post("/api/run", json={"upload_id": _upload(c)["upload_id"], "municipio": "Claudia"})
    s = _wait(c, lambda s: s["status"] == "error")
    assert s["error"]["kind"] == "preflight" and "integrantes[1] / CPF" in s["error"]["issues"][0]


def test_cancel_unblocks_a_waiting_prompt():
    def runner(inputs, ui):
        ui.confirm_save("registration", "x")

    c = _client(runner)
    c.post("/api/run", json={"upload_id": _upload(c)["upload_id"], "municipio": "Claudia"})
    _wait(c, lambda s: s["prompt"])
    c.post("/api/cancel")
    s = _wait(c, lambda s: s["status"] == "error")
    assert s["error"]["kind"] == "cancelled"


def test_cancel_check_stops_the_gate():
    from src.fill.action_gate import ActionGate
    flag = {"stop": False}
    gate = ActionGate(log_path=os.path.join(tempfile.mkdtemp(), "l.jsonl"), auto_allow=True, cancel_check=lambda: flag["stop"])
    assert gate.confirm("one", lambda: 1) == 1
    flag["stop"] = True
    try:
        gate.confirm("two", lambda: 2)
    except AbortRun:
        return
    raise AssertionError("cancel_check must abort")


if __name__ == "__main__":
    test_token_required_and_credentials()
    test_upload_reads_pa_and_rejects_non_docx()
    test_full_run_with_prompts()
    test_diagnostico_review_offers_choices()
    test_preflight_error_is_plain_language()
    test_cancel_unblocks_a_waiting_prompt()
    test_cancel_check_stops_the_gate()
    print("ok")
