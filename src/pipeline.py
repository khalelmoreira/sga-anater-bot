"""
One call for the whole job: .docx (+ WhatsApp template) -> schema ->
pre-flight gate -> review -> registration -> Diagnóstico T0 -> summary.

Replaces running scripts/extract_schema, run_registration and
run_diagnostico by hand (they are now thin wrappers around this). Every
question to the person goes through the `UI` (src/ui.py); nothing here
prints or reads the terminal. See docs/produto.md.

Failures propagate as the same exceptions the fill layer raises
(MissingKeyDataError, AbortRun, UfpaNotFound, UfpaAlreadyFinalized,
WrongUfpa, MissingCredentialsError) — the caller decides how to show them.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.entitlement import AlwaysAllow
from src.extract import extract_docx, extract_whatsapp_text, find_pa_municipio, load_whatsapp_text
from src.fill import register_ufpa
from src.fill.action_gate import ActionGate
from src.fill.credentials import load_credentials
from src.fill.diagnostico import UfpaNotFound, run_diagnostico_t0, salvar
from src.fill.review import resolve, resolve_indicadores
from src.fill.site import login, submit
from src.schema import build_schema
from src.schema.gate import MissingKeyDataError, check_blocking
from src.schema.persist import (
    indicadores_path, load_indicadores, load_panels, save_indicadores, save_panels,
)


@dataclass
class RunInputs:
    # exactly one of these two
    docx_path: str | None = None
    schema_path: str | None = None  # panels JSON from a previous run (its .diagnostico.json sibling is used too)

    municipio: str | None = None    # required when registering
    nome: str | None = None         # UFPA name to look up in Diagnóstico (default: read from the schema)
    use_whatsapp: bool = True
    whatsapp_text: str | None = None  # explicit text; otherwise the PA template is looked up

    do_registration: bool = True
    do_diagnostico: bool = True
    auto_submit: bool = False       # click the registration Salvar without asking
    auto_save: bool = False         # click the Diagnóstico Salvar without asking
    dry_run: bool = False           # fill everything, never click either Salvar (and don't ask)

    headless: bool = False
    auto_allow: bool = False
    auto_allow_until: int = 0
    screenshots: bool = True
    save_schema_to: str | None = None  # also persist the resolved schema here
    credentials: tuple[str, str] | None = None  # (usuario, senha); default: env

    def validate(self):
        if bool(self.docx_path) == bool(self.schema_path):
            raise ValueError("pass exactly one of docx_path or schema_path")
        if self.do_registration and not self.municipio:
            raise ValueError("municipio is required to register")
        if not (self.do_registration or self.do_diagnostico):
            raise ValueError("nothing to do: both phases are off")


@dataclass
class Prepared:
    panels: list
    answers: list
    nome: str | None
    reviewed: int  # low-confidence fields + answers a person resolved
    skipped: int   # ... of which were skipped


def _whatsapp_text(inputs, ui):
    if inputs.whatsapp_text:
        return inputs.whatsapp_text
    if not inputs.use_whatsapp:
        return None
    pa_nome, municipio = find_pa_municipio(inputs.docx_path)
    if not (pa_nome and municipio):
        return None
    text = load_whatsapp_text(pa_nome, municipio)
    if text is None:
        ui.progress(f"No WhatsApp template found for '{pa_nome} - {municipio}' in data/acoes_potenciais/ "
                    "-- Ações Potenciais will be left for a low-confidence pause")
    return text


def prepare(inputs, ui) -> Prepared:
    """Everything that needs no browser: extract (or load), pre-flight gate,
    resolve low-confidence fields with `ui.review`, optionally save."""
    inputs.validate()

    if inputs.schema_path:
        panels = load_panels(inputs.schema_path)
        ind_file = indicadores_path(inputs.schema_path)
        answers = load_indicadores(ind_file) if inputs.do_diagnostico else []
        ui.progress("Loaded saved schema", f"{len(panels)} fields, {len(answers)} answers -- skipping extraction/review")
        reviewed = skipped = 0
    else:
        ui.progress("Reading the registration file")
        schema = build_schema(
            extract_docx(inputs.docx_path),
            whatsapp_data=(lambda t: extract_whatsapp_text(t) if t else None)(_whatsapp_text(inputs, ui)),
        )
        blocking = check_blocking(schema["panels"])
        if blocking:
            raise MissingKeyDataError(blocking)

        panels, answers = schema["panels"], schema["indicadores"]
        low = sum(f.confidence == "low" for f in panels) + sum(a.confidence == "low" for a in answers)
        if low:
            ui.progress("Reviewing fields that need a person", f"{low}")
        n_panels, n_answers = len(panels), len(answers)
        panels = resolve(panels, ui.review)
        answers = resolve_indicadores(answers, ui.review, notify=ui.progress)
        reviewed = low
        skipped = (n_panels - len(panels)) + (n_answers - len(answers))

        if inputs.save_schema_to:
            path = save_panels(panels, inputs.save_schema_to)
            save_indicadores(answers, indicadores_path(path))
            ui.progress("Saved resolved schema", path)

    nome = inputs.nome or next((f.value for f in panels if f.panel == "ufpa" and f.field == "Nome da UFPA"), None)
    if inputs.do_diagnostico and not nome:
        raise ValueError("couldn't read 'Nome da UFPA' from the schema -- pass nome")
    return Prepared(panels, answers, nome, reviewed, skipped)


def run_ufpa(inputs, ui, *, gate=None, entitlement=None) -> dict:
    """Runs the selected phases for one family and returns the summary
    handed to `ui.report`:
        {"registration": {fields, per_panel, rows, reviewed, options_picked, skipped, saved} | None,
         "diagnostico": <fill_questions summary + opened_as, saved> | None,
         "run_id": <unique per run>, "log": <action log path>}

    `entitlement` (src.entitlement) is the payment seam: checked first,
    consumed only after a registration was saved for real (never on a dry
    run or a failed run). Default: always allow.
    """
    entitlement = entitlement or AlwaysAllow()
    run_id = uuid.uuid4().hex
    inputs.validate()
    entitlement.check(inputs)
    prepared = prepare(inputs, ui)
    usuario, senha = inputs.credentials or load_credentials()

    gate = gate or ActionGate(
        auto_allow=inputs.auto_allow, screenshot=inputs.screenshots,
        auto_allow_until=inputs.auto_allow_until, ui=ui,
        cancel_check=getattr(ui, "cancelled", None),
    )
    ui.progress("Action log", str(gate.path))

    summary = {"run_id": run_id, "registration": None, "diagnostico": None, "log": str(gate.path) if gate.path else None}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=inputs.headless)
        try:
            page = browser.new_page()
            gate.attach_page(page)

            ui.progress("Logging in to SGA")
            login(page, usuario, senha, gate)

            if inputs.do_registration:
                ui.progress("Registering the UFPA")
                reg = register_ufpa(
                    page, schema_panels=prepared.panels, municipio=inputs.municipio,
                    review_handler=ui.review, gate=gate, picker=ui.pick_option, logged_in=True,
                )
                saved = not inputs.dry_run and (inputs.auto_submit or ui.confirm_save(
                    "registration", "Review the filled registration page in the browser."))
                if inputs.dry_run:
                    ui.progress("Dry run", "registration filled, NOT saved")
                if saved:
                    submit(page, gate)
                summary["registration"] = {
                    **reg["summary"],
                    "reviewed": prepared.reviewed + reg["summary"]["reviewed_at_fill"],
                    "skipped": prepared.skipped + reg["summary"]["skipped_at_fill"],
                    "saved": bool(saved),
                }
                if saved and not inputs.dry_run:
                    try:
                        entitlement.consume(run_id, inputs, summary)
                    except Exception as e:  # the UFPA IS saved: don't abort the rest of the run over billing
                        summary["entitlement_error"] = str(e)
                        ui.progress("Could not record this registration for billing", str(e))

            if inputs.do_diagnostico:
                ui.progress("Filling Diagnóstico T0")
                try:
                    diag = run_diagnostico_t0(
                        page, prepared.nome, prepared.answers,
                        review_handler=ui.review, gate=gate, picker=ui.pick_option,
                    )
                except UfpaNotFound as e:
                    if not (inputs.dry_run and inputs.do_registration):
                        raise
                    # expected: the registration above was never saved
                    ui.progress("Dry run", f"Diagnóstico skipped -- person not registered on the site ({e})")
                    diag = None
                if diag is not None:
                    saved = not inputs.dry_run and (inputs.auto_save or ui.confirm_save(
                        "diagnostico", "Review the Diagnóstico T0 page in the browser."))
                    if saved:
                        salvar(page, gate)
                    diag["saved"] = bool(saved)
                    summary["diagnostico"] = diag
        finally:
            browser.close()

    ui.report(summary)
    return summary
