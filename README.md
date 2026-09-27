# sga-anater-bot

Automation for registering UFPAs (Unidades Familiares de Produção Agrária —
Family Agrarian Production Units) in ANATER's SGA system
(`sga.anater.org`), from a hand-filled `.docx` file and/or loose text
received via WhatsApp.

See [`docs/mapeamento.md`](docs/mapeamento.md) for the full mapping of
data sources, the site's screen flow, and the scope decisions already
closed — and [`CLAUDE.md`](CLAUDE.md) for the architecture and project
layout summary.

## Development environment

This project uses a Dev Container (Python 3.12 + Node.js + Playwright +
Claude Code + `gh` CLI already configured). Open the folder in VS Code (or
equivalent) with the Dev Containers extension and choose "Reopen in
Container".

## Before running

1. Place a sample `.docx` (fake data) and the saved registration page in
   `examples/` — see `examples/README.md`.
2. Install dependencies (already done automatically in the devcontainer's
   `postCreateCommand`): `pip install -r requirements.txt`.

## Status

Initial scaffold — extraction, validation, and fill-in logic have not been
implemented yet (stubs in `src/`).
