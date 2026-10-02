"""
Standalone extraction + schema step: runs extract_docx() + build_schema()
(+ the matching WhatsApp "Ações Potenciais" template, auto-looked-up the
same way scripts/run_registration.py does it) + the pre-flight gate, then
resolves every low-confidence field with cli_review() -- all before any
browser opens -- and saves the fully-resolved schema to a JSON file.

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

from src.extract import extract_docx, extract_whatsapp_text, find_pa_municipio, load_whatsapp_text
from src.fill.review import cli_review, resolve
from src.schema import build_schema
from src.schema.gate import check_blocking
from src.schema.persist import save_panels


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx_path", help="path to the real registration .docx (e.g. data/familia-silva.docx)")
    parser.add_argument("--out", required=True, help="where to save the resolved schema JSON (e.g. logs/schema-familia-silva.json)")
    parser.add_argument("--no-whatsapp", action="store_true", help="skip the Ações Potenciais WhatsApp template lookup")
    args = parser.parse_args()

    whatsapp_text = None
    if not args.no_whatsapp:
        pa_nome, municipio = find_pa_municipio(args.docx_path)
        if pa_nome and municipio:
            whatsapp_text = load_whatsapp_text(pa_nome, municipio)
            if whatsapp_text is None:
                print(f"No WhatsApp template found for '{pa_nome} - {municipio}' in data/acoes_potenciais/ "
                      "-- Ações Potenciais will be left for a low-confidence pause.", file=sys.stderr)

    records = extract_docx(args.docx_path)
    whatsapp_data = extract_whatsapp_text(whatsapp_text) if whatsapp_text else None
    schema = build_schema(records, whatsapp_data=whatsapp_data)

    blocking = check_blocking(schema["panels"])
    if blocking:
        print(f"Pre-flight gate failed -- fix the .docx before trying again:\n{blocking}", file=sys.stderr)
        sys.exit(1)

    print(f"{len(schema['panels'])} fields built. Resolving low-confidence fields (if any)...")
    resolved = resolve(schema["panels"], cli_review)

    path = save_panels(resolved, args.out)
    print(f"\nSaved resolved schema: {path}")
    print(f"Run it with: python -m scripts.run_registration --schema {path} --municipio \"<município>\"")


if __name__ == "__main__":
    main()
