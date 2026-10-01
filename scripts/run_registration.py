"""
End-to-end entrypoint: launches Playwright and runs one family's
registration via src.fill.register_ufpa().

Usage:
    python -m scripts.run_registration data/familia-silva.docx --municipio "Bom Jesus Do Araguaia"

Credentials (SGA_USUARIO / SGA_SENHA) are read from the environment,
loaded from a local .env via python-dotenv — see src/fill/credentials.py.
.env itself is gitignored and Claude Code is configured to never read it
(.claude/settings.json) — it's your responsibility to create it:

    SGA_USUARIO=12345678900
    SGA_SENHA=...

The matching WhatsApp "Ações Potenciais" template (see
data/acoes_potenciais/README.md) is looked up automatically from the
family's own PA/município, found by re-reading the .docx once up front
-- no need to pass it in by hand. Pass --no-whatsapp to skip this (the
Ações Potenciais panel is then left for a low-confidence pause instead).

Doesn't submit by default -- review the filled page, then confirm with
Enter, or pass --auto-submit to skip the prompt.
"""

import argparse
import sys

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from src.extract import extract_docx, load_whatsapp_text
from src.fill import register_ufpa
from src.fill.site import submit
from src.schema.gate import MissingKeyDataError


def _find_pa_municipio(docx_path):
    """Pulls Nome do PA / Município straight from the .docx, the same way
    src/schema/build.py does, so the WhatsApp lookup can happen before the
    full schema (and browser) are built."""
    records = extract_docx(docx_path)
    idx = {}
    for r in records:
        idx.setdefault(r["section"], {})[r["field"]] = r["value"]
    pa_nome = idx.get("ufpa", {}).get("Nome do PA")
    municipio = idx.get("entidade.local", {}).get("Município")
    return pa_nome, municipio


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx_path", help="path to the real registration .docx (e.g. data/familia-silva.docx)")
    parser.add_argument("--municipio", required=True, help="Município to select on the Consultar UFPA filter screen")
    parser.add_argument("--no-whatsapp", action="store_true", help="skip the Ações Potenciais WhatsApp template lookup")
    parser.add_argument("--auto-submit", action="store_true", help="click Salvar automatically instead of pausing for review")
    parser.add_argument("--headless", action="store_true", help="run the browser headless (default: visible, recommended for the first real runs)")
    args = parser.parse_args()

    load_dotenv()

    whatsapp_text = None
    if not args.no_whatsapp:
        pa_nome, municipio = _find_pa_municipio(args.docx_path)
        if pa_nome and municipio:
            whatsapp_text = load_whatsapp_text(pa_nome, municipio)
            if whatsapp_text is None:
                print(f"No WhatsApp template found for '{pa_nome} - {municipio}' in data/acoes_potenciais/ "
                      "-- Ações Potenciais will be left for a low-confidence pause.", file=sys.stderr)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()
        try:
            register_ufpa(
                page,
                args.docx_path,
                municipio=args.municipio,
                whatsapp_text=whatsapp_text,
                auto_submit=args.auto_submit,
            )
        except MissingKeyDataError as e:
            print(f"Pre-flight gate failed -- fix the .docx before trying again:\n{e}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        if not args.auto_submit:
            input("\nReview the filled page in the browser, then press Enter to Salvar (Ctrl+C to abort without submitting): ")
            submit(page)

        browser.close()


if __name__ == "__main__":
    main()
