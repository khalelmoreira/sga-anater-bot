"""
End-to-end entrypoint: launches Playwright and runs one family's
registration via src.fill.register_ufpa().

Two ways to run it:
    python -m scripts.run_registration data/familia-silva.docx --municipio "Bom Jesus Do Araguaia"
    python -m scripts.run_registration --schema logs/schema-familia-silva.json --municipio "Bom Jesus Do Araguaia"

The first extracts the .docx and builds the schema right here, in
memory, exactly as before -- low-confidence fields get reviewed inline
as each panel is filled. The second skips extraction/schema-build
entirely and loads an already-resolved schema produced separately by
`python -m scripts.extract_schema` -- useful for retrying a run that
crashed mid-fill without re-answering every low-confidence prompt, or
just for keeping extraction and filling as separate steps. Exactly one
of docx_path / --schema must be given.

Credentials (SGA_USUARIO / SGA_SENHA) are read from the environment,
loaded from a local .env via python-dotenv — see src/fill/credentials.py.
.env itself is gitignored and Claude Code is configured to never read it
(.claude/settings.json) — it's your responsibility to create it:

    SGA_USUARIO=12345678900
    SGA_SENHA=...

The matching WhatsApp "Ações Potenciais" template (see
data/acoes_potenciais/README.md) is looked up automatically from the
family's own PA/município, found by re-reading the .docx once up front
-- no need to pass it in by hand. Only applies to the docx_path form
above (--schema already has it baked in, or doesn't, from whenever it
was built). Pass --no-whatsapp to skip this (the Ações Potenciais panel
is then left for a low-confidence pause instead).

Doesn't submit by default -- review the filled page, then confirm with
Enter, or pass --auto-submit to skip the prompt.

Every state-changing action on the real site (click/fill/select) pauses
for an explicit allow/deny/quit and is logged -- sanitized, personal data
redacted -- to logs/run-<timestamp>.jsonl, so a live run can be reviewed
afterward. Pass --auto-allow to skip the per-action prompts (still
logged); there is no way to skip the logging itself.

Screenshots are taken after every action (logs/screenshots/<timestamp>/)
by default -- useful with --headless, or in an environment where a
headed browser window doesn't actually render (e.g. broken X11
forwarding in a devcontainer). Unlike the log, screenshots are NOT
sanitized -- they're pictures of the real, filled form. Review them
yourself; don't hand them to Claude. Pass --no-screenshots to skip.
"""

import argparse

from scripts._common import run_cli
from src.pipeline import RunInputs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx_path", nargs="?", help="path to the real registration .docx (e.g. data/familia-silva.docx) -- omit if using --schema")
    parser.add_argument("--schema", help="path to an already-resolved schema JSON from `scripts.extract_schema` -- omit if passing docx_path")
    parser.add_argument("--municipio", required=True, help="Município to select on the Consultar UFPA filter screen")
    parser.add_argument("--no-whatsapp", action="store_true", help="skip the Ações Potenciais WhatsApp template lookup")
    parser.add_argument("--auto-submit", action="store_true", help="click Salvar automatically instead of pausing for review")
    parser.add_argument("--headless", action="store_true", help="run the browser headless (default: visible, recommended for the first real runs)")
    parser.add_argument("--auto-allow", action="store_true", help="don't prompt before each action (still logged) -- NOT recommended for a first live run")
    parser.add_argument("--auto-allow-until", type=int, default=0, metavar="N", help="don't prompt for the first N actions (still logged) -- use the number shown in the last [ACTION n] prompt you verified, e.g. when retrying after a crash; prompts resume at N+1")
    parser.add_argument("--no-screenshots", action="store_true", help="skip the after-action screenshots")
    args = parser.parse_args()

    if bool(args.docx_path) == bool(args.schema):
        parser.error("pass exactly one of docx_path or --schema")

    run_cli(RunInputs(
        docx_path=args.docx_path, schema_path=args.schema, municipio=args.municipio,
        use_whatsapp=not args.no_whatsapp, do_diagnostico=False, auto_submit=args.auto_submit,
        headless=args.headless, auto_allow=args.auto_allow, auto_allow_until=args.auto_allow_until,
        screenshots=not args.no_screenshots,
    ))


if __name__ == "__main__":
    main()
