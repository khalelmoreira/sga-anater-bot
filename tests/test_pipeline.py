"""
Offline checks for src/pipeline.py + src/ui.py (no browser, no network).
Run with:

    python -m tests.test_pipeline
"""

import os
import tempfile

from src.fill.action_gate import AbortRun, ActionGate
from src.fill.review import SKIP, ReviewDecision
import src.pipeline as pipeline
from src.pipeline import RunInputs, prepare
from src.schema.persist import indicadores_path, load_indicadores, load_panels
from src.schema.gate import MissingKeyDataError

EX = os.path.join(os.path.dirname(__file__), "..", "examples")
DOCX = os.path.join(EX, "example.docx")


class ScriptedUI:
    """Records every interaction; answers reviews by keeping the value."""

    def __init__(self, action_answers=()):
        self.events = []
        self._actions = list(action_answers)

    def progress(self, step, detail=""):
        self.events.append(("progress", step))

    def review(self, field):
        self.events.append(("review", field.field))
        return ReviewDecision(field.value)

    def pick_option(self, field_label, wanted, options):
        self.events.append(("pick", field_label))
        return SKIP

    def confirm_action(self, n, description, label, safe_value):
        self.events.append(("action", n))
        return self._actions.pop(0) if self._actions else "y"

    def confirm_save(self, kind, message):
        return True

    def report(self, summary):
        self.events.append(("report",))


def test_gate_blocks_before_any_review():
    # the mock example.docx has no birth date for integrante 1 (see mapeamento.md)
    ui = ScriptedUI()
    try:
        prepare(RunInputs(docx_path=DOCX, use_whatsapp=False, do_registration=False), ui)
    except MissingKeyDataError:
        assert not [e for e in ui.events if e[0] == "review"], "no review before the gate passes"
    else:
        raise AssertionError("expected MissingKeyDataError")


def test_prepare_reviews_only_low_confidence_and_saves():
    ui = ScriptedUI()
    out = os.path.join(tempfile.mkdtemp(), "schema.json")
    real_gate, pipeline.check_blocking = pipeline.check_blocking, lambda panels: []  # example.docx is incomplete on purpose
    try:
        prepared = prepare(RunInputs(docx_path=DOCX, use_whatsapp=False, do_registration=False, save_schema_to=out), ui)
    finally:
        pipeline.check_blocking = real_gate

    reviewed = [e for e in ui.events if e[0] == "review"]
    assert reviewed and len(reviewed) == prepared.reviewed - prepared.skipped
    assert all(f.confidence == "high" for f in prepared.panels), "every field is resolved before a browser opens"
    assert prepared.nome

    # the saved schema round-trips and is reusable as schema_path (no review the second time)
    assert len(load_panels(out)) == len(prepared.panels)
    assert len(load_indicadores(indicadores_path(out))) == len(prepared.answers)
    ui2 = ScriptedUI()
    again = prepare(RunInputs(schema_path=out, do_registration=False), ui2)
    assert not [e for e in ui2.events if e[0] == "review"]
    assert again.nome == prepared.nome and len(again.panels) == len(prepared.panels)


def test_input_validation():
    for bad in (RunInputs(), RunInputs(docx_path=DOCX, schema_path="x"), RunInputs(docx_path=DOCX)):
        try:
            prepare(bad, ScriptedUI())
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


def test_gate_asks_the_ui():
    ui = ScriptedUI(action_answers=["y", "n", "q"])
    gate = ActionGate.__new__(ActionGate)  # no log file / dirs needed
    ActionGate.__init__(gate, log_path=os.path.join(tempfile.mkdtemp(), "log.jsonl"), ui=ui)
    ran = []
    assert gate.confirm("first", lambda: ran.append(1) or "ok") == "ok"
    assert gate.confirm("second", lambda: ran.append(2)) is None  # denied
    try:
        gate.confirm("third", lambda: ran.append(3))
    except AbortRun:
        pass
    else:
        raise AssertionError("q must abort")
    assert ran == [1]
    assert [e for e in ui.events if e[0] == "action"] == [("action", 1), ("action", 2), ("action", 3)]


def test_auto_allow_until_does_not_prompt():
    ui = ScriptedUI()
    gate = ActionGate(log_path=os.path.join(tempfile.mkdtemp(), "log.jsonl"), auto_allow_until=2, ui=ui)
    for i in range(3):
        gate.confirm(f"a{i}", lambda: None)
    assert [e for e in ui.events if e[0] == "action"] == [("action", 3)]


if __name__ == "__main__":
    test_gate_blocks_before_any_review()
    test_prepare_reviews_only_low_confidence_and_saves()
    test_input_validation()
    test_gate_asks_the_ui()
    test_auto_allow_until_does_not_prompt()
    print("ok")
