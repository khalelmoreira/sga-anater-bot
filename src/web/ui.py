"""
WebUI: the src.ui.UI implementation behind the local web page.

The pipeline runs in a worker thread and blocks inside review() /
pick_option() / confirm_save() until the person answers in the browser
(POST /api/answer). The page polls the state, which includes the pending
prompt.
"""

import threading
import time

from src.fill.action_gate import AbortRun
from src.fill.review import SKIP, ReviewDecision, _rank_options

_CHOICES = ["Sim", "Não", "Não se Aplica"]


class WebUI:
    def __init__(self):
        self._lock = threading.RLock()
        self._answered = threading.Event()
        self._seq = 0
        self._answer = None
        self._cancel = False
        self.events = []
        self.prompt = None
        self.summary = None

    # ------------------------------------------------------------ state
    def cancelled(self):
        return self._cancel

    def cancel(self):
        self._cancel = True
        self._answered.set()  # wake a blocked prompt

    def snapshot(self, last_events=300):
        with self._lock:
            return {"events": self.events[-last_events:], "prompt": self.prompt, "summary": self.summary}

    def answer(self, prompt_id, answer):
        with self._lock:
            if not self.prompt or self.prompt["id"] != prompt_id:
                return False
            self._answer = answer
            self._answered.set()
            return True

    def _ask(self, kind, **payload):
        with self._lock:
            self._seq += 1
            self._answer = None
            self._answered.clear()
            self.prompt = {"id": self._seq, "kind": kind, **payload}
        self._answered.wait()
        with self._lock:
            answer, self.prompt = self._answer, None
        if self._cancel:
            raise AbortRun("cancelled")
        return answer or {}

    # -------------------------------------------------------- UI protocol
    def progress(self, step, detail=""):
        with self._lock:
            self.events.append({"t": time.strftime("%H:%M:%S"), "step": step, "detail": detail})

    def review(self, field):
        panel = str(field.panel)
        a = self._ask(
            "review", panel=panel, field=str(field.field), value=_text(field.value),
            reason=field.review_reason or "", choices=_CHOICES if panel.startswith("diagnostico_t0") else None,
        )
        if a.get("action") == "skip":
            return ReviewDecision(SKIP)
        if a.get("action") == "value":
            return ReviewDecision(a.get("value"))
        return ReviewDecision(field.value)

    def pick_option(self, field_label, wanted, options):
        a = self._ask("pick", field=str(field_label), wanted=_text(wanted), options=_rank_options(wanted, list(options)))
        if a.get("action") == "pick" and a.get("value") in options:
            return a["value"]
        return SKIP

    def confirm_action(self, n, description, label, safe_value):
        return "q" if self._cancel else "y"  # the web UI doesn't ask per click (still logged)

    def confirm_save(self, kind, message):
        return self._ask("save", save_kind=kind, message=message).get("action") == "save"

    def confirm_continue(self, kind, message):
        return self._ask("continue", continue_kind=kind, message=message).get("action") == "continue"

    def report(self, summary):
        with self._lock:
            self.summary = summary


def _text(value):
    return "" if value is None else str(value)
