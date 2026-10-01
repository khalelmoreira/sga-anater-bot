"""
Playwright automation for sga.anater.org.

Grounding, honestly stated:

  - Filling the 8 panels of "Cadastrar UFPA" (locators.py + fill_field()
    below) is grounded directly in the saved HTML captures in examples/
    (real ids, real radio/select structure) — see locators.py's docstring.
  - Login (`login()`), the "Consultar UFPA" filter screen
    (`open_cadastrar_ufpa()`), and the Diagnóstico T0 search/questionnaire
    screens are NOT in any saved capture — docs/mapeamento.md describes
    their flow in prose but no real ids were ever pulled from a live page
    for them. Those three are implemented with best-effort, text-based
    locators and clearly marked below; they need a supervised first run
    against the real site to confirm (or correct) the selectors.
"""

from src.fill import locators as loc
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
# NOT grounded in a saved capture — best-effort text locators, needs a
# supervised live run to confirm.

def login(page, usuario, senha):
    page.goto(f"{BASE_URL}/pages/login.xhtml")
    page.get_by_label("Usuário").fill(usuario)
    page.get_by_label("Senha").fill(senha)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_load_state("networkidle")


def open_cadastrar_ufpa(page, *, entidade, estado, municipio):
    """Sidebar UFPA -> Cadastro -> Consultar UFPA -> select filters ->
    Cadastrar. Per docs/mapeamento.md: Entidade is the user's only real
    option; Projeto/Instrumento auto-populate as the single option once
    Entidade is picked (and are filled as fixed values on the Cadastrar
    UFPA page itself, not here)."""
    page.get_by_role("link", name="UFPA").click()
    page.get_by_role("link", name="Cadastro").click()
    page.get_by_label("Entidade").select_option(label=entidade)
    page.get_by_label("Estado").select_option(label=estado)
    page.get_by_label("Município").select_option(label=municipio)
    page.get_by_role("button", name="Cadastrar").click()
    page.wait_for_load_state("networkidle")


def expand_all_accordions(page):
    for heading_id in _PANEL_HEADING.values():
        collapse_id = heading_id.replace("heading", "collapse")
        panel = page.locator(f"#{collapse_id}")
        if "in" not in (panel.get_attribute("class") or ""):
            loc.accordion_toggle(page, heading_id)
            page.wait_for_timeout(200)


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


def fill_field(page, field, review_handler=cli_review):
    """Fills one CanonicalField on the currently-open Cadastrar UFPA page."""
    value, should_fill = _resolve_value(field, review_handler)
    if not should_fill or value is None or value == "":
        return

    site_id = field.site_field_id
    label_text = site_id[len("label:"):] if site_id.startswith("label:") else None

    if field.field_type == "text":
        target = loc.form_group_by_label(page, label_text).locator("input, textarea").first if label_text else loc.by_business_id(page, site_id)
        target.fill(str(value))

    elif field.field_type == "select":
        # no schema field currently uses the "label:" scheme for a <select>
        loc.select_dropdown(page, site_id, str(value))

    elif field.field_type == "checkbox":
        target = loc.by_business_id(page, site_id)
        if value:
            target.check()
        else:
            target.uncheck()

    elif field.field_type == "radio_bool":
        group = loc.radio_group(page, site_id=None if label_text else site_id, label_text=label_text)
        loc.click_radio_option(group, "Sim" if value else "Não")

    elif field.field_type == "radio_text":
        group = loc.radio_group(page, site_id=None if label_text else site_id, label_text=label_text)
        loc.click_radio_option(group, str(value))

    else:
        raise ValueError(f"unknown field_type {field.field_type!r} for {field.panel}/{field.field}")

    page.wait_for_timeout(100)  # lets any onchange AJAX (mojarra.ab) settle


def fill_simple_panel(page, panel_fields, review_handler=cli_review):
    """UFPA, Diversos, Ações Potenciais — no repeatable rows, just fill
    every field."""
    for field in panel_fields:
        fill_field(page, field, review_handler)


def fill_repeatable_panel(page, panel_name, rows_by_index, review_handler=cli_review):
    """Atividade Produtiva, Patrimônio, Plantel, Tipo Área: fill one row's
    inputs, click Adicionar, repeat for the next row (confirmed pattern —
    see docs/mapeamento.md, each panel's "Structure" note)."""
    panel_span_id = _REPEATABLE_ROW_PANEL[panel_name]
    for _, row_fields in sorted(rows_by_index.items()):
        for field in row_fields:
            fill_field(page, field, review_handler)
        loc.add_row_button(page, panel_span_id).click()
        page.wait_for_timeout(300)


def fill_integrantes_panel(page, rows_by_index, review_handler=cli_review):
    """One modal submission per person (see docs/mapeamento.md)."""
    for _, person_fields in sorted(rows_by_index.items()):
        loc.inserir_integrante_button(page).click()
        page.wait_for_timeout(300)
        for field in person_fields:
            fill_field(page, field, review_handler)
        loc.modal_salvar_button(page).click()
        page.wait_for_timeout(300)


def group_by_panel_index(fields):
    """{index: [fields...]} for a repeatable panel's CanonicalFields,
    whose `.panel` is like 'atividade_produtiva[0]'."""
    groups = {}
    for f in fields:
        idx = int(f.panel.split("[")[1].rstrip("]"))
        groups.setdefault(idx, []).append(f)
    return groups


def submit(page):
    loc.main_salvar_button(page).click()
    page.wait_for_load_state("networkidle")


# --------------------------------------------------------------- orchestrator

def fill_cadastro_ufpa(page, schema_panels, review_handler=cli_review):
    """Fills every panel of an already-open Cadastrar UFPA page from the
    canonical schema (src.schema.build_schema()["panels"]). Does NOT
    submit — call submit(page) once satisfied."""
    expand_all_accordions(page)

    by_panel = {}
    for field in schema_panels:
        base = field.panel.split("[")[0]
        by_panel.setdefault(base, []).append(field)

    fill_simple_panel(page, by_panel.get("ufpa", []), review_handler)
    fill_simple_panel(page, by_panel.get("diversos", []), review_handler)
    fill_simple_panel(page, by_panel.get("acoes_potenciais", []), review_handler)

    for panel_name in ("atividade_produtiva", "patrimonio", "plantel", "tipo_area"):
        fields = [f for f in schema_panels if f.panel.startswith(panel_name)]
        if fields:
            fill_repeatable_panel(page, panel_name, group_by_panel_index(fields), review_handler)

    integrantes_fields = [f for f in schema_panels if f.panel.startswith("integrantes")]
    if integrantes_fields:
        fill_integrantes_panel(page, group_by_panel_index(integrantes_fields), review_handler)
