"""
Fill layer — canonical schema -> site, via Playwright.

Browser automation for the Cadastrar UFPA page, login, and the
Consultar UFPA filter screen is grounded in the saved HTML captures in
examples/ (see site.py's module docstring for exactly what's confirmed
vs. still inferred). Diagnóstico T0 is not grounded or implemented yet.

register_ufpa() is the end-to-end convenience entrypoint: extract -> build
schema -> pre-flight gate -> login -> navigate -> fill -> (pause on low
confidence) -> submit. Diagnóstico T0 (the ~140-question follow-up) is a
separate step — not implemented yet, since the only panels mapped
field-by-field so far are the 8 Cadastrar UFPA ones (see
docs/mapeamento.md).
"""

from src.extract import extract_docx
from src.fill.action_gate import ActionGate
from src.fill.credentials import load_credentials
from src.fill.review import cli_review
from src.fill.site import fill_cadastro_ufpa, login, open_cadastrar_ufpa, submit
from src.schema import build_schema
from src.schema.gate import MissingKeyDataError, check_blocking


def register_ufpa(page, docx_path=None, *, municipio, whatsapp_text=None, review_handler=cli_review,
                   auto_submit=False, gate=None, schema_panels=None):
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
    """
    gate = gate or ActionGate()

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

    usuario, senha = load_credentials()
    login(page, usuario, senha, gate)
    open_cadastrar_ufpa(page, municipio=municipio, gate=gate)
    fill_cadastro_ufpa(page, panels, review_handler, gate)

    if auto_submit:
        submit(page, gate)

    return {"panels": panels}


__all__ = ["register_ufpa"]
