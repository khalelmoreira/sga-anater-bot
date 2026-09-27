# sga-anater-bot

## What this project does

Automates the recurring registration of UFPAs (Unidades Familiares de
Produção Agrária — Family Agrarian Production Units) in ANATER's SGA web
system (`sga.anater.org`). Today, a person reads a hand-filled `.docx`
file (`( x ) Sim / ( ) Não` checkboxes) and re-types field by field into
the site. The goal is a bot that runs this registration from start to
finish on its own, pausing **only** on fields with inconsistent,
ambiguous, or low-confidence data — never asking for field-by-field
approval.

**Read `docs/mapeamento.md` before touching any part of this project.**
That file is the source of truth for what has already been mapped and
decided: data sources, source file structure, the site's complete screen
flow, scope decisions (what's left out), and the 3-layer architecture
used here. It was exported from an earlier planning session and may go
stale if the mapping continues elsewhere — in that case, ask Khalel
before assuming something is still true.

**Important:** real registration files come in `.docx` (not `.odt` — that
only happened during an earlier analysis step because of a LibreOffice
conversion on Fedora). The extractor in `src/extract/` works with
`.docx` via `python-docx`.

## Layout

```
sga-anater-bot/
├── docs/
│   └── mapeamento.md   # source of truth for what's already mapped/decided
├── examples/            # sample .docx (fake data) + saved site page
├── src/
│   ├── extract/         # layer 1: source -> raw data
│   ├── schema/          # layer 2: canonical schema + confidence rules
│   └── fill/            # layer 3: data -> site fill-in (Playwright)
└── requirements.txt
```

## Architecture (summary — details in `docs/mapeamento.md`)

1. **Extraction** (`src/extract/`) — one extractor per source type. Today:
   the registration `.docx` (main source) and loose WhatsApp text
   (exclusive to the "Ações Potenciais" panel).
2. **Canonical schema + validation** (`src/schema/`) — each answer becomes
   a record with `confidence: high | low`. Only low-confidence ones pause
   the bot.
3. **Fill-in** (`src/fill/`) — browser automation with Playwright, since
   the site is JSF/`.xhtml` with viewstate and a ~20-minute session.

## Current state

This is a scaffold. The modules in `src/` are only stubs
(`NotImplementedError`) — the real logic hasn't been written yet. The
field-by-field mapping of the site's panels (UFPA, Atividade Produtiva,
Diversos, Patrimônio, Plantel, Tipo Área, Ações Potenciais, Integrantes)
is in progress; what's already closed is in `docs/mapeamento.md`.
