"""
Offline checks for src/fill/diagnostico.py against the saved captures in
examples/ (file:// pages, no network, no login). Run with:

    python -m tests.test_diagnostico
"""

import os

from playwright.sync_api import sync_playwright

from src.extract.docx_source import extract_docx
from src.fill.diagnostico import (
    fill_questions, match_answers, parse_choice, scrape_questions, ufpa_name_on_page,
)
from src.schema.build import _align_indicador, build_indicadores
from src.schema.persist import load_indicadores, save_indicadores

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


def _page_url(name):
    return "file://" + os.path.abspath(os.path.join(EX, name))


def _docx_answers():
    """What the schema layer hands to the fill layer for example.docx."""
    return build_indicadores(extract_docx(os.path.join(EX, "example.docx")))


def test_parse_choice():
    assert parse_choice("( x ) Sim      (   ) Não") == "Sim"
    assert parse_choice("(   ) Sim      ( x  ) Não") == "Não"
    assert parse_choice("(   ) Sim (   ) Não ( X ) Não se aplica") == "Não se Aplica"
    assert parse_choice("(   ) Sim      (   ) Não") is None          # nothing marked
    assert parse_choice("( x ) Sim      ( x ) Não") is None          # two marked
    assert parse_choice("Não se Aplica") == "Não se Aplica"
    assert parse_choice(None) is None


def test_alignment():
    answers = _docx_answers()
    assert not [a for a in answers if a.confidence == "low"], "no block should need a human just to align"
    prop = {a.question: a.value for a in answers if a.indicator.startswith("Propriedade")}
    # the .docx drifts after "7.Se sim, quantas mulheres..." (header with no answer line): labels must anchor it
    assert "7.Se sim, quantas mulheres na UFPA diretamente beneficiadas pelo projeto de recuperação ?" not in prop
    assert prop["a) 1 (uma) mulher"].startswith("a)")
    assert prop["8. Área beneficiada com projeto de recuperação com SAF de até 1 h ?"].startswith("8")
    assert prop["9. Área beneficiada com projeto de recuperação com SAF maior que 1 há ?"].startswith("9")
    # a header with a placeholder answer ("Qual") is dropped too, and its options keep their own answers
    assert "Se sim, qual?" not in prop and "Descarte correto de embalagens" in prop
    # labels that can't be reconciled -> no alignment instead of a guess
    assert _align_indicador(["1. a?", "2. b?"], ["2 .( x ) Sim ( ) Não", "1 .( ) Sim ( x ) Não"]) is None


def test_rules():
    answers = _docx_answers()
    by = {(a.indicator, a.question): a for a in answers}
    # 1. nothing marked -> Não se Aplica
    assert by[("Regularização Fundiária", "Contrato de Compra e Venda")].value == "Não se Aplica"
    assert all(parse_choice(a.value) for a in answers if a.confidence == "high")
    # 2. Propriedade, question 7: first row and option d are dropped, a/b/c stay
    prop = [q for (i, q) in by if i.startswith("Propriedade")]
    assert not any(q.startswith("7. Mulheres na UFPA") for q in prop)
    assert not any(q.startswith("d) mais do que 3") for q in prop)
    assert {"a) 1 (uma) mulher", "b) 2 (duas) mulheres", "c) 3 (três) mulheres"} <= set(prop)
    # 3. Políticas Públicas, questions 2 and 6: only their options a/b/c... remain
    pol = [q for (i, q) in by if i == "Políticas Públicas"]
    assert "2. Se não, qual o motivo?" not in pol and "6. Se sim, qual?" not in pol
    assert "a) Falta de informação" in pol and "a) Pronaf Custeio" in pol


def test_persist_roundtrip(tmp_path="logs/_test_diag.json"):
    answers = _docx_answers()
    path = save_indicadores(answers, tmp_path)
    assert load_indicadores(path) == answers
    os.remove(path)


def test_match_answers(page):
    page.goto(_page_url("ANATER-diagnostico-T0-fill-page.html"), wait_until="domcontentloaded")
    questions = scrape_questions(page)
    assert len(questions) == 129
    assert ufpa_name_on_page(page) == "Itajara Aparecida Lopes De Oliveira"
    answers = _docx_answers()
    m = match_answers(questions, answers)
    assert len(m.assigned) >= 128, len(m.assigned)
    pair = {questions[i]["label"]: a.question for i, a in m.assigned.items()}
    # sub-options: site label is "<parent> <letter>. <option>"
    assert pair["5. Se sim na questão 5, qual? g. CRO"] == "CRO"
    # identical option text under two different parents is handed out in order
    nec = [(l, q) for l, q in pair.items() if l.endswith("a. Não há necessidade de acordo com o CAR")]
    assert len(nec) == 2
    # a site label that glues two questions together must not steal the next question's answer
    assert pair["6. No mês passado, algum morador de 18 anos ou mais sentiu fome, mas não comeu porque não havia comida ou recursos?"].startswith("No mês passado, algum morador")
    # group headers never take an answer
    assert not any(a.question.strip().lower().startswith(("se sim na questão 5", "se sim, qual")) for a in m.assigned.values())


def _checked(page):
    return {q["label"]: q["checked"] for q in scrape_questions(page)}


def test_fill_blank(page):
    page.goto(_page_url("ANATER-diagnostico-T0-fill-page.html"), wait_until="domcontentloaded")
    s = fill_questions(page, _docx_answers(), review_handler=lambda f: (_ for _ in ()).throw(AssertionError(f"unexpected pause: {f.field}")))
    after = _checked(page)
    assert s["filled"] == sum(v is not None for v in after.values()) >= 40, s["filled"]
    assert not s["left_blank"], "unmarked answers are filled as Não se Aplica, never left blank"
    assert after["1. Possui georreferenciamento aprovado pelo INCRA?"] in ("true", "false", "N-A")


def test_fill_half_keeps_existing(page):
    page.goto(_page_url("ANATER-diagnostico-T0-fill-page-half.html"), wait_until="domcontentloaded")
    before = _checked(page)
    answered_before = {k: v for k, v in before.items() if v is not None}
    s = fill_questions(page, _docx_answers(), review_handler=lambda f: None)
    after = _checked(page)
    assert all(after[k] == v for k, v in answered_before.items()), "an existing answer was overwritten"
    assert s["already_answered"] > 0 and s["filled"] > 0
    assert len(answered_before) + s["filled"] == sum(v is not None for v in after.values())


if __name__ == "__main__":
    test_parse_choice()
    test_alignment()
    test_rules()
    test_persist_roundtrip()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for test in (test_match_answers, test_fill_blank, test_fill_half_keeps_existing):
            test(browser.new_page())
        browser.close()
    print("ok")
