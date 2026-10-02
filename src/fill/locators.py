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


def select_dropdown(page, site_id, option_text):
    """Selects a <select> option by its visible label text."""
    page.locator(f'#{FORM}\\:{site_id}').select_option(label=option_text)


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
