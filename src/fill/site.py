"""
Playwright automation for sga.anater.org.

Grounding, honestly stated:

  - Filling the 8 panels of "Cadastrar UFPA" (locators.py + fill_field()
    below) is grounded directly in the saved HTML captures in examples/
    (real ids, real radio/select structure) — see locators.py's docstring.
  - Login (`login()`) is grounded in examples/ANATER-login.html: a plain
    HTML form (not JSF) posting to /sgaLogin, not an xhtml page under
    /pages/ as originally assumed in docs/mapeamento.md.
  - The "Consultar UFPA" filter screen (`open_cadastrar_ufpa()`) is
    grounded in examples/ANATER -ufpa-cadastro.html (blank) and
    examples/ANATER -ufpa-cadastro-filled.html (filters set, Cadastrar
    button revealed) — real ids for Entidade/Projeto/Instrumento/Estado/
    Município and the real Cadastrar button. The one inferred (not
    directly captured) part is the sidebar's "UFPA" item expand — see
    that function's docstring.
  - Diagnóstico T0 (search + the ~140-question page) is NOT in any saved
    capture yet — no ids exist for it anywhere in this module.
"""

from src.fill import locators as loc
from src.fill.action_gate import ActionGate
from src.fill.review import cli_review

BASE_URL = "https://sga.anater.org"

_PANEL_HEADING = {
    "ufpa": "headingUnidadeFamiliar",
    "atividade_produtiva": "headingAtividadeProdutiva",
    "diversos": "headingPerfilComunicacao",
    "patrimonio": "headingPatrimonio",
    "plantel": "headingPlantel",
    "tipo_area": "headingTipoArea",
    "acoes_potenciais": "headingAcoesPonteciais",
    "integrantes": "headingIntegrantes",
}

_REPEATABLE_ROW_PANEL = {
    "atividade_produtiva": "idPanelAtividadeProdutiva",
    "patrimonio": "idPanelPatrimonio",
    "plantel": "idPanelPlantel",
    "tipo_area": "idPanelTipoArea",
}


# --------------------------------------------------------------- navigation

def login(page, usuario, senha, gate=None):
    """Grounded in examples/ANATER-login.html. Plain HTML form (no JSF
    viewstate), posts to /sgaLogin. `usuario` is the CPF — the page's own
    JS mask strips dots/dashes from #j_username before submit, so it's
    safest to pass raw digits directly rather than a formatted CPF
    string (the mask plugin only reformats on real keystroke events,
    which Playwright's .fill() doesn't trigger)."""
    def _submit_login():
        page.locator("#loginform button[type=submit]").click()
        page.wait_for_load_state("networkidle")  # this submits a plain form -> full page navigation

    gate = gate or ActionGate.noop()
    gate.confirm("Navigate to login page", lambda: page.goto(f"{BASE_URL}/pages/login.xhtml"))
    gate.confirm("Fill login CPF", lambda: page.fill("#j_username", usuario), label="CPF (login)", value=usuario)
    gate.confirm("Fill login password", lambda: page.fill("#j_password", senha), label="Senha", value=senha)
    gate.confirm("Click ENTRAR (submit login)", _submit_login)


# Fixed, single-option values on the Consultar UFPA filter screen,
# confirmed in examples/ANATER -ufpa-cadastro-filled.html — same
# real-world values as the Cadastrar UFPA page's own fixed fields
# (src/schema/build.py), just a different page/DOM.
_PROJETO_LABEL = "UNIÃO COM MUNICÍPIOS"
_INSTRUMENTO_LABEL = "CTR.GTI.ASS.667.26"
_ESTADO_LABEL = "Mato Grosso"


def open_cadastrar_ufpa(page, *, municipio, gate=None):
    """Sidebar UFPA -> Cadastro -> Consultar UFPA filter screen -> Cadastrar.

    Grounded in examples/ANATER -ufpa-cadastro.html and
    -ufpa-cadastro-filled.html. Confirmed by Khalel: Entidade, Projeto,
    Instrumento and Estado are each a single real option in this account
    (Entidade is already pre-selected on page load; Projeto/Instrumento/
    Estado still need an explicit .select_option() to fire their AJAX
    cascade) — Município is the one real per-family choice, and Tipo de
    Público always stays empty. Then click "Cadastrar", not
    "Pré-Cadastro" — both render inside the same AJAX-updated
    `idPanelCadastroUpf` span, so they're disambiguated by visible text,
    not DOM scope.

    The sidebar's top-level "UFPA" `<a>` has no href/onclick of its own in
    examples/ANATER -home.html — it's a pure client-side toggle (standard
    admin-template pattern) that reveals the "Cadastro"/"Diagnóstico ..."
    submenu underneath. That toggle behavior itself was never directly
    observed in a captured DOM event, so this one step is inferred, not
    confirmed, and is the most likely thing to need correcting on a first
    live run.
    """
    def _click_cadastro():
        ufpa_item.get_by_text("Cadastro", exact=True).click()
        page.wait_for_load_state("networkidle")  # full page: Consultar UFPA filter screen

    def _select(site_id, label_option):
        def _run():
            page.locator(f"#formularioUpf\\:{site_id}").select_option(label=label_option)
            page.wait_for_timeout(300)  # lets the AJAX cascade (Projeto -> Instrumento/Estado/Município) settle
        return _run

    def _click_cadastrar():
        page.locator(r"#formularioUpf\:idPanelCadastroUpf").get_by_text("Cadastrar", exact=True).click()
        page.wait_for_load_state("networkidle")  # full page: Cadastrar UFPA

    gate = gate or ActionGate.noop()
    ufpa_item = page.locator("#sidebar-menu li").filter(has_text="UFPA").first
    gate.confirm("Click sidebar 'UFPA' (expand submenu)", lambda: ufpa_item.locator("> a").first.click())
    gate.confirm("Click sidebar 'Cadastro'", _click_cadastro)

    gate.confirm("Select Projeto", _select("idProjeto", _PROJETO_LABEL), label="Projeto", value=_PROJETO_LABEL)
    gate.confirm("Select Instrumento", _select("idInstrumento", _INSTRUMENTO_LABEL), label="Instrumento", value=_INSTRUMENTO_LABEL)
    gate.confirm("Select Estado", _select("idUf", _ESTADO_LABEL), label="Estado", value=_ESTADO_LABEL)
    gate.confirm("Select Município", _select("idMunicipio", municipio), label="Município", value=municipio)

    gate.confirm("Click 'Cadastrar' (open Cadastrar UFPA page)", _click_cadastrar)


def expand_all_accordions(page, gate=None):
    gate = gate or ActionGate.noop()
    for panel_name, heading_id in _PANEL_HEADING.items():
        collapse_id = heading_id.replace("heading", "collapse")
        panel = page.locator(f"#{collapse_id}")
        if "in" not in (panel.get_attribute("class") or ""):
            def _toggle(h=heading_id):
                loc.accordion_toggle(page, h)
                page.wait_for_timeout(200)
            gate.confirm(f"Expand accordion panel '{panel_name}'", _toggle)


# ------------------------------------------------------------- field filling
# Grounded in examples/anater-signup-page-1.html.

def _resolve_value(field, review_handler):
    """Runs the review handler on a low-confidence field. Returns
    (value, should_fill)."""
    if field.confidence != "low":
        return field.value, True
    from src.fill.review import SKIP

    decision = review_handler(field)
    if decision.value is SKIP:
        return None, False
    return decision.value, True


def fill_field(page, field, review_handler=cli_review, gate=None):
    """Fills one CanonicalField on the currently-open Cadastrar UFPA page."""
    gate = gate or ActionGate.noop()
    value, should_fill = _resolve_value(field, review_handler)
    if not should_fill or value is None or value == "":
        return

    site_id = field.site_field_id
    label_text = site_id[len("label:"):] if site_id.startswith("label:") else None
    where = f"{field.panel}/{field.field}"

    def _settle():
        page.wait_for_timeout(100)  # lets any onchange AJAX (mojarra.ab) settle

    if field.field_type == "text":
        target = loc.form_group_by_label(page, label_text).locator("input, textarea").first if label_text else loc.by_business_id(page, site_id)
        gate.confirm(f"Fill '{where}'", lambda: (target.fill(str(value)), _settle()), label=field.field, value=value)

    elif field.field_type == "select":
        # no schema field currently uses the "label:" scheme for a <select>
        gate.confirm(f"Select '{where}'", lambda: (loc.select_dropdown(page, site_id, str(value)), _settle()), label=field.field, value=value)

    elif field.field_type == "checkbox":
        target = loc.by_business_id(page, site_id)
        action = "Check" if value else "Uncheck"
        gate.confirm(f"{action} '{where}'", lambda: ((target.check() if value else target.uncheck()), _settle()), label=field.field, value=value)

    elif field.field_type == "radio_bool":
        group = loc.radio_group(page, site_id=None if label_text else site_id, label_text=label_text)
        option = "Sim" if value else "Não"
        gate.confirm(f"Click '{option}' for '{where}'", lambda: (loc.click_radio_option(group, option), _settle()), label=field.field, value=value)

    elif field.field_type == "radio_text":
        group = loc.radio_group(page, site_id=None if label_text else site_id, label_text=label_text)
        gate.confirm(f"Click '{value}' for '{where}'", lambda: (loc.click_radio_option(group, str(value)), _settle()), label=field.field, value=value)

    else:
        raise ValueError(f"unknown field_type {field.field_type!r} for {field.panel}/{field.field}")


def fill_simple_panel(page, panel_fields, review_handler=cli_review, gate=None):
    """UFPA, Diversos, Ações Potenciais — no repeatable rows, just fill
    every field."""
    gate = gate or ActionGate.noop()
    for field in panel_fields:
        fill_field(page, field, review_handler, gate)


def fill_repeatable_panel(page, panel_name, rows_by_index, review_handler=cli_review, gate=None):
    """Atividade Produtiva, Patrimônio, Plantel, Tipo Área: fill one row's
    inputs, click Adicionar, repeat for the next row (confirmed pattern —
    see docs/mapeamento.md, each panel's "Structure" note)."""
    gate = gate or ActionGate.noop()
    panel_span_id = _REPEATABLE_ROW_PANEL[panel_name]
    def _add_row():
        loc.add_row_button(page, panel_span_id).click()
        page.wait_for_timeout(300)

    for idx, row_fields in sorted(rows_by_index.items()):
        for field in row_fields:
            fill_field(page, field, review_handler, gate)
        gate.confirm(f"Click 'Adicionar' ({panel_name} row {idx})", _add_row)


def fill_integrantes_panel(page, rows_by_index, review_handler=cli_review, gate=None):
    """One modal submission per person (see docs/mapeamento.md)."""
    def _open_modal():
        loc.inserir_integrante_button(page).click()
        page.wait_for_timeout(300)

    def _save_modal():
        loc.modal_salvar_button(page).click()
        page.wait_for_timeout(300)

    gate = gate or ActionGate.noop()
    for idx, person_fields in sorted(rows_by_index.items()):
        gate.confirm(f"Click 'Inserir Integrante' (person {idx})", _open_modal)
        for field in person_fields:
            fill_field(page, field, review_handler, gate)
        gate.confirm(f"Click modal 'Salvar' (person {idx})", _save_modal)


def group_by_panel_index(fields):
    """{index: [fields...]} for a repeatable panel's CanonicalFields,
    whose `.panel` is like 'atividade_produtiva[0]'."""
    groups = {}
    for f in fields:
        idx = int(f.panel.split("[")[1].rstrip("]"))
        groups.setdefault(idx, []).append(f)
    return groups


def submit(page, gate=None):
    def _submit():
        loc.main_salvar_button(page).click()
        page.wait_for_load_state("networkidle")

    gate = gate or ActionGate.noop()
    gate.confirm("Click page 'Salvar' -- SUBMITS the whole Cadastrar UFPA registration", _submit)


# --------------------------------------------------------------- orchestrator

def fill_cadastro_ufpa(page, schema_panels, review_handler=cli_review, gate=None):
    """Fills every panel of an already-open Cadastrar UFPA page from the
    canonical schema (src.schema.build_schema()["panels"]). Does NOT
    submit — call submit(page) once satisfied."""
    gate = gate or ActionGate.noop()
    expand_all_accordions(page, gate)

    by_panel = {}
    for field in schema_panels:
        base = field.panel.split("[")[0]
        by_panel.setdefault(base, []).append(field)

    fill_simple_panel(page, by_panel.get("ufpa", []), review_handler, gate)
    fill_simple_panel(page, by_panel.get("diversos", []), review_handler, gate)
    fill_simple_panel(page, by_panel.get("acoes_potenciais", []), review_handler, gate)

    for panel_name in ("atividade_produtiva", "patrimonio", "plantel", "tipo_area"):
        fields = [f for f in schema_panels if f.panel.startswith(panel_name)]
        if fields:
            fill_repeatable_panel(page, panel_name, group_by_panel_index(fields), review_handler, gate)

    integrantes_fields = [f for f in schema_panels if f.panel.startswith("integrantes")]
    if integrantes_fields:
        fill_integrantes_panel(page, group_by_panel_index(integrantes_fields), review_handler, gate)
