"""
Offline checks for src/pipeline.py + src/ui.py (no browser, no network).
Run with:

    python -m tests.test_pipeline
"""

import os
import tempfile

from src.fill.action_gate import AbortRun, ActionGate
from src.fill import summarize_panels
from src.fill.review import SKIP, ReviewDecision, resolve_indicadores
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


def test_summarize_panels_counts_rows():
    from src.schema.model import CanonicalField
    import inspect
    names = [p for p in inspect.signature(CanonicalField).parameters]
    def f(panel):
        kw = {n: None for n in names}
        kw.update(panel=panel, field="x", value="v", confidence="high")
        return CanonicalField(**kw)
    panels = [f("ufpa"), f("ufpa"), f("plantel[0]"), f("plantel[0]"), f("plantel[1]"), f("integrantes[0]")]
    s = summarize_panels(panels, reviewed=2, picked=1, skipped=1)
    assert s["fields"] == 6 and s["per_panel"] == {"ufpa": 2, "plantel": 3, "integrantes": 1}
    assert s["rows"] == {"plantel": 2, "integrantes": 1}
    assert (s["reviewed_at_fill"], s["options_picked"], s["skipped_at_fill"]) == (2, 1, 1)


def test_resolve_indicadores_notifies_instead_of_printing():
    from src.schema.model import IndicadorAnswer
    import inspect
    kw = {n: None for n in inspect.signature(IndicadorAnswer).parameters}
    kw.update(indicator="i", question="q?", value="???", confidence="low", review_reason="r")
    msgs = []
    out = resolve_indicadores([IndicadorAnswer(**kw)], lambda f: ReviewDecision(SKIP), notify=msgs.append)
    assert out == [] and msgs and "q?" in msgs[0]


# ------------------------------------------------------------ entitlement
class _FakePlaywright:
    class _Browser:
        def new_page(self):
            return object()

        def close(self):
            pass

    class chromium:
        @staticmethod
        def launch(headless=False):
            return _FakePlaywright._Browser()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Recorder:
    def __init__(self, deny=None, consume_fails=False):
        self.calls, self.deny, self.consume_fails = [], deny, consume_fails

    def check(self, inputs):
        self.calls.append("check")
        if self.deny:
            from src.entitlement import NotEntitled
            raise NotEntitled(self.deny)

    def consume(self, run_id, inputs, summary):
        self.calls.append(("consume", run_id, summary["registration"]["saved"]))
        if self.consume_fails:
            raise RuntimeError("billing server down")


def _run(ent, *, dry_run=False, save=True, do_registration=True, do_diagnostico=False, register_raises=None):
    """run_ufpa with Playwright and the site steps faked out."""
    from src.fill.action_gate import ActionGate
    import src.pipeline as pl

    saved_calls = []
    originals = {k: getattr(pl, k) for k in ("sync_playwright", "login", "register_ufpa", "submit", "prepare", "run_diagnostico_t0")}
    pl.sync_playwright = _FakePlaywright
    pl.login = lambda *a, **k: None
    pl.submit = lambda *a, **k: saved_calls.append("submit")

    def fake_register(*a, **k):
        if register_raises:
            raise register_raises
        return {"summary": {"fields": 1, "per_panel": {"ufpa": 1}, "rows": {}, "reviewed_at_fill": 0,
                            "options_picked": 0, "skipped_at_fill": 0}}

    pl.register_ufpa = fake_register
    pl.prepare = lambda inputs, ui: pl.Prepared([], [], "Maria", 0, 0)
    pl.run_diagnostico_t0 = lambda *a, **k: {"opened_as": "Iniciar", "filled": 0, "already_answered": 0,
                                             "discrepancies": [], "left_blank": [], "unmatched_site": [],
                                             "unused_answers": []}
    ui = ScriptedUI()
    ui.confirm_save = lambda kind, message: save
    try:
        inputs = RunInputs(docx_path=DOCX, municipio="Claudia", do_registration=do_registration,
                           do_diagnostico=do_diagnostico, dry_run=dry_run, credentials=("1", "2"))
        return pl.run_ufpa(inputs, ui, gate=ActionGate.noop(), entitlement=ent), saved_calls
    finally:
        for k, v in originals.items():
            setattr(pl, k, v)


def test_entitlement_denied_stops_before_anything():
    from src.entitlement import NotEntitled
    ent = _Recorder(deny="Sem créditos")
    try:
        _run(ent)
    except NotEntitled as e:
        assert str(e) == "Sem créditos"
    else:
        raise AssertionError("expected NotEntitled")
    assert ent.calls == ["check"]


def test_entitlement_consumed_once_after_a_real_save():
    ent = _Recorder()
    summary, submitted = _run(ent)
    assert submitted == ["submit"]
    assert ent.calls[0] == "check" and len(ent.calls) == 2
    kind, run_id, saved = ent.calls[1]
    assert kind == "consume" and saved is True and run_id == summary["run_id"]


def test_entitlement_not_consumed_for_dry_run_unsaved_or_failed():
    for kw in ({"dry_run": True}, {"save": False}, {"do_registration": False, "do_diagnostico": True, "save": False}):
        ent = _Recorder()
        _run(ent, **kw)
        assert ent.calls == ["check"], (kw, ent.calls)

    ent = _Recorder()
    try:
        _run(ent, register_raises=RuntimeError("site changed"))
    except RuntimeError:
        pass
    assert ent.calls == ["check"]


def test_billing_failure_does_not_abort_after_save():
    ent = _Recorder(consume_fails=True)
    summary, submitted = _run(ent)
    assert submitted == ["submit"] and summary["registration"]["saved"]
    assert "billing server down" in summary["entitlement_error"]


def test_default_entitlement_allows():
    summary, submitted = _run(None)
    assert submitted == ["submit"]


if __name__ == "__main__":
    test_summarize_panels_counts_rows()
    test_resolve_indicadores_notifies_instead_of_printing()
    test_gate_blocks_before_any_review()
    test_prepare_reviews_only_low_confidence_and_saves()
    test_input_validation()
    test_gate_asks_the_ui()
    test_auto_allow_until_does_not_prompt()

    test_entitlement_denied_stops_before_anything()
    test_entitlement_consumed_once_after_a_real_save()
    test_entitlement_not_consumed_for_dry_run_unsaved_or_failed()
    test_billing_failure_does_not_abort_after_save()
    test_default_entitlement_allows()
    print("ok")
