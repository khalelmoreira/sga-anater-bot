"""
Diagnóstico T0 fill-in: the "Consultar Diagnóstico T0" search screen and
the question page it opens.

Grounded in the saved captures in examples/ (see docs/mapeamento.md,
"Consultar Diagnóstico T0" and "Diagnóstico T0 question page"):

  - ANATER-diagnostico-T0-consulta-page*.html  (form `formularioDiagnostico`)
  - ANATER-diagnostico-T0-fill-page.html / -half.html  (form `formDiagnostico`)

Confirmed by Khalel:
  - only Estado is filled on the search screen; Município and Status stay
    empty, the person is found by name in the DataTables search box;
  - homonyms: >1 matching row -> use the one with an Iniciar/Continuar
    button if exactly one has it, otherwise pause for a human;
  - the bot ends with Salvar only. Finalizar is always a human click;
  - on a Continuar page, only unanswered questions are filled, existing
    answers are never overwritten (differences are reported instead).

Still inferred (not directly captured): the sidebar's "UFPA" expand step,
same as open_cadastrar_ufpa() in site.py.
"""

import difflib
import re
from dataclasses import dataclass, field

from src.fill.action_gate import ActionGate
from src.fill.review import SKIP, cli_review, pick_option
from src.schema.rules import normalize, parse_choice, read_choice  # noqa: F401  (re-exported)

SEARCH_FORM = "formularioDiagnostico"
FILL_FORM = "formDiagnostico"
_ESTADO_LABEL = "Mato Grosso"
_ACTION_TITLE = "Iniciar/Continuar Diagnóstico"  # same title for both buttons
_FINALIZADO_TITLE = "Diagnóstico Finalizado"

# radio value attribute -> what the answer is called
_RADIO_VALUE = {"Sim": "true", "Não": "false", "Não se Aplica": "N-A"}


class UfpaNotFound(Exception):
    """The name typed in the search box matched no row."""


class UfpaAlreadyFinalized(Exception):
    """The only matching row is Finalizado — nothing left to do."""


class WrongUfpa(Exception):
    """The question page opened for a different UFPA than expected."""


# ------------------------------------------------------------ pure helpers

def _indicator_key(text):
    """'Indicador: UCM - Situação do CAR' / 'Situação do CAR' -> same key."""
    t = re.sub(r"^\s*indicador\s*:\s*", "", str(text), flags=re.IGNORECASE)
    t = re.sub(r"^\s*ucm\s*-\s*", "", t, flags=re.IGNORECASE)
    return normalize(t)


def _match_indicator(key, keys):
    if key in keys:
        return key
    close = difflib.get_close_matches(key, list(keys), 1, 0.85)  # e.g. the .docx typo "Capaciatção"
    return close[0] if close else None


def _variants(nq):
    """The .docx question text with and without its leading list marker
    ('1', 'a', 'b'...) — the site prefixes sub-options with their parent
    question and letter, the .docx often doesn't."""
    out = [nq]
    stripped = re.sub(r"^(?:\d+|[a-z])\s+", "", nq)
    if stripped and stripped != nq:
        out.append(stripped)
    return out


@dataclass
class MatchResult:
    # site question index -> answer (IndicadorAnswer-like) that goes in it
    assigned: dict = field(default_factory=dict)
    # site question index -> why it has no answer (shown in the summary)
    unmatched: dict = field(default_factory=dict)
    # answers that no site question took (header rows, options that don't exist on the site...)
    unused: list = field(default_factory=list)


def _level(v, nl):
    """How strongly the .docx text `v` points at the site label `nl`
    (both normalized). 0 = not at all."""
    if not v:
        return 0
    if v == nl:
        return 4
    if nl.endswith(" " + v):
        return 3  # sub-option: the site label is "<parent> <letter> <option>"
    # the site label's last words are the start of a longer .docx text
    # (e.g. site "... h. Linhas Sucessivas" vs docx "Linhas Sucessivas (contra ...)")
    words = nl.split()
    for k in range(len(words) - 1):
        tail = " ".join(words[k:])
        if len(tail) >= 10 and v.startswith(tail + " ") and k > 0:
            return 2
    if len(v) >= 8 and difflib.SequenceMatcher(None, v, nl[-(len(v) + 2):]).ratio() >= 0.9:
        return 2
    if len(v) >= 8 and v in nl:
        return 1
    return 0


def match_answers(site_questions, answers):
    """Pairs each site question with a .docx answer.

    `site_questions`: list of {"indicador": str, "label": str} in page order.
    `answers`: IndicadorAnswer-like objects (.indicator, .question, ...).

    Matching is by Indicador name + normalized question text, never by
    position or by Eixo (the .docx files several Indicadores under the
    wrong Eixo, and its multi-part items carry an extra header row that
    has no radio on the site). Per site question the strongest evidence
    wins (see _level). A .docx text that is merely contained in 2+ site
    labels of the same Indicador and is the end of none of them is a group
    header and is ignored. Identical .docx texts (the same option under
    two different parents) are given out in .docx order. Anything else
    that ties, or a loose containment that fits more than one answer, is
    reported as ambiguous instead of guessed.
    """
    res = MatchResult()
    by_ind = {}
    for a in answers:
        by_ind.setdefault(_indicator_key(a.indicator), []).append(a)
    site_by_ind = {}
    for i, q in enumerate(site_questions):
        site_by_ind.setdefault(_indicator_key(q["indicador"]), []).append(i)

    used = set()
    for sk, idxs in site_by_ind.items():
        ak = _match_indicator(sk, by_ind)
        cands = by_ind.get(ak, []) if ak else []
        norm_labels = {i: normalize(site_questions[i]["label"]) for i in idxs}

        headers = set()
        for a in cands:
            nq = normalize(a.question)
            if nq and sum(nq in nl for nl in norm_labels.values()) >= 2 \
                    and not any(nl.endswith(" " + nq) for nl in norm_labels.values()):
                headers.add(id(a))

        # every plausible (site question, .docx answer) pair, strongest first,
        # then handed out greedily: a strong match elsewhere must win over a
        # weak one here (e.g. a site label that glues two questions together)
        pairs = []
        for i in idxs:
            for order, a in enumerate(cands):
                if id(a) in headers:
                    continue
                best = None
                for v in _variants(normalize(a.question)):
                    lvl = _level(v, norm_labels[i])
                    if lvl and (best is None or (lvl, len(v)) > best):
                        best = (lvl, len(v))
                if best:
                    pairs.append((-best[0], -best[1], i, order, a))
        pairs.sort(key=lambda p: p[:4])

        for lvl, ln, i, order, a in pairs:
            if i in res.assigned or i in res.unmatched or id(a) in used:
                continue
            rivals = [q for q in pairs if q[2] == i and q[:2] == (lvl, ln) and id(q[4]) not in used
                      and normalize(q[4].question) != normalize(a.question)]
            loose = lvl == -1 and len([q for q in pairs if q[2] == i and q[0] == -1 and id(q[4]) not in used]) > 1
            if rivals or loose:
                res.unmatched[i] = "ambiguous: more than one .docx answer fits this question"
                continue
            used.add(id(a))
            res.assigned[i] = a
        for i in idxs:
            if i not in res.assigned and i not in res.unmatched:
                res.unmatched[i] = "no (unused) .docx answer matches this question"

    res.unused = [a for a in answers if id(a) not in used]
    return res


# -------------------------------------------------- search screen (browser)

def _open_diagnostico_page(page, gate):
    """Sidebar UFPA -> Diagnóstico T0. The UFPA submenu may already be
    expanded (e.g. right after Cadastro); clicking the toggle again would
    collapse it, so only expand when the link isn't visible."""
    ufpa_item = page.locator("#sidebar-menu li").filter(has_text="UFPA").first
    link = ufpa_item.get_by_text("Diagnóstico T0", exact=True)
    if not link.is_visible():
        gate.confirm("Click sidebar 'UFPA' (expand submenu)", lambda: ufpa_item.locator("> a").first.click())

    def _click():
        link.click()
        page.wait_for_load_state("networkidle")  # full page: Consultar Diagnóstico T0

    gate.confirm("Click sidebar 'Diagnóstico T0'", _click)


def _search_rows(page):
    """[(row_locator, {cod, nome, municipio, evolucao, action})] for the
    rows currently shown, skipping DataTables' 'no results' placeholder."""
    rows = page.locator("#DataTables_Table_0 tbody tr")
    out = []
    for i in range(rows.count()):
        row = rows.nth(i)
        if row.locator("td.dataTables_empty").count():
            continue
        tds = row.locator("td")
        text = lambda n: re.sub(r"\s+", " ", tds.nth(n).inner_text()).strip()
        if row.locator(f'a[title="{_ACTION_TITLE}"]').count():
            action = row.locator(f'a[title="{_ACTION_TITLE}"]').inner_text().strip()
        elif row.locator(f'a[title="{_FINALIZADO_TITLE}"]').count():
            action = "Finalizado"
        else:
            action = None
        out.append((row, {"cod": text(0), "nome": text(1), "municipio": text(4), "evolucao": text(5), "action": action}))
    return out


def find_and_open_diagnostico(page, nome, *, gate=None):
    """Search screen: Estado -> Pesquisar -> search box by name -> click
    Iniciar/Continuar on the person's row. Returns the button's label
    ('Iniciar' | 'Continuar'). Raises UfpaNotFound / UfpaAlreadyFinalized.

    Município and Status are intentionally left empty (confirmed by
    Khalel): the name alone identifies the person across the whole Estado.
    """
    gate = gate or ActionGate.noop()
    _open_diagnostico_page(page, gate)

    estado = page.locator(f"#{SEARCH_FORM}\\:idEstado")

    def _select_estado():
        estado.select_option(label=_ESTADO_LABEL)
        # AJAX cascade: Município is re-rendered and enabled once it's done
        page.locator(f"select#{SEARCH_FORM}\\:idMunicipio:not([disabled])").wait_for(state="attached", timeout=15000)

    def _pesquisar():
        page.locator(f'#{SEARCH_FORM} a[title="Pesquisar"]').click()
        page.wait_for_load_state("networkidle")  # full submit, not AJAX
        page.locator("#DataTables_Table_0").wait_for(state="visible", timeout=15000)

    def _search(text):
        box = page.locator("#DataTables_Table_0_filter input[type=search]")
        box.fill(text)
        page.wait_for_timeout(300)  # client-side filter redraw, no request is sent

    gate.confirm("Select Estado (search screen)", _select_estado, label="Estado", value=_ESTADO_LABEL)
    gate.confirm("Click 'Pesquisar'", _pesquisar)
    gate.confirm("Type the name in the results search box", lambda: _search(nome), label="Nome da UFPA", value=nome)

    # the search is a substring filter over every column; keep exact-name rows
    target = normalize(nome)
    matches = [(r, d) for r, d in _search_rows(page) if normalize(d["nome"]) == target]
    if not matches:
        raise UfpaNotFound(f"no row named {nome!r} in the Diagnóstico T0 results")

    actionable = [(r, d) for r, d in matches if d["action"] in ("Iniciar", "Continuar")]
    if not actionable:
        raise UfpaAlreadyFinalized(f"{nome!r} is already Finalizado")
    if len(actionable) == 1:
        row, data = actionable[0]
    else:
        options = [f'{d["cod"]} | {d["nome"]} | {d["municipio"]} | {d["evolucao"]} | {d["action"]}' for _, d in actionable]
        choice = pick_option("Diagnóstico T0 row (homonyms)", nome, options)
        if choice is SKIP:
            raise UfpaNotFound(f"{nome!r}: several rows matched and none was picked")
        row, data = actionable[options.index(choice)]

    def _open():
        row.locator(f'a[title="{_ACTION_TITLE}"]').click()
        page.wait_for_load_state("networkidle")
        page.locator(f"#{FILL_FORM}").wait_for(state="visible", timeout=15000)

    gate.confirm(f"Click '{data['action']}' on the person's row", _open)
    return data["action"]


# -------------------------------------------------- question page (browser)

_SCRAPE_JS = """
() => {
  const form = document.getElementById('formDiagnostico');
  let indicador = null, out = [];
  for (const el of form.querySelectorAll('label.fundoIndicadorSanfona, label:has(> i.fa-hand-o-right)')) {
    if (el.classList.contains('fundoIndicadorSanfona')) { indicador = el.textContent.trim(); continue; }
    const radios = [...el.parentElement.querySelectorAll('input[type=radio]')];
    const checked = radios.find(r => r.checked);
    out.push({
      indicador,
      label: el.textContent.replace(/\\s+/g, ' ').trim(),
      radios: Object.fromEntries(radios.map(r => [r.value, r.id])),
      checked: checked ? checked.value : null,
    });
  }
  return out;
}
"""


def scrape_questions(page):
    """Every question on the page, in order:
    [{indicador, label, radios: {value: input id}, checked: value | None}]"""
    return page.evaluate(_SCRAPE_JS)


def ufpa_name_on_page(page):
    """The UFPA name shown in the page header (read-only text)."""
    group = page.locator(f"#{FILL_FORM} div.form-group").filter(
        has=page.locator("label.control-label", has_text=re.compile(r"^\s*UFPA\s*$"))
    ).first
    return re.sub(r"\s+", " ", group.locator("> div").first.inner_text()).strip()


def ensure_instrumento_meta(page, gate):
    """Instrumento Meta has a single real option and must be selected. On a
    Continuar page it's already set (and Qtd. Prevista/Disponível already
    filled), so leave it alone."""
    sel = page.locator(f"select#{FILL_FORM}\\:idInstrumentoMeta")
    if sel.evaluate("el => el.value"):
        return

    def _select():
        value = sel.locator('option:not([value=""])').first.get_attribute("value")
        sel.select_option(value=value)
        page.wait_for_load_state("networkidle")  # onchange re-renders idPanelQuantidade

    gate.confirm("Select Instrumento Meta", _select, label="Instrumento Meta", value="single option")


@dataclass
class _ReviewItem:
    """Adapter so the CLI review handler (written for CanonicalField) can
    show an IndicadorAnswer."""
    panel: str
    field: str
    value: object
    review_reason: str
    confidence: str = "low"


def _resolve_choice(answer, review_handler):
    """-> (choice or None, why). Pauses for a human only when the answer is
    low confidence or has more than one option marked. A blank answer (no
    option marked — common for sub-options the family didn't answer) is
    left unanswered and reported, not paused on."""
    choice, state = read_choice(answer.value)
    if state == "blank" and answer.confidence != "low":
        return None, "blank in the .docx"
    if state == "ok" and answer.confidence != "low":
        return choice, None
    item = _ReviewItem(
        panel=f"diagnostico_t0 / {answer.indicator}",
        field=answer.question,
        value=answer.value,
        review_reason=answer.review_reason
        or ("more than one option marked" if state == "ambiguous" else "low confidence in the source answer"),
    )
    decision = review_handler(item)
    if decision.value is SKIP:
        return None, "skipped at review"
    choice = parse_choice(decision.value)
    return choice, (None if choice else "review answer not understood")


def fill_questions(page, answers, review_handler=cli_review, gate=None):
    """Fills the unanswered questions of the open question page and returns
    a summary dict (nothing is saved here — see salvar()).

    Existing answers (Continuar pages) are never overwritten; if one
    differs from the .docx it is listed under `discrepancies`.
    """
    gate = gate or ActionGate.noop()
    questions = scrape_questions(page)
    match = match_answers(questions, answers)
    summary = {"filled": 0, "already_answered": 0, "discrepancies": [], "left_blank": [],
               "unmatched_site": [], "unused_answers": [a.question for a in match.unused]}

    for i, q in enumerate(questions):
        answer = match.assigned.get(i)
        label = q["label"]
        if answer is None:
            reason = match.unmatched.get(i, "no .docx answer")
            if q["checked"] is None:
                summary["unmatched_site"].append((label, reason))
            continue

        if q["checked"] is not None:  # Continuar page: keep what's there
            summary["already_answered"] += 1
            wanted = parse_choice(answer.value)
            have = next((k for k, v in _RADIO_VALUE.items() if v == q["checked"]), q["checked"])
            if wanted and wanted != have:
                summary["discrepancies"].append((label, have, wanted))
            continue

        choice, why = _resolve_choice(answer, review_handler)
        if choice is None:
            summary["left_blank"].append((label, why))
            continue

        radio_id = q["radios"][_RADIO_VALUE[choice]]

        def _click(rid=radio_id):
            page.locator(f'label[for="{rid}"]').click()

        gate.confirm(f"Answer '{choice}' ({q['indicador']})", _click, label="Resposta", value=choice)
        summary["filled"] += 1

    return summary


def salvar(page, gate=None):
    """Salvar only — Finalizar is always a human click (confirmed by
    Khalel). Full-page submit; the person shows up as Continuar afterward
    until a human finalizes."""
    def _salvar():
        page.locator(f'#{FILL_FORM} a[title="Salvar"]').click()
        page.wait_for_load_state("networkidle")

    gate = gate or ActionGate.noop()
    gate.confirm("Click page 'Salvar' -- saves the Diagnóstico T0 answers (does NOT finalize)", _salvar)


def run_diagnostico_t0(page, nome, answers, *, review_handler=cli_review, gate=None, auto_save=False):
    """Search screen -> question page -> answer -> (optionally) Salvar.
    Expects an already logged-in `page`. Returns the fill_questions()
    summary plus 'opened_as' ('Iniciar' | 'Continuar').

    Safety check: the UFPA name in the question page's header must match
    `nome`, otherwise nothing is answered (WrongUfpa).
    """
    gate = gate or ActionGate.noop()
    opened_as = find_and_open_diagnostico(page, nome, gate=gate)
    shown = ufpa_name_on_page(page)
    if normalize(shown) != normalize(nome):
        raise WrongUfpa(f"opened the diagnostic for {shown!r}, expected {nome!r}")
    ensure_instrumento_meta(page, gate)
    summary = fill_questions(page, answers, review_handler, gate)
    summary["opened_as"] = opened_as
    if auto_save:
        salvar(page, gate)
    return summary
