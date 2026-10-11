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

from scripts._common import run_cli
from src.pipeline import RunInputs


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

    run_cli(RunInputs(
        docx_path=args.docx_path, schema_path=args.schema, nome=args.nome,
        do_registration=False, auto_save=args.auto_save, headless=args.headless,
        auto_allow=args.auto_allow, auto_allow_until=args.auto_allow_until,
        screenshots=not args.no_screenshots,
    ))


if __name__ == "__main__":
    main()
