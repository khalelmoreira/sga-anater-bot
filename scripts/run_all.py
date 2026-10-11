"""
The whole process in one run, one login: registration -> Diagnóstico T0.

    python -m scripts.run_all data/familia-silva.docx --municipio "Bom Jesus Do Araguaia"
    python -m scripts.run_all data/familia-silva.docx --municipio "..." --dry-run

--dry-run fills everything but never clicks either Salvar, and doesn't ask.
Nothing is saved on the site. Caveat: the Diagnóstico step looks the person
up on the site, so for a family that isn't registered yet it is skipped
(reported); use an already-registered family to exercise it.

Same safety rails as the other scripts: per-action prompts (--auto-allow /
--auto-allow-until N), sanitized log in logs/, credentials from .env.
"""

import argparse

from scripts._common import run_cli
from src.pipeline import RunInputs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx_path", nargs="?", help="the registration .docx -- omit if using --schema")
    parser.add_argument("--schema", help="schema JSON saved by `scripts.extract_schema` -- omit if passing docx_path")
    parser.add_argument("--municipio", required=True)
    parser.add_argument("--nome", help="UFPA name to search in Diagnóstico (default: read from the schema)")
    parser.add_argument("--no-whatsapp", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="fill everything, save nothing")
    parser.add_argument("--auto-submit", action="store_true", help="click the registration Salvar without asking")
    parser.add_argument("--auto-save", action="store_true", help="click the Diagnóstico Salvar without asking")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--auto-allow", action="store_true")
    parser.add_argument("--auto-allow-until", type=int, default=0, metavar="N")
    parser.add_argument("--no-screenshots", action="store_true")
    args = parser.parse_args()

    if bool(args.docx_path) == bool(args.schema):
        parser.error("pass exactly one of docx_path or --schema")

    run_cli(RunInputs(
        docx_path=args.docx_path, schema_path=args.schema, municipio=args.municipio, nome=args.nome,
        use_whatsapp=not args.no_whatsapp, dry_run=args.dry_run, auto_submit=args.auto_submit,
        auto_save=args.auto_save, headless=args.headless, auto_allow=args.auto_allow,
        auto_allow_until=args.auto_allow_until, screenshots=not args.no_screenshots,
    ))


if __name__ == "__main__":
    main()
