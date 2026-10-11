"""
Fills the Diagnóstico T0 questionnaire for one already-registered family.

    python -m scripts.run_diagnostico data/familia-silva.docx
    python -m scripts.run_diagnostico --schema logs/schema-familia-silva.json

The second form reuses what `scripts.extract_schema` already built and
reviewed (it reads logs/schema-familia-silva.json for the person's name and
logs/schema-familia-silva.diagnostico.json for the answers), so nothing is
re-extracted or re-reviewed -- handy for retrying a crashed run.

Logs in, opens UFPA -> Diagnóstico T0, finds the person by the "Nome da
UFPA" read from the same .docx (Estado only; Município/Status stay empty),
opens Iniciar/Continuar, answers the questions that are still blank and
stops at Salvar. It never clicks Finalizar -- that stays a human decision.

Same safety rails as scripts.run_registration: every state-changing action
pauses for allow/deny/quit and is logged (sanitized) to logs/, credentials
come from .env, and Salvar waits for an Enter unless --auto-save is given.
"""

import argparse
import sys

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from src.extract import extract_docx
from src.fill.action_gate import AbortRun, ActionGate
from src.fill.credentials import load_credentials
from src.fill.diagnostico import (
    UfpaAlreadyFinalized, UfpaNotFound, WrongUfpa, run_diagnostico_t0, salvar,
)
from src.fill.site import login
from src.schema import build_schema
from src.schema.persist import indicadores_path, load_indicadores, load_panels


def _print_summary(s):
    print(f"\nOpened as: {s['opened_as']}  |  answered now: {s['filled']}  |  already answered: {s['already_answered']}")
    for title, items in (
        ("Left blank (blank in the .docx / skipped)", s["left_blank"]),
        ("Site questions with no .docx answer", s["unmatched_site"]),
    ):
        if items:
            print(f"\n{title}: {len(items)}")
            for label, why in items:
                print(f"  - {label[:110]}  [{why}]")
    if s["discrepancies"]:
        print(f"\nExisting answers that differ from the .docx (NOT changed): {len(s['discrepancies'])}")
        for label, have, wanted in s["discrepancies"]:
            print(f"  - {label[:90]}: site={have}, docx={wanted}")
    if s["unused_answers"]:
        print(f"\n.docx rows that matched no site question (headers/extra options): {len(s['unused_answers'])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx_path", nargs="?", help="the registration .docx of the family -- omit if using --schema")
    parser.add_argument("--schema", help="schema JSON saved by `scripts.extract_schema` (its .diagnostico.json sibling must exist) -- omit if passing docx_path")
    parser.add_argument("--nome", help="UFPA name to search for (default: 'Nome da UFPA' read from the .docx)")
    parser.add_argument("--auto-save", action="store_true", help="click Salvar without waiting for Enter")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--auto-allow", action="store_true", help="don't prompt before each action (still logged)")
    parser.add_argument("--auto-allow-until", type=int, default=0, metavar="N")
    parser.add_argument("--no-screenshots", action="store_true")
    args = parser.parse_args()

    if bool(args.docx_path) == bool(args.schema):
        parser.error("pass exactly one of docx_path or --schema")
    if args.schema:
        panels = load_panels(args.schema)
        answers = load_indicadores(indicadores_path(args.schema))
        print(f"Loaded {len(answers)} answers from {indicadores_path(args.schema)} -- skipping extraction/review.")
    else:
        schema = build_schema(extract_docx(args.docx_path))
        panels, answers = schema["panels"], schema["indicadores"]
    nome = args.nome or next((f.value for f in panels if f.panel == "ufpa" and f.field == "Nome da UFPA"), None)
    if not nome:
        parser.error("couldn't read 'Nome da UFPA' -- pass --nome")

    load_dotenv()
    gate = ActionGate(auto_allow=args.auto_allow, screenshot=not args.no_screenshots, auto_allow_until=args.auto_allow_until)
    print(f"Action log: {gate.path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()
        gate.attach_page(page)
        try:
            login(page, *load_credentials(), gate)
            summary = run_diagnostico_t0(page, nome, answers, gate=gate)
            _print_summary(summary)
            if not args.auto_save:
                input("\nReview the page, then press Enter to Salvar (Ctrl+C to leave without saving): ")
                salvar(page, gate)
            print("\nSaved. Finalizar is yours to click.")
        except (UfpaNotFound, UfpaAlreadyFinalized, WrongUfpa) as e:
            print(f"\nStopped: {e}", file=sys.stderr)
            browser.close()
            sys.exit(1)
        except AbortRun as e:
            print(f"\nRun aborted by user at: {e}\nSee {gate.path}", file=sys.stderr)
            browser.close()
            sys.exit(1)
        browser.close()


if __name__ == "__main__":
    main()
