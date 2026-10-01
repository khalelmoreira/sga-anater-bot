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

def login(page, usuario, senha):
    """Grounded in examples/ANATER-login.html. Plain HTML form (no JSF
    viewstate), posts to /sgaLogin. `usuario` is the CPF — the page's own
    JS mask strips dots/dashes from #j_username before submit, so it's
    safest to pass raw digits directly rather than a formatted CPF
    string (the mask plugin only reformats on real keystroke events,
    which Playwright's .fill() doesn't trigger)."""
    page.goto(f"{BASE_URL}/pages/login.xhtml")
    page.fill("#j_username", usuario)
    page.fill("#j_password", senha)
    page.locator("#loginform button[type=submit]").click()
    page.wait_for_load_state("networkidle")


# Fixed, single-option values on the Consultar UFPA filter screen,
# confirmed in examples/ANATER -ufpa-cadastro-filled.html — same
# real-world values as the Cadastrar UFPA page's own fixed fields
# (src/schema/build.py), just a different page/DOM.
_PROJETO_LABEL = "UNIÃO COM MUNICÍPIOS"
_INSTRUMENTO_LABEL = "CTR.GTI.ASS.667.26"
_ESTADO_LABEL = "Mato Grosso"


def open_cadastrar_ufpa(page, *, municipio):
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
    ufpa_item = page.locator("#sidebar-menu li").filter(has_text="UFPA").first
    ufpa_item.locator("> a").first.click()
    ufpa_item.get_by_text("Cadastro", exact=True).click()
    page.wait_for_load_state("networkidle")

    page.locator(r"#formularioUpf\:idProjeto").select_option(label=_PROJETO_LABEL)
    page.wait_for_timeout(300)
    page.locator(r"#formularioUpf\:idInstrumento").select_option(label=_INSTRUMENTO_LABEL)
    page.wait_for_timeout(300)
    page.locator(r"#formularioUpf\:idUf").select_option(label=_ESTADO_LABEL)
    page.wait_for_timeout(300)
    page.locator(r"#formularioUpf\:idMunicipio").select_option(label=municipio)
    page.wait_for_timeout(300)

    page.locator(r"#formularioUpf\:idPanelCadastroUpf").get_by_text("Cadastrar", exact=True).click()
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
