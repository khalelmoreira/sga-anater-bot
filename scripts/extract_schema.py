"""
Standalone extraction + schema step: runs extract_docx() + build_schema()
(+ the matching WhatsApp "Ações Potenciais" template, auto-looked-up the
same way scripts/run_registration.py does it) + the pre-flight gate, then
resolves every low-confidence field with cli_review() -- all before any
browser opens -- and saves the fully-resolved schema to a JSON file.

It also builds and resolves the Diagnóstico T0 answers and saves them next
to it (<out stem>.diagnostico.json) for scripts/run_diagnostico.py --schema.

This is entirely optional. scripts/run_registration.py works fine
without ever running this: by default it extracts, builds, and reviews
in memory, exactly as before. Use this script when you'd rather do that
work once and reuse it (debugging a parse, or retrying a fill run that
crashed) via `run_registration.py --schema <path>` instead of redoing
extraction and re-answering every low-confidence prompt from scratch.

Usage:
    python -m scripts.extract_schema data/familia-silva.docx --out logs/schema-familia-silva.json

The saved file is NOT sanitized -- it holds this family's real, resolved
field values. It naturally lands under logs/ (gitignored); don't hand it
to Claude.
"""

import argparse
import sys

from src.pipeline import RunInputs, prepare
from src.schema.gate import MissingKeyDataError
from src.schema.persist import indicadores_path
from src.ui import CliUI


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx_path", help="path to the real registration .docx (e.g. data/familia-silva.docx)")
    parser.add_argument("--out", required=True, help="where to save the resolved schema JSON (e.g. logs/schema-familia-silva.json)")
    parser.add_argument("--no-whatsapp", action="store_true", help="skip the Ações Potenciais WhatsApp template lookup")
    args = parser.parse_args()

    try:
        prepare(RunInputs(docx_path=args.docx_path, use_whatsapp=not args.no_whatsapp,
                          do_registration=False, save_schema_to=args.out), CliUI())
    except MissingKeyDataError as e:
        print(f"Pre-flight gate failed -- fix the .docx before trying again:\n{e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nSaved Diagnóstico T0 answers: {indicadores_path(args.out)}")
    print(f"Register with:   python -m scripts.run_registration --schema {args.out} --municipio \"<município>\"")
    print(f"Then diagnostic: python -m scripts.run_diagnostico --schema {args.out}")


if __name__ == "__main__":
    main()
