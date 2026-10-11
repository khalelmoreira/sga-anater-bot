# Product plan — making the bot usable by ANATER agents

Oct 11, 2026 · @Khalel

Companion to `docs/mapeamento.md`. That file records **what the bot does on
the site** (mapping, rules, scope). This one records **how it becomes a
product** other people can run: one pipeline, a UI, Windows packaging, and a
payment hook. Read `mapeamento.md` first; nothing here changes its rules.

## Goal and users

- **Users:** other ANATER agents (not Khalel), on **Windows**, with **no
  terminal knowledge**. Multiple customers, each with their own SGA login.
- **Today:** registration and Diagnóstico T0 both work against the live site,
  but only as three separate terminal scripts run by hand.
- **Needed to be functional:** (1) a UI, (2) one wired-up pipeline,
  (3) a payment hook for the future. Billing model is **undecided**.

## Current state (grounded in the code)

### Entrypoints are separate and not importable

| Script | Does | Hands off via |
| --- | --- | --- |
| `scripts/extract_schema.py` | extract `.docx` → schema → `check_blocking` → terminal review → save | `<out>.json` + `<out>.diagnostico.json` (path from `src/schema/persist.py: indicadores_path()`) |
| `scripts/run_registration.py` | login → Cadastrar UFPA → fill 8 panels → optional submit | reads `--schema` or the `.docx` |
| `scripts/run_diagnostico.py` | login → find UFPA in Diagnóstico T0 → answer → Salvar | reads `--schema` (+ `.diagnostico.json`) or the `.docx` |

Each `main()` is argparse + `sys.exit`, so nothing can call them as
functions. The only link between them is the JSON files and a shared
`--schema` path. Running from a `.docx` directly skips the up-front review in
`run_diagnostico` (low-confidence answers get reviewed later, inside
`fill_questions`) and loads no WhatsApp text.

### Human pauses: three mechanisms, only one injectable

| Mechanism | Where | Injectable? |
| --- | --- | --- |
| `review_handler(field) -> ReviewDecision` (low-confidence value; `SKIP` sentinel) | `src/fill/review.py` (`cli_review`, `resolve`, `resolve_indicadores`); threaded through `register_ufpa`, `fill_*`, `run_diagnostico_t0` | **Yes** |
| `pick_option(field_label, wanted, options)` (dropdown with no match; homonym rows) | `src/fill/review.py:79`, `input()` at `:89`; called from `site.py` (`_select`) and `diagnostico.py` | **No**, hard-wired |
| `ActionGate.confirm(description, action_fn, ...)` (numbered `[ACTION n]` prompt, `--auto-allow-until N`) | `src/fill/action_gate.py:148`, `input()` at `:171` | **No**, hard-wired |
| End-of-run "press Enter to Salvar" | `run_registration.py:128`, `run_diagnostico.py:95` | **No**, lives in the scripts |

### Other facts that shape the design

- Credentials come from env `SGA_USUARIO` / `SGA_SENHA`
  (`src/fill/credentials.py`); the scripts call `load_dotenv()` themselves.
- Browser: `p.chromium.launch(headless=...)`, headed by default, no
  persistent context.
- `check_blocking` runs in `extract_schema.py:56` and `register_ufpa`
  (`src/fill/__init__.py:74`), **not** in `run_diagnostico`.
- Run reports: Diagnóstico returns a summary dict (`filled`,
  `already_answered`, `discrepancies`, `left_blank`, `unmatched_site`,
  `unused_answers`, `opened_as`). **Registration returns only
  `{"panels": panels}`** — no structured summary.
- The action log (`logs/run-<stamp>.jsonl`) and screenshots already exist and
  are PII-sanitised; they are the real record of a registration run today.
- Only `tests/test_diagnostico.py` exists (no pytest in `requirements.txt`).

## Target architecture

### One pipeline function

`src/pipeline.py`: `run_ufpa(inputs, ui)` =
extract → schema → pre-flight gate → review → registration →
Diagnóstico T0 → summary. Replaces running three scripts by hand. The scripts
become thin CLI wrappers around it, so Khalel's current workflow keeps working.

- `inputs`: `.docx` path (or saved schema), WhatsApp text or PA template,
  município, credentials, options (`auto_submit`, `auto_save`, headless).
- Carry the person's name from registration into Diagnóstico in memory instead
  of through `--schema` / `--nome`.
- Call `check_blocking` **once, at the start**, so a bad `.docx` never reaches
  login (today `run_diagnostico` skips it).

### A `UI` interface

One Protocol the pipeline talks to; the pipeline never touches the terminal.

| Method | Replaces |
| --- | --- |
| `progress(step, detail)` | scattered `print()` calls |
| `review(field) -> ReviewDecision` | `review_handler` / `cli_review` |
| `pick_option(label, wanted, options) -> str \| SKIP` | `review.pick_option` |
| `confirm_action(n, description) -> allow/deny/abort/allow_rest` | `ActionGate.confirm` prompt |
| `confirm_save(kind)` | the two end-of-run `input()` calls |
| `report(summary)` | `_print_summary` and the "Done." print |

Two implementations: **`CliUI`** (today's behaviour, keeps `--auto-allow*`)
and **`WebUI`** (below).

### Refactors this requires

- [x] `pick_option` takes its prompter from the injected `UI` (thread through
      `fill_field`, `_select`, `find_and_open_diagnostico`).
- [x] `ActionGate` takes a `ui` instead of calling `input()`; keep the
      log/screenshot/`auto_allow_until` logic as is.
- [x] `register_ufpa` returns a structured summary (`summarize_panels`: fields and rows per panel, reviewed at fill time, dropdown picks, skipped) (fields filled
      automatically vs reviewed vs skipped, rows added per panel, whether
      Salvar happened).
- [x] Lift the end-of-run Salvar prompts out of the scripts into the pipeline.
- [x] Make `login` / browser launch a pipeline step shared by both phases
      (one login, one browser, one session — also helps the ~20 min session
      question).

### Pauses in a GUI

A pause is a blocking call inside the pipeline that waits for the person's
answer. Run the pipeline in a worker thread; `WebUI.review(...)` posts the
question to the page and waits on a future that the HTTP endpoint resolves.
Same shape for `pick_option` and `confirm_action`.

## UI sketch

Screens a non-technical user needs (text wireframes, to refine):

1. **Setup (first run):** SGA CPF + password, stored in **Windows Credential
   Manager** (`keyring`), not a `.env` file. "Test login" button.
2. **New registration:** pick the `.docx`; WhatsApp text (paste, or choose a
   saved PA template from `data/acoes_potenciais/`); Município.
3. **Pre-flight result:** the `MissingKeyDataError` list in plain language,
   e.g. "Integrante 2 has no CPF. Fix the file and try again." Nothing opens
   in the browser.
4. **Running:** step list (Reading file → Registering → Diagnóstico T0) with
   a progress indicator; a "watch the browser" note when headed.
5. **Review card:** field name, value from the file, why it needs review,
   option dropdown or text box, **Confirm / Skip**. Replaces `cli_review`
   and `pick_option`.
6. **Summary:** automatic vs reviewed, discrepancies on a Continuar page,
   unanswered questions, link to the log/screenshots, and a clear
   reminder that **Finalizar is theirs to click** (the bot never does).

**Recommended tech:** a local FastAPI app serving a simple HTML page, opened
in the default browser. Reasons: fastest to iterate; Playwright already needs
a browser; easy to run the review card as normal web forms. Rejected for now:
Tkinter/Qt (more UI code for the same screens, poorer dropdown/search UX).

### M3 as built

- `python -m scripts.run_web` starts FastAPI on `127.0.0.1:8765` and opens the
  browser (`src/web/app.py`, page in `src/web/static/index.html`, UI strings in pt-BR).
- `src/web/ui.py` `WebUI`: pipeline runs in a worker thread and blocks in
  `review` / `pick_option` / `confirm_save` until `POST /api/answer`; the page polls `/api/state`.
- **Web runs don't ask per click** (`auto_allow=True`; every action is still
  logged and screenshotted). Cancel works through `ActionGate(cancel_check=...)`.
- Credentials: `src/web/creds.py` (`keyring`, env fallback); the password is never sent to the page.
- Every `/api` call needs a per-process token embedded in the served page.
- Not done: the "Test login" button, an update channel, and a Windows-tested build.

## Windows packaging

- Double-click `.exe` via **PyInstaller**; the app starts the local server and
  opens the browser page.
- **Riskiest part:** bundling Playwright's Chromium (large, path-sensitive).
  Test on a **clean Windows machine early**, before building more UI.
- Logs and screenshots under `%APPDATA%`, not the install folder.
- Unpinned `requirements.txt` needs pinning before building releases.

## Payment and licensing — decision pending

The billing unit decides whether a server is needed at all:

| Model | Needs a server? | Notes |
| --- | --- | --- |
| Per-UFPA credits | Yes (credit balance) | Fits the work unit; consume only after a successful save |
| Subscription / licence key | Yes (key validation, renewals) | Predictable revenue; needs online check or signed offline tokens |
| One-time purchase | No (offline signature check) | Simplest; no recurring revenue, harder to revoke |

**Decided now:** a single seam, `entitlement.check_and_consume()`, called
before the browser opens, next to `check_blocking`. Stubbed to always allow.
Consume the credit **only after the UFPA saves successfully**, so a failed run
never costs the user. Nothing else in the pipeline knows about payment.

## Cross-cutting concerns

- **LGPD:** personal data of rural families (CPF, names, birth dates) flows
  through the app. Logs are already sanitised and stay local. Under a credits
  model the server should see only a counter/licence id, never family data.
- **Multi-customer SGA accounts:** `mapeamento.md` assumes one
  Entidade/Projeto/Instrumento/Estado and fixed values (e.g. Classificação
  da UFPA = `Assentados`, Programa de Fomento = `NENHUM`). Other agents may
  have different ones, so these must become configuration, not constants.
- **WhatsApp templates** (`data/acoes_potenciais/`): need a UI to add and
  edit per PA + município, not hand-placed text files.
- **Site changes:** SGA is JSF with unstable ids; plan for an update channel
  and a clear "the site changed, update the app" failure message.
- **Support:** run logs + screenshots are what a user sends when something
  breaks; make them easy to export.

## Milestones (in order)

- [x] **M1** — `src/pipeline.py` + `UI` Protocol + `CliUI`; scripts become thin
      wrappers; no behaviour change. Refactors listed above.
- [x] **M2** — structured registration summary; registration + Diagnóstico in
      one run, one login.
- [x] **M3** — `WebUI` and the six screens.
- [ ] **M4** — `entitlement` stub, settings and credentials storage
      (`keyring`), per-account config for the fixed values.
- [ ] **M5** — Windows packaging, tested on a clean machine.
- [ ] **M6** — real billing, once the model is chosen.

## Open points

- [ ] Billing model and unit (per UFPA / subscription / one-time), price,
      payment provider, free trial.
- [ ] Is a server needed at all (depends on the billing model)?
- [ ] Which of the "fixed" values in `mapeamento.md` differ per agent/entity?
- [ ] Headed vs headless default for non-technical users (headed lets them
      watch and trust it).
- [ ] How updates are delivered, and how support receives logs.
- [ ] Pin dependency versions and add pytest before packaging.
