"""
Fill layer — canonical schema -> site, via Playwright.

Browser automation for the Cadastrar UFPA page, login, and the
Consultar UFPA filter screen is grounded in the saved HTML captures in
examples/ (see site.py's module docstring for exactly what's confirmed
vs. still inferred). Diagnóstico T0 lives in diagnostico.py.

register_ufpa() is the end-to-end convenience entrypoint: extract -> build
schema -> pre-flight gate -> login -> navigate -> fill -> (pause on low
confidence) -> submit. Diagnóstico T0 (the questionnaire) is a
separate step: src.fill.diagnostico.run_diagnostico_t0() /
scripts.run_diagnostico (see docs/mapeamento.md).
"""

from src.extract import extract_docx
from src.fill.action_gate import ActionGate
from src.fill.credentials import load_credentials
from src.fill.review import SKIP, cli_review, pick_option
from src.fill.site import fill_cadastro_ufpa, login, open_cadastrar_ufpa, submit
from src.schema import build_schema
from src.schema.gate import MissingKeyDataError, check_blocking


def register_ufpa(page, docx_path=None, *, municipio, whatsapp_text=None, review_handler=cli_review,
                   auto_submit=False, gate=None, schema_panels=None, picker=pick_option, logged_in=False):
    """Runs one family's registration end to end on an already-launched
    Playwright `page`. Pauses (via `review_handler`) only on fields the
    schema layer flagged low confidence — everything else fills
    automatically, per docs/mapeamento.md.

    Two ways to get there, your choice:
      - pass `docx_path` (default): extracts + builds the schema in
        memory, right here, same as always. Low-confidence fields are
        reviewed inline as fill_cadastro_ufpa() reaches each one.
      - pass `schema_panels` instead (a list of CanonicalField, e.g. from
        src.schema.persist.load_panels() after running
        scripts/extract_schema.py separately): skips extraction and
        schema-build entirely and fills directly from it. `docx_path` /
        `whatsapp_text` are ignored in this case.
    Exactly one of the two must be given.

    Either way, the pre-flight gate (src.schema.gate.check_blocking) runs
    before touching the browser at all: if any Integrante is missing
    CPF, Nome, or Data de Nascimento, raises MissingKeyDataError listing
    every issue at once rather than burning a login session only to get
    stuck mid-fill — confirmed by Khalel as the 3 fields that should stop
    the whole run, not just pause for a quick review.

    Doesn't submit by default (`auto_submit=False`) — review the filled
    page first; call `src.fill.site.submit(page)` yourself once satisfied,
    or pass auto_submit=True to do it immediately.

    `gate` (src.fill.action_gate.ActionGate) pauses for an explicit
    allow/deny/quit before every state-changing Playwright action and
    logs the attempt (sanitized — see action_gate.py) for review
    afterward. Defaults to a fresh, prompting ActionGate (one real,
    timestamped log file per run) — pass ActionGate.noop() to run
    unattended (e.g. mock-page smoke tests).

    `picker` answers dropdowns with no matching option (a UI's
    pick_option); `logged_in=True` skips the login step when the caller
    (src.pipeline) already logged in on this `page`.
    """
    gate = gate or ActionGate()

    # count what a person had to decide during the fill (fields reviewed at
    # fill time, dropdown picks, and how many of those ended up skipped)
    stats = {"reviewed": 0, "picked": 0, "skipped": 0}

    def counting_review(field):
        decision = review_handler(field)
        stats["reviewed"] += 1
        stats["skipped"] += decision.value is SKIP
        return decision

    def counting_picker(*args, **kwargs):
        choice = picker(*args, **kwargs)
        stats["picked"] += 1
        stats["skipped"] += choice is SKIP
        return choice

    if schema_panels is not None:
        panels = schema_panels
    elif docx_path is not None:
        from src.extract import extract_whatsapp_text

        records = extract_docx(docx_path)
        whatsapp_data = extract_whatsapp_text(whatsapp_text) if whatsapp_text else None
        panels = build_schema(records, whatsapp_data=whatsapp_data)["panels"]
    else:
        raise ValueError("register_ufpa() needs either docx_path or schema_panels")

    blocking = check_blocking(panels)
    if blocking:
        raise MissingKeyDataError(blocking)

    if not logged_in:
        usuario, senha = load_credentials()
        login(page, usuario, senha, gate)
    open_cadastrar_ufpa(page, municipio=municipio, gate=gate)
    fill_cadastro_ufpa(page, panels, counting_review, gate, counting_picker)

    if auto_submit:
        submit(page, gate)

    return {"panels": panels, "summary": summarize_panels(panels, **stats)}


def summarize_panels(panels, *, reviewed=0, picked=0, skipped=0):
    """What a registration run did, per panel: field count, and rows for the
    repeatable panels / people for Integrantes. `reviewed`/`picked`/`skipped`
    are what a person decided while filling."""
    per_panel = {}
    rows = {}
    for f in panels:
        base = f.panel.split("[")[0]
        per_panel[base] = per_panel.get(base, 0) + 1
        if "[" in f.panel:
            rows.setdefault(base, set()).add(f.panel)
    return {
        "fields": len(panels),
        "per_panel": per_panel,
        "rows": {k: len(v) for k, v in rows.items()},
        "reviewed_at_fill": reviewed,
        "options_picked": picked,
        "skipped_at_fill": skipped,
    }


__all__ = ["register_ufpa"]
