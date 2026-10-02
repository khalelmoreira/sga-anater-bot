"""
Low-level element lookup for the Cadastrar UFPA page (`formularioUpf`).

Grounded directly in the saved HTML captures (examples/anater-signup-
page-1.html), not guessed:

  - Stable, business-meaningful ids (idNome, idPossuiCar, idSexo, ...)
    render as `formularioUpf:<id>` — looked up by exact id.
  - Every Sim/Não (and other) radio group renders as
        <table id="formularioUpf:<id>"> OR an unlabeled <table class="radio-sim-nao">
            <input type="radio" name="formularioUpf:<id>" id="...:0" value="true"><label for="...:0"> Sim</label>
            <input type="radio" name="formularioUpf:<id>" id="...:1" value="false"><label for="...:1"> Não</label>
        </table>
    Where the id is auto-generated (j_idtNNN, unstable across page loads
    per docs/mapeamento.md), the group has no stable id — it's located
    instead via the <label class="control-label"> that precedes it in the
    same .form-group, exactly as docs/mapeamento.md prescribes ("match by
    label text, not id").
  - "Adicionar" buttons (repeatable-row panels) are also auto-generated
    ids, but their onclick always references the panel's stable
    `idPanelXxx` span — located by that, not by id.
"""

from src.schema.rules import normalize

FORM = "formularioUpf"


def by_business_id(page, site_id):
    """Exact, stable id — formularioUpf:<site_id>."""
    return page.locator(f'#{FORM}\\:{site_id}')


def form_group_by_label(page, label_text):
    """The .form-group containing a <label class="control-label"> with
    this exact text — the scope used to find an auto-generated-id field
    next to its (stable) question label."""
    return page.locator(
        "div.form-group",
        has=page.locator("label.control-label", has_text=label_text),
    )


def radio_group(page, *, site_id=None, label_text=None):
    """A Sim/Não (or other) radio group, located either by stable id or
    by the label text of the question it answers. Exactly one of
    site_id/label_text must be given."""
    if site_id:
        return by_business_id(page, site_id)
    if label_text:
        return form_group_by_label(page, label_text)
    raise ValueError("radio_group needs either site_id or label_text")


def click_radio_option(group_locator, option_text):
    """Clicks the radio whose <label> text matches `option_text`
    (case/whitespace-insensitive substring match, e.g. "Sim", "Não",
    "Masculino", "E-mail")."""
    group_locator.locator("label", has_text=option_text).first.click()


def _select_locator(page, site_id):
    """The <select> for a business id. Some ids (e.g. Estado's `idUf`)
    sit on a wrapper <span> around an auto-id'd <select>, so match either."""
    return page.locator(f'select#{FORM}\\:{site_id}, #{FORM}\\:{site_id} select')


def select_dropdown(page, site_id, option_text):
    """Selects a <select> option by its visible label text."""
    _select_locator(page, site_id).select_option(label=option_text)


def select_is_already_set(page, site_id, wanted):
    """True if the <select> already shows `wanted` — the site pre-selects
    the standard Projeto/Instrumento/Meta/Classificação. Matches the
    selected option's value or visible text; `wanted` may also be a longer
    description that contains the selected value (e.g. Meta: "Cod.: 21100
    - ..." vs option value "21100")."""
    sel = _select_locator(page, site_id)
    cur_value = sel.evaluate("el => el.value")
    if not cur_value:
        return False
    cur_label = sel.evaluate("el => el.options[el.selectedIndex].text").strip()
    wanted = str(wanted).strip()
    return (
        wanted in (cur_value, cur_label)
        or cur_value in wanted
        or normalize(wanted) == normalize(cur_label)
    )


def select_dropdown_if_needed(page, site_id, wanted):
    """Leaves a pre-selected <select> alone. Otherwise selects `wanted`
    (by value, then by visible text); failing that, if the site offers
    exactly one non-blank option, selects that one. Returns True if it
    changed anything.

    Cascading selects (Município after Estado) are filled by AJAX, so
    first wait for real options to show up."""
    sel = _select_locator(page, site_id)
    try:
        sel.locator('option:not([value=""])').first.wait_for(state="attached", timeout=10000)
    except Exception:
        pass  # fall through to the error below with the real option count
    if select_is_already_set(page, site_id, wanted):
        return False
    for kwargs in ({"value": str(wanted)}, {"label": str(wanted)}):
        try:
            sel.select_option(timeout=2000, **kwargs)
            return True
        except Exception:
            pass
    # punctuation/case/accent-insensitive match against the live options
    # (docx "PA.MACIFE" vs site "PA MACIFE")
    live = [o for o in sel.locator("option").evaluate_all(
        "els => els.map(e => ({value: e.value, text: e.text}))") if o["value"]]
    target = normalize(wanted)
    matches = [o for o in live if normalize(o["text"]) == target or normalize(o["value"]) == target]
    if len(matches) == 1:
        sel.select_option(value=matches[0]["value"])
        return True
    options = [o["value"] for o in live]
    if len(options) == 1:
        sel.select_option(value=options[0])
        return True
    raise ValueError(f"<select {site_id}> isn't set to {wanted!r} and has {len(options)} non-blank options")


def add_row_button(page, panel_span_id):
    """The 'Adicionar' button for a repeatable-row panel (Atividade
    Produtiva, Patrimônio, Plantel, Tipo Área), located by the stable
    `idPanelXxx` span its onclick AJAX call targets — not by its own
    (unstable) id."""
    return page.locator(f'a:has-text("Adicionar")[onclick*="{panel_span_id}"]')


def accordion_toggle(page, heading_id):
    """Expands an accordion panel by its heading id, if it's collapsed.

    The heading *is* the clickable <a> itself (id="headingXxx" sits on
    the <a class="panel-heading" ...> tag — see examples/anater-signup-
    page-1.html), not a wrapper containing a separate <a> child. An
    earlier version of this function searched for a descendant <a>
    inside it, which never matches (Playwright's .locator() only finds
    descendants, never the element itself) and hangs until Playwright's
    default click timeout."""
    page.locator(f"#{heading_id}").click()


def inserir_integrante_button(page):
    """'Inserir Integrante' icon button — located relative to its label,
    same pattern as the radio groups above (see examples/anater-signup-
    page-1.html around 'headingIntegrantes')."""
    return page.locator('label', has_text="Inserir Integrante").locator(
        "xpath=following-sibling::a[1]"
    )


def modal_salvar_button(page):
    """The 'Salvar' button inside the 'Cadastrar Pessoa' modal — distinct
    from the page's main Salvar and from the modal's photo-upload Salvar,
    both of which also live under formularioUpf (see src/fill/site.py
    docstring for how these were disambiguated)."""
    return page.locator(
        'a[title="Salvar"][onclick*="idPanelIntegrantes formularioUpf:formularioBeneficiarioPf"]'
    )


def dropdown_options(page, site_id):
    """Scrapes a <select>'s real, live option labels — the 'live catalog'
    src.schema.rules.dropdown_match() can use to upgrade a field from low
    to high confidence just-in-time (see src/schema/rules.py docstring)."""
    return by_business_id(page, site_id).locator("option").all_text_contents()


def main_salvar_button(page):
    """The page-level Salvar button that submits the whole Cadastrar UFPA
    form — distinguished from the modal Salvar buttons by its onclick
    using `mojarra.jsfcljs` (plain form submit) instead of `mojarra.ab`
    (AJAX, used by every other Salvar/Adicionar on this page)."""
    return page.locator('a[title="Salvar"][onclick*="jsfcljs"]')
