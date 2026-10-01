# ANATER Registration Automation — Mapping and Plan

Sep 25, 2026 · @Khalel

## Context and goal

Today, a person manually registers UFPAs (Unidades Familiares de Produção
Agrária — Family Agrarian Production Units): they read a hand-filled
`.docx` file (`( x ) Sim / ( ) Não` checkboxes) and re-type field by field
into ANATER's SGA web system (sga.anater.org). The goal is a bot that runs
this registration from start to finish on its own, stopping **only** on
fields with inconsistent, ambiguous, or low-confidence data — never asking
for field-by-field approval.

This document consolidates what has already been mapped (sources, file
structure, site flow, scope decisions) before we move into the field-by-
field mapping of each panel — work too large for a single session, to be
done in separate stages using this document as a reference.

## Data sources

| Source | Format | What it feeds |
| --- | --- | --- |
| Registration `.docx` file | Word document (.docx) with tables, hand-marked checkboxes | Practically every panel of the registration — it's the main source |
| Loose text via WhatsApp | Free-flowing text, written by another person, in 4 fixed paragraphs (Eixo Produtivo / Social / Ambiental / Fundiário) | Exclusively the **Ações Potenciais** panel — this section comes empty in the `.docx` |

The user flagged that **there may be other sources not yet mapped** (still
to be investigated). That's why the proposed architecture (further below)
separates the extraction layer from the rules/validation layer: a new
source gets its own extractor, without touching the rest of the pipeline.

## Mapping the `.docx` file to the site's panels

The full file (anonymized sample analyzed) has **10 tables**. Mapping to
the registration/site panels:

| # | Table in the `.docx` | Content | Destination on the site | Status |
| --- | --- | --- | --- | --- |
| 0 | Entidade executora | Entidade, CNPJ, Núcleo Operacional, N° instrumento, Agente de Ater, UF/Município/Data | Entidade/Projeto/Instrumento selection screen (dropdowns, usually a single default option) | Mapped |
| 1 | Dados da UFPA | Nome, terra pública, PA, documentos da terra, CAR, ocupação, endereço, área | **UFPA** panel | Mapped, still needs field-by-field detail |
| 2 (part 1) | Coordinates + individual questions | Public office, PRNA, business partner, non-farm income | — | **Out of scope** (user decision) |
| 2 (part 2) | Productive activities | Activity, annual production, unit, main activity | **Atividade Produtiva** panel | Mapped, still needs detail |
| 2 (part 3) | Diversos | Means of communication, rural sanitation | **Diversos** panel | Mapped, still needs detail |
| 3 | Patrimônio (single, large block: machinery/vehicles, herd headcount, area allocated to, available resources, participation in collective activities) | Description/Quantity/Unit | **Patrimônio**, **Plantel**, **Tipo Área** panels | Partially mapped — **pending confirmation** on whether "available resources" and "collective activities" have their own panel on the site |
| 4 | Ações Potenciais | Eixo Produtivo/Social/Ambiental/Fundiário (comes empty in the `.docx`) | **Ações Potenciais** panel | Real source is the WhatsApp text, not this table |
| 5 and 6 | Integrantes (one block per person) | CPF, name, nickname, sex, marital status, birth date, education, classification, contact, UFPA responsible party | **Integrantes** panel | Mapped, still needs detail |
| 7 | Políticas Públicas (per member) | Federal public policy, year joined | — | **Out of scope** (user decision — the site's equivalent panel is also left unfilled) |
| 8 | Proteção de Dados Pessoais (LGPD) | Consent text + signature | — | **Out of scope** (documentation, doesn't go to the site) |
| 9 | Indicadores | ~140 Sim/Não/Não se aplica questions, organized by Eixo (SOCIAL, AMBIENTAL, ECONÔMICO) and Indicador | **Diagnóstico T0** | Mapped — answer format matches the site's, match considered reliable |

### Inconsistencies already observed during extraction

In the first sample file (partial, only the Indicadores table), some
sections had a **question count that didn't match the marked-answer
count** (misalignment between the question column and the answer column
in the original document). These rows need human review case by case —
this is exactly the kind of case that should pause the bot, not fields
that match 1:1.

## SGA/ANATER site screen flow

Site: `sga.anater.org` (login at `/pages/login.xhtml`). **Session expires
after ~20 min, no captcha.**

1. **Login** → Home (shows overall totals: UFPAs, men, women, diagnostics, etc.)
2. Sidebar menu **UFPA → Cadastro** → "Consultar UFPA" screen with filters: Entidade, Projeto, Instrumento, Estado, Município, Tipo de Público.
   - Entidade is already fixed (the user's only option).
   - Once Entidade is selected, Projeto and Instrumento show up already filled in/as the single option — just confirm.
3. **Cadastrar** button → opens "Cadastrar UFPA": a single page with **9 accordion panels** (expand/collapse):
   1. Unidade Familiar de Produção Agrária (UFPA) — general data, address, land documents
   2. Atividade Produtiva (agricultural, non-agricultural, and services production)
   3. Diversos (means of communication, rural sanitation)
   4. Patrimônio
   5. Plantel
   6. Tipo Área
   7. Ações Potenciais (4 textareas: Eixo Produtivo/Social/Ambiental/Fundiário)
   8. Integrantes (buttons to add a member and check fomento)
   9. Políticas Públicas — **not filled in**
   - A single **Salvar** button at the bottom submits the whole page.
4. **UFPA → Diagnóstico T0** menu → "Consultar Diagnóstico T0" screen with filters Instrumento (fixed), Estado (fixed), Município, Status do Diagnóstico → search and find the just-registered person in the results list (columns: Cód. UFPA, Nome, Validade DAP, Estado, Município, Evolução %, Ações: Iniciar/Progresso/Finalizado).
5. **Iniciar** button on the person's row → opens the Diagnóstico T0 page: the ~140 Sim/Não/Não se aplica questions, organized by Eixo → Indicador → Questão, in the same structure as Table 9 of the `.docx`. Here the match is direct and reliable.
6. End of process — there are no steps after Diagnóstico T0.

## Decisions and scope already closed

- The bot runs the process from start to finish **on its own**; it only pauses on fields with inconsistent/ambiguous/low-confidence data — it never asks for field-by-field approval.
- **Políticas Públicas** panel on the site: not filled in.
- **Políticas Públicas** table from the source file: left out, doesn't feed anything on the site.
- Questions about **public office, PRNA, business partner, and non-farm income** (part of Table 2 of the `.docx`): out of scope, must be ignored entirely.
- **Ações Potenciais** panel: fed by the WhatsApp text, not the `.docx`.
- The registration is done **recurrently** (multiple families/UFPAs), not a one-off event.
- The site has no captcha; the session expires after ~20 minutes.
- At this mapping stage, the user navigates the site manually and describes/shows the screens (no direct access via Claude in Chrome in this session).

## Proposed architecture

Three layers, so that a new data source (the user still has to investigate others) doesn't require redoing the site automation:

1. **Extraction** (source → raw data) One extractor per source type (the `.docx` one already exists as a proof of concept). Each extractor returns the same output format, regardless of origin.
2. **Canonical schema + validation** (the process's "brain") Each answer becomes a record `{axis, indicator, question, value, confidence, review_reason}`.
   - `confidence: high` → goes straight to automatic fill-in.
   - `confidence: low` (misaligned question/answer count, empty field, ambiguous answer, text that didn't match the site's expected format 1:1) → flagged for pause and human approval **only at that point**.
3. **Site fill-in** (data → form, via browser automation — Playwright is the best fit given the site is JSF/`.xhtml` with viewstate and a short session) For each field, the bot looks up the corresponding record in the canonical schema:
   - `confidence: high` → fills in and keeps going on its own.
   - `confidence: low` → **pauses**, flags the field, and waits for a human decision, then continues. At the end, shows a summary of what was automatic vs. manually reviewed before final submission.

## Open points and next steps

- [x] Map field by field (real names/ids, input type, validations) each of the 8 fillable panels of the registration — **done**: UFPA, Atividade Produtiva, Diversos, Patrimônio, Plantel, Tipo Área, Integrantes, and Ações Potenciais are all mapped below, with real field ids pulled from saved HTML captures (see each panel's section)
- [x] "Recursos disponíveis" and "Participação em atividades coletivas" sub-blocks (within Table 3 of the `.docx`) — **confirmed by Khalel: always empty in practice, ignore** (see Patrimônio panel section)
- [x] Decide the bot's login/session strategy: **automated login with stored credentials** — confirmed by Khalel
- [x] Investigate the other data sources the user still needs to identify: **confirmed by Khalel — there are none; `.docx` + WhatsApp text are the only two sources**
- [x] Define in detail the high/low confidence rules of the canonical schema, per field type — implemented in `src/schema/build.py`, one rule per field as documented in each panel's section above
- [x] Confirm browser automation tool: **Playwright, confirmed by Khalel**
- [x] Extraction layer (`src/extract/`) implemented and verified against `examples/example.docx` — both `docx_source.py` (10-table walker) and `whatsapp_source.py` (4-paragraph parser)
- [x] Schema layer (`src/schema/`) implemented and verified — `build.py` turns raw records into per-panel `CanonicalField`s (+ `IndicadorAnswer` for Diagnóstico T0), applying every confidence rule documented above. Dropdown-heavy fields (Atividade, Unidade de Medida, Município, Comunidade/Grupo, Estado Civil, Classificação da Pessoa, Escolaridade) accept an optional live option catalog from `src/fill/` to upgrade low→high confidence just-in-time; without one they default to low rather than guessing
- [x] `src/fill/` (Playwright) implemented for the 8 Cadastrar UFPA panels — locators and fill logic are grounded directly in `examples/anater-signup-page-1.html` (real stable ids, real radio/select DOM structure, real "Adicionar"/"Salvar"/modal button behavior) and smoke-tested with a mock page against the full canonical schema (correct accordion/panel/row ordering, correct number of "Adicionar" clicks per repeatable panel, low-confidence fields correctly held for review instead of blindly filled). **Not yet verified against the live site**: login (`src/fill/site.py:login()`), the "Consultar UFPA" filter screen (`open_cadastrar_ufpa()`), and all of Diagnóstico T0 (search screen + the ~140-question page) — no saved HTML capture exists for any of these three, so their selectors are best-effort placeholders. Needs a supervised first run to confirm/correct
- [ ] Diagnóstico T0 fill-in (the ~140 Indicador questions, already mapped into `IndicadorAnswer` by the schema layer) — not implemented in `src/fill/` yet, only the 8 Cadastrar UFPA panels

---

# UFPA panel — field-by-field mapping

Rebuilt from a real saved copy of the Cadastrar UFPA page
(`examples/anater-singup-page.html`, "Webpage, Complete") cross-referenced
with `examples/example.docx` (mock data). This replaces the earlier draft,
which was based only on screenshots. All ids below are the actual
`name`/`id` attributes JSF renders (form is `formularioUpf`), confirmed by
reading the saved HTML with BeautifulSoup — not guessed.

The saved page is a **blank / freshly opened** form (Entidade selected,
nothing else chosen yet), which matters for a few fields — see
"Cascading/conditional fields" below.

## Fields with a direct match (high confidence)

| Field on the site | Site field id (`formularioUpf:...`) | Type | Source in the `.docx` (Table 1) | Rule |
| --- | --- | --- | --- | --- |
| Nome da UFPA | `idNome` | text (maxlength 100) | Denominação da UFPA | direct copy |
| DAP/CAF | `idDap` | text | CAF | direct copy (different names, same data) |
| Órgão Emissor | `idOrgaoEmissorDap` | text | Órgão Emissor (next to CAF) | direct copy |
| Validade da DAP/CAF | `idValidadeDap` | text | Validade (next to CAF) | direct copy |
| Área do estabelecimento (ha) | `idAreaEstabelecimento` | text | Área do estabelecimento (ha) | direct copy |
| Área do Imóvel Principal (ha) | `idAreaImovelPrincipal` | text | Área do imóvel principal (ha) | direct copy |
| Endereço | `idEndereco` | text (required) | Endereço | direct copy |
| Complemento | `idComplemento` | text | Complemento | direct copy |
| CEP | `idCep` | text (required) | CEP | direct copy |
| A área está inserida em terra pública? | `j_idt281` (auto-generated JSF id — not stable across page loads, match by label instead) | radio Sim/Não | same question | direct copy |
| Nome da gleba | `j_idt285` (auto-generated; also not stable) | text (maxlength 200) | Nome da gleba | direct copy — see note below, it's **not** conditionally hidden |
| A área está inserida em projeto de assentamento – PA? | `idAreaProjetoAssentamentoPa` | radio Sim/Não | same question | direct copy |
| Possui documentos da terra expedido por órgão público? | `idPossuiDocumentosTerra` (+ conditional panel `idPanelDocumentosTerra`) | radio Sim/Não + 6 checkboxes (CATP, LO, TD, CRO, CDRU, CPCV) | same question + same list of 6 documents | direct copy, field by field — sub-checkboxes only exist in the DOM after Sim is picked (see below) |
| A área é georreferenciada? | `j_idt322` (auto-generated) | radio Sim/Não | same question | direct copy |
| A área possui CAR? | `idPossuiCar` (+ conditional panel `idPanelReciboCar`) | radio Sim/Não | same question | direct copy |
| É ocupante primitivo | `idOcupantePrimitivo` (+ conditional panel `idPanelDatasOcupacao`) | radio Sim/Não | same question | direct copy |
| Nome do Transmitente ou beneficiário | `idNomeTransmitenteBeneficiario` | text (maxlength 200) | same field | direct copy |
| CPF | `idCpfTransmitenteBeneficiario` | text | same field | direct copy |
| Está em RB? | `j_idt339` (auto-generated) | radio Sim/Não | — | **fixed value, always "Sim"** — confirmed by Khalel; not read from the `.docx` even though the mock sample happens to have it marked "Não" |
| Ocupa o imóvel de forma mansa e pacífica? | `j_idt343` (auto-generated) | radio Sim/Não | same question | direct copy |
| Forma de acesso — Terrestre | `idAcessoTerrestre` | radio Sim/Não | same question (sub-answer 1) | direct copy |
| Forma de acesso — Fluvial | `idAcessoFluvial` | radio Sim/Não | same question (sub-answer 2) | direct copy |

Several Sim/Não questions render with **auto-generated ids** (`j_idtNNN`)
instead of a stable business id. These numbers can shift between JSF
page renders/versions, so `src/fill/` should locate them **by their
`<label>` text**, not by id, and only fall back to id for the ones that
do have a stable, business-meaningful id (`idPossuiCar`,
`idOcupantePrimitivo`, `idAreaProjetoAssentamentoPa`, etc.).

## Conditional panels — resolved

Second capture (`examples/anater-signup-page-1.html`) has every
conditional toggled to reveal its fields, confirming both the reveal
direction and the real field ids:

| Placeholder span | Revealed when | Real field(s) inside |
| --- | --- | --- |
| `idPanelNomePa` | `idAreaProjetoAssentamentoPa` = **Sim** (confirmed, checked in capture) | `idNomePa` (text) — "Nome do PA" |
| `idPanelDocumentosTerra` | `idPossuiDocumentosTerra` = **Sim** (confirmed) | 6 Sim/Não radio pairs, one per document, auto-generated ids: `j_idt297` (CATP), `j_idt301` (LO), `j_idt305` (TD), `j_idt309` (CRO), `j_idt313` (CDRU), `j_idt317` (CPCV) — match by label text, ids aren't stable |
| `idPanelReciboCar` | `idPossuiCar` = **Sim** (confirmed) | `idNumeroReciboCar` (text) — "nº do recibo do CAR" |
| `idPanelDatasOcupacao` | `idOcupantePrimitivo` = **Não** (confirmed, checked in capture — the non-intuitive direction Khalel had already flagged) | `idDataOcupacaoOriginaria`, `idDataOcupacaoAtual` (text/date) |

All 4 are now fully mappable. Rules:
- **Nome do PA** (`idNomePa`) — direct copy from `.docx` "Nome do PA" (Table 1, only meaningful when the PA question = Sim).
- **6 land documents** — direct copy, field by field, from the matching Sim/Não list in `.docx` Table 1 (CATP, LO, TD, CRO, CDRU, CPCV).
- **nº do recibo do CAR** (`idNumeroReciboCar`) — **low-confidence regardless**: Khalel confirmed the `.docx` sometimes has it filled and sometimes doesn't, so this field always needs human review, not just when data is missing.
- **Data da Ocupação Originária / Atual** — direct copy from `.docx`, only fill when `idOcupantePrimitivo` = Não.

## Dropdowns — resolved with real option values

Confirmed from the same second capture:

| Field | Site field id | Resolution |
| --- | --- | --- |
| Projeto | `idProjeto` | Single real option, value `47` = "UNIÃO COM MUNICÍPIOS" — always auto-select it |
| Instrumento | `idInstrumento` | Single real option, value `CTR.GTI.ASS.667.26` — always auto-select it |
| Meta | `idInstrumentoMeta` | Single real option (cascades from Instrumento): "Cod.: 21100 - UCM - Visita de cadastro e diagnóstico da UFPA (P1) - 8/2026 a 10/2026" — confirmed single-option like Projeto/Instrumento |
| Estado | `idUf` | Renders as a `<span>`, not an editable dropdown, showing "Mato Grosso" already selected. **Confirmed by Khalel: this is wired at the site right before Cadastro (set on the "Consultar UFPA" filter screen), not derived from the `.docx`.** `src/fill/` should treat it as pre-set context, not a field to fill from source data |
| Município | `idMunicipio` (select, 8 options) | Cascades from Estado. Confirmed selected value matches `.docx`: `Bom Jesus Do Araguaia` (option value `6980`) — direct copy from Table 0 "Local de realização da atividade", same as previously assumed |
| Comunidade / Grupo | `idComunidade` (select, 3 options: `--Selecione--`, `TI Maraiwatsede / Xavante`, `PA MACIFE`) | Confirmed: sourced from `.docx` "Grupo" field, **not** a fixed single option. Confirmed type-mismatch risk is real: `.docx` mock value is `PA.MACIFE` (dot) vs dropdown option `PA MACIFE` (space) — an exact string match fails on this real example. `src/fill/` needs normalized/fuzzy matching (e.g. strip punctuation) against the cascaded option list, and must flag low-confidence when nothing matches close enough, rather than assuming exact equality |
| Classificação da UFPA | `idClassificacaoUpf` (select, 3 options: `--Selecione--`, `Agricultores Familiares`, `Assentados`) | Confirmed fixed value, always `Assentados` — not read from the `.docx` |

## "Coordenadas" block — scope decision reversed

**Correction to the earlier scope decision:** this block is real data and
must **not** be ignored, except the 3 geographic-coordinate fields, which
are always empty. Matches `.docx` Table 2 part 1 ("Coordenadas Geográficas"
+ "individual questions") 1:1, same structure as the other Sim/Não
fields in this panel.

| Field on the site | Site field id | Source in the `.docx` (Table 2) | Rule |
| --- | --- | --- | --- |
| Latitude principal / Longitude principal / Local | not present in this saved page (no matching label anywhere in the HTML) | Table 2 rows 1–2, always blank in practice | **ignore** — always empty, not filled on the site (likely captured via the georeferencing map widget instead, if at all) |
| Exerce cargo, emprego ou função pública remunerada? | `idExerceCargoPublico` (+ panel `idPanelCargoInstituicao`) | same question | direct copy |
| Presta serviço de interesse comunitário à comunidade rural...? | `j_idt357` (auto-generated) | same question | direct copy |
| Já foi beneficiário(a) do Programa Nacional de Reforma Agrária – PNRA...? | `j_idt361` (auto-generated) | same question | **fixed value, always "Sim"** — confirmed by Khalel; not read from the `.docx`, even though the mock sample has it marked "Não" |
| É proprietário, cotista ou acionista de sociedade empresária em atividade? | `j_idt365` (auto-generated) | same question | direct copy |
| É proprietário(a) de outro imóvel rural dentro do território nacional? | `j_idt369` (auto-generated) | same question | direct copy |
| Aufere renda familiar... não agrária...? | `j_idt373` (auto-generated) | same question | direct copy |

Same caveat as before: match these by label text, not the `j_idtNNN` id,
since those numbers aren't stable.

## Remaining fields with no `.docx` source

| Field on the site | Site field id | Resolution |
| --- | --- | --- |
| Bairro | `idBairro` (text, optional) | **Confirmed by Khalel: no source, ignore.** Field exists on the site but is never filled by the bot |
| Número | `idNumero` (text, optional) | Same as Bairro — **confirmed ignore, never filled** |
| Programa de Fomento | `idPbsm` (radio, required, 4 options: `FEZ_USO_FOMENTO`, `FAZ_USO_FOMENTO`, `FARA_USO_FOMENTO`, `NENHUM`) | Confirmed fixed value, always `NENHUM` ("Nenhum.") — not read from the `.docx` |

## UFPA panel: fully mapped

Every field, dropdown, and conditional panel in this panel now has a
confirmed source (`.docx`, fixed value, or "wired at the site") and a
real field id. Nothing left open here — ready for `src/fill/`
implementation whenever we get to it.

## How I want to proceed from here

Same format for the remaining panels: pull real field ids/types/options
straight from the saved HTML, cross-check against the `.docx`, and only
flag genuinely open points — no need to describe fields verbally.

---

# Atividade Produtiva panel — field-by-field mapping

Pulled from `examples/anater-signup-page-1.html`, between the
`<!-- Início tab Atividade Produtiva -->` and `<!-- Fim tab atividade
produtiva -->` comments. Cross-referenced with `examples/example.docx`
Table 2, "Atividades produtivas da UFPA (Produção agrícola, não agrícolas
e serviços)" section (rows 10–19).

## Structure: a repeatable "add row" widget, not a fixed field set

Unlike the UFPA panel, this one is a single input row (inside
`idPanelAtividadeProdutiva`) that gets filled and submitted once **per
activity**, appending a row to a running table. The `.docx` template
allows up to 8 activities per UFPA (rows 12–19 of Table 2); the mock only
has one filled in (the rest are blank placeholder rows). `src/fill/`
needs to loop: fill the input row → click Adicionar → repeat for each
activity found in the source.

| Field on the site | Site field id (`formularioUpf:...`) | Type | Source in the `.docx` (Table 2) | Rule |
| --- | --- | --- | --- | --- |
| Atividade | `idAtividadeProdutivaUpfAtividadeProdutivasAd` | select (~300 options, e.g. "Pecuária Corte", "Café", "Avicultura de corte"...) | "Atividade" column | direct copy — needs exact (or close) text match against the dropdown option list; flag low-confidence if the `.docx` value doesn't match any option |
| Produção Anual | `idProducaoAnualUpfAtividadeProdutivasAd` | text | "Produção anual" column | direct copy (numeric, Brazilian decimal comma, e.g. `16,780`) |
| Unidade de Medida | `idUnidMedidaUpfAtividadeProdutivasAd` | select (~130 options: kg, cabeça, hectare, litro, saca, arroba, unidade, etc.) | "Unidade" column | direct copy — same type-mismatch risk as "Atividade": needs matching against the option list, not assumed correct |
| Atividade Principal | `idCheckAtividadePrincipal` | checkbox | Sim/Não checkbox next to each activity row | check the box only when marked Sim in the `.docx` |
| Ações → "Adicionar" | `j_idt537` (auto-generated `<a>`, AJAX) | button | — | commits the current row's 4 fields into the table and clears the inputs for the next activity; click once per activity, not once per panel |

## Data-quality example found in the mock file (real, not hypothetical)

Row 12 of Table 2 in the mock `.docx`: Atividade = `Pecuária Corte`,
Produção anual = `16,780`, **Unidade = `45`**. `45` does not match any of
the ~130 real "Unidade de Medida" dropdown options (all unit names like
`kg`, `cabeça`, `arroba` — never a bare number). This is exactly the
"text that didn't match the site's expected format 1:1" case from the
architecture doc's confidence rules: **low confidence, pause for human
review** — don't guess which unit `45` was supposed to mean.

## Open points

- [ ] Confirm whether more than one activity can be marked "Atividade Principal" at once, or if the site enforces a single selection (matters for how `src/fill/` should validate before submitting)
- [ ] No blank capture of this panel with an activity already added (i.e. an existing table row) was available — the real ids/structure of an **already-submitted** activity row (for a future edit/remove flow) are still unknown, though not needed for the write-only registration flow this bot performs

---

# Diversos panel — field-by-field mapping

Pulled from `examples/anater-signup-page-1.html`, from
`id="formularioUpf:idPanelMulheres"` through `id="collapsePerfilComunicacao"`
(the accordion `id`s call it "Perfil Comunicação"; the visible panel title
is "Diversos"). Cross-referenced with `examples/example.docx` Table 2,
"Diversos" section (rows 20–27).

14 Sim/Não questions total, split into two labeled groups, all with
auto-generated `j_idtNNN` ids (match by label text, not id — same caveat
as elsewhere in this document).

## Meios de Comunicação (7 fields on site vs. 6 in the `.docx`)

| Field on the site | Site field id | Source in the `.docx` | Rule |
| --- | --- | --- | --- |
| Celular? | `j_idt548` | Celular | direct copy |
| Rádio? | `j_idt563` | Rádio | direct copy |
| Internet? | `j_idt558` | Internet | direct copy |
| TV? | `j_idt568` | Televisão | direct copy (different label, same data) |
| Facebook? | `j_idt553` | Redes Sociais | **confirmed by Khalel: apply the "Redes Sociais" Sim/Não answer to Facebook, Whatsapp, and Youtube alike** — no per-network breakdown exists in the `.docx`, so all 3 get the same value |
| Whatsapp? | `j_idt573` | Redes Sociais | same rule as Facebook, above |
| Youtube? | `j_idt578` | Redes Sociais | same rule as Facebook, above |
| — | — | Outros (`.docx` free-text item + Sim/Não) | **confirmed ignore** — no corresponding site field, dropped |

## Saneamento Rural (7 fields on site vs. 6 in the `.docx`)

| Field on the site | Site field id | Source in the `.docx` | Rule |
| --- | --- | --- | --- |
| Água para consumo? | `j_idt584` | Água para consumo | direct copy |
| Água para consumo tratada? | `j_idt589` | Água para consumo tratada | direct copy |
| Água para produção? | `j_idt594` | Água para produção | direct copy |
| Captação de Água da chuva? | `j_idt599` | Captação de água da chuva | direct copy |
| Esgoto tratado? | `j_idt604` | Esgoto tratado | direct copy |
| Fontes e nascentes protegidas? | `j_idt609` | Fontes protegidas | direct copy (different label, same data) |
| Utiliza agrotóxicos? | `j_idt614` | — (no source in the `.docx`) | **confirmed by Khalel: low confidence, human decides** — always pause on this one rather than leaving it unfilled |

## Diversos panel: fully mapped

Every field has a confirmed rule (direct copy, fan-out from Redes
Sociais, ignore, or flag for human review). Nothing left open.

---

# Patrimônio panel — field-by-field mapping

Pulled from `examples/anater-signup-page-1.html`, from
`id="formularioUpf:idPanelTerraBrasil2"` through the "Plantel" accordion
heading (no literal "Fim tab Patrimônio" comment exists in this capture —
the panel closes right where the next accordion, Plantel, begins).
Cross-referenced with `examples/example.docx` Table 3, which — as
suspected in the original mapping — turns out to span **3 site panels
plus 2 still-unmapped blocks**:

| `.docx` Table 3 block | Rows | Destination |
| --- | --- | --- |
| Patrimônio (machinery/vehicles/etc.) | 2–9 | **This panel** |
| Quantidade de cabeças no plantel | 11–19 | Plantel panel (next) |
| Área destinada a: | 21–28 | Tipo Área panel |
| Recursos disponíveis para produção, beneficiamento e comercialização | 30–38 | **confirmed ignore — always empty in practice** |
| Participação em atividades coletivas | 40–46 | **confirmed ignore — always empty in practice** |

## Structure: repeatable "add row" widget (same pattern as Atividade Produtiva)

| Field on the site | Site field id (`formularioUpf:...`) | Type |
| --- | --- | --- |
| Descrição | `idUpfPatrimonioAd` | select, 9 fixed options (`01-...` through `09-Não se aplica`) |
| Quantidade | `idUpfPatrimonioQuantidadeAd` | text |
| Unidade Medida | `idUpfPatrimonioUnidMedidaAd` | select, same ~130-option unit list as Atividade Produtiva |
| Ações → "Adicionar" | `j_idt667` (AJAX) | button — commits the row, clears inputs, repeat per item |

## Field mapping, `.docx` row → Descrição option

| `.docx` row | Site "Descrição" option | Quantidade (mock) | Rule |
| --- | --- | --- | --- |
| Quantidade de implemento agrícolas | `01-Quantidade de implemento agrícolas` | 0 | **skip — Quantidade = 0** (confirmed: don't add a row when the family has none) |
| Quantidade de máquinas agrícolas | `02-Quantidade de máquinas agrícolas` | 0 | skip — Quantidade = 0 |
| Quantidade de veículos de passeio | `03-Quantidade de veículos de passeio` | 2 | add row |
| Quantidade de construções rurais | `04-Quantidade de construções rurais` | 1 | add row |
| Quantidade de motores elétricos (não pertencente às máquinas) | `05-Quantidade de motores elétricos` | 0 | skip — Quantidade = 0 (docx label has an extra parenthetical; matches by the "motores elétricos" core text) |
| Quantidade de conjuntos de irrigação | `06-Quantidade de conjuntos de irrigação` | 0 | skip — Quantidade = 0 |
| Quantidade de animais de trabalho | `07-Quantidade de animais de trabalho` | 2 | add row |
| Quantidade de veículos / maquinário de tração animal | `08-Quantidade de veículos / maquinário de tração animal` | 4 | add row |
| — | `09-Não se aplica` | — | not driven by a `.docx` row; presumably a manual fallback option, unused by the bot |

## Unidade Medida — fixed rule, ignores the `.docx`'s "Unid." column entirely

**Confirmed by Khalel:** Unidade Medida is a fixed value per Descrição
category, not read from the `.docx`'s "Unid." free-text column (which is
mostly blank anyway, and the two rows where it does have a value —
"Moto/carro", "Carro/m/cavalo" — don't match any real dropdown option,
confirming it was never meant to be parsed):

- **`07-Quantidade de animais de trabalho`** → always `unidade animal`
- **Every other category** → always `unidade`

## Patrimônio panel: fully mapped

Descrição categories, Quantidade sourcing, zero-quantity handling, and
Unidade Medida are all confirmed rules. The two other `.docx` blocks in
Table 3 (Recursos disponíveis, Participação em atividades coletivas) are
confirmed always empty in practice — ignored, not fed into any panel.

---

# Plantel panel — field-by-field mapping

Pulled from `examples/anater-signup-page-1.html` (no literal "Início/Fim
tab Plantel" comments exist in this capture — used the accordion
boundaries instead: `headingPlantel`/`collapsePlantel` through
`headingTipoArea`). Cross-referenced with `examples/example.docx` Table 3,
"Quantidade de cabeças no plantel" sub-block (rows 11–19).

Same repeatable "add row" widget pattern as Atividade Produtiva and
Patrimônio.

| Field on the site | Site field id (`formularioUpf:...`) | Type |
| --- | --- | --- |
| Descrição | `idUpfPlantelDescricaoAd` | select, 10 fixed options (`01-Bovinos` through `10-Não se Aplica`) |
| Quantidade | `idUpfPlantelQuantidadeAd` | text |
| Unidade Medida | `idUpfPlantelUnidMedidaAd` | select, same ~130-option unit list as the other "add row" panels |
| Ações → "Adicionar" | `j_idt814` (AJAX) | button — commits the row, clears inputs, repeat per item |

## Field mapping, `.docx` row → Descrição option

Unlike Patrimônio, this one is a clean 1:1 name match, 9 of 9 categories:

| `.docx` row | Site "Descrição" option | Quantidade (mock) |
| --- | --- | --- |
| Bovinos | `01-Bovinos` | 45 |
| Ovinos | `02-Ovinos` | 0 — skip |
| Caprinos | `03-Caprinos` | 0 — skip |
| Suínos | `04-Suínos` | 2 |
| Aves | `05-Aves` | 20 |
| Bubalinos | `06-Bubalinos` | 0 — skip |
| Equinos, muares e asininos | `07-Equinos, muares e asininos` | 2 |
| Colmeias | `08-Colmeias` | 0 — skip |
| Pequenos animais (outros) | `09-Pequenos animais (outros)` | 2 |
| — | `10-Não se Aplica` | not driven by a `.docx` row, unused by the bot |

Same rules as Patrimônio, confirmed by Khalel:
- **Skip rows where Quantidade = 0.**
- **Unidade Medida is fixed, always `cabeça`, for every category** — including Colmeias and Pequenos animais, where the `.docx`'s "Unid." column happens to be blank (ignored either way, same as Patrimônio's non-matching "Unid." values).

## Plantel panel: fully mapped

---

# Tipo Área panel — field-by-field mapping

Pulled from `examples/anater-signup-page-1.html` (accordion boundaries
`headingTipoArea`/`collapseTipoArea` through the start of "Ações
Potenciais" — no literal "Início/Fim tab Tipo Area" comments exist in
this capture, same as Plantel). Cross-referenced with
`examples/example.docx` Table 3, "Área destinada a:" sub-block (rows
21–28).

Same repeatable "add row" widget pattern as Atividade Produtiva,
Patrimônio, and Plantel.

| Field on the site | Site field id (`formularioUpf:...`) | Type |
| --- | --- | --- |
| Descrição | `idUpfTipoAreaDescricaoAd` | select, 8 fixed options (`01-Pastagens` through `08-Não se Aplica`) |
| Quantidade | `idUpfTipoAreaQuantidadeAd` | text |
| Unidade Medida | `idUpfTipoAreaUnidMedidaAd` | select, same ~130-option unit list as the other "add row" panels |
| Ações → "Adicionar" | (auto-generated AJAX button, same pattern as the other 3 panels) | button — commits the row, clears inputs, repeat per item |

## Field mapping, `.docx` row → Descrição option, confirmed by Khalel

Unlike Patrimônio/Plantel, this category list is **not** a clean 1:1 with
the `.docx` — two `.docx` rows have no site equivalent and are dropped,
and one site option (`Agrofloresta`) has no `.docx` source at all:

| `.docx` row | Site "Descrição" option | Unidade Medida (fixed) | Rule |
| --- | --- | --- | --- |
| Pastagens | `01-Pastagens` | `hectare` | direct copy (skip if Quantidade = 0, same as Patrimônio/Plantel) |
| Culturas temporárias | `02-Culturas Temporárias` | `hectare` | direct copy, skip if 0 |
| Culturas permanentes | `03-Culturas permanentes` | `hectare` | direct copy, skip if 0 |
| Lâmina d'água | `04-Lâmina d'água` | `metro quadrado` → site option value is `m²` | direct copy, skip if 0 |
| Extrativismo | `05-Extrativismo` | — | **confirmed ignore** — never filled by the bot regardless of the `.docx` value |
| Reserva Legal | `06-Reserva Legal` | `hectare` | direct copy, skip if 0 |
| — | `07-Agrofloresta` | — | no `.docx` source, unused by the bot |
| — | `08-Não se Aplica` | — | not driven by a `.docx` row, unused by the bot |
| Área de Preservação Permanente - APP | — (no matching site option) | — | **confirmed ignore** — dropped silently, not paused for review, even though the `.docx` value (108,6128) is real and non-zero |
| Outros | — (no matching site option) | — | **confirmed ignore** — dropped silently (also happens to be 0 in the mock) |

Note: unlike Patrimônio/Plantel, the Unidade Medida per-category rule
above is only confirmed for the 4 categories that get filled
(Pastagens, Culturas Temporárias, Culturas permanentes, Reserva Legal →
`hectare`; Lâmina d'água → `m²`) — **Khalel flagged this list of 4 as
provisional** ("if we figure out the rule after all... for now let's map
one by one"), so treat it as the working rule but be ready to revisit if
a future `.docx` sample breaks the hectare/m² split.

## Tipo Área panel: mapped, one caveat carried forward

Descrição categories, drop rules, and per-row Unidade Medida are all
confirmed. The only open item is the note above: the Unidade Medida rule
was filled in row-by-row rather than derived from a general principle,
so it may need revisiting once more `.docx` samples are available.

---

# Integrantes panel — field-by-field mapping

Pulled from `examples/anater-signup-page-1.html`, from
`<!-- Início tab Integrantes -->` to `<!-- Fim tab Integrantes -->`
(lines 2857–2872) — which turned out to be just the panel's trigger UI
("Inserir Integrante" button + an empty `idPanelIntegrantes` list
placeholder), plus the actual "Cadastrar Pessoa" **modal form**
(`formularioUpf:formularioBeneficiarioPf`), located much further down in
the same HTML file (~line 3068–3555), which is where every real field
lives. Cross-referenced with `examples/example.docx` Tables 5 and 6
("Integrantes", page 6) — one table per person; the mock only has person
1 filled in, table 6 (person 2) is entirely blank, confirming this is a
per-person repeatable block, same pattern as "Inserir Integrante".

## Structure: modal form, one submission per person

"Inserir Integrante" (`j_idt910`) opens the modal via AJAX
(`abrirModalCadastrarBeneficiario()`). The modal's "Salvar" button
(`j_idt1081`) commits the person into `idPanelIntegrantes` and clears the
form for the next one. `src/fill/` loops this once per person block found
in the `.docx`.

## Fields with a direct match (high confidence)

| Field on the site | Site field id (`formularioUpf:...`) | Type | Source in the `.docx` (Tables 5/6) | Rule |
| --- | --- | --- | --- | --- |
| CPF | `idCpf` (required) | text | CPF | direct copy |
| NIS/CAD ÚNICO | `idNis` | text | NIS/CAD ÚNICO | direct copy (blank in the mock) |
| Nome | `idNomeBeneficiarioPf` (required) | text | Nome | direct copy |
| Apelido | `idApelido` | text | Apelido | direct copy |
| Sexo | `idSexo` (required, radio M/F) | radio | sexo | direct copy (Masculino→M, Feminino→F) |
| Data de Nascimento | `idDataNasc` (required) | text | Data de nascimento | direct copy (blank in the mock — required field with no value is itself a low-confidence case if it ever happens for real) |
| Nome da Mãe | `idNomeMae` (required) | text | Nome da mãe | direct copy |
| Nome do Pai | `idNomePai` | text | Nome do pai | direct copy |
| Classificação da Pessoa | `idClassificacaoBeneficiario` (required, select, ~29 options) | select | Classificação da pessoa | direct copy — clean match in the mock ("Assentado" is a literal option); this is a **per-person** field, distinct from the UFPA panel's fixed "Classificação da UFPA" ("Assentados", plural) |
| Email | `idEmailBeneficiarioPf` | text | E-mail | direct copy |
| Modo preferencial (Correio/E-mail) | `idModoComunicacaoIntegrante` (radio) | radio | Modo preferencial para recebimento de comunicações | direct copy |
| Resp. pela Família | `idRespFamilia` (required, radio Sim/Não) | radio | Responsável pela UFPA | direct copy |
| Celular | `idCelular` | text | Telefones | **confirmed: the `.docx`'s single "Telefones" value always goes to Celular** — Telefone Residencial is left blank |

## Fixed values (not read from the `.docx`)

| Field on the site | Site field id | Rule |
| --- | --- | --- |
| Orientação sexual | `idOrientacaoSexual` (required, select) | **fixed, always `Heterossexual`** — confirmed by Khalel; no source exists in the `.docx` for this field |
| Identidade de gênero | `idIdentidadeGenero` (required, select) | **fixed, always `Cysgênero`** — confirmed by Khalel |
| Regime de Bens | `idRegimeBensIntegrante` (select) | **fixed, always `Comunhão parcial de bens`, whenever Estado Civil = Casado(a)** — confirmed by Khalel; not derived from the `.docx`'s generic "Comunhão de bens" text. Since Estado Civil itself is now low-confidence (see below), this rule applies once a human has confirmed Estado Civil, not automatically from the `.docx` value |

## Conditional field — Estado Civil = Casado(a) or União estável

**Confirmed by Khalel:** when Estado Civil is `Casado(a)` or `União
estável`, an extra label appears — **"Data da União"** (text), not
literally "Data do Casamento" as the `.docx` label suggests, though it's
the same underlying data (`.docx` "Data do Casamento", e.g. `30/07/2001`)
— direct copy once revealed.

The site wires this via `idPanelDataCasamentoIntegrante`
(`onchange` on `idEstadoCivilIntegrante`). Real field id confirmed by
Khalel: **`idDataCasamentoIntegrante`** (text, "Data da União").

## No source in the `.docx` (both required — need low-confidence handling)

| Field on the site | Site field id | Rule |
| --- | --- | --- |
| Parentesco | `idParentesco` (required, select, ~20 options) | **confirmed by Khalel: low confidence, pause** — the mock's responsible-person row has this blank, and there's no fixed default; always needs human input when the `.docx` doesn't provide it |

## `.docx` fields with no site destination

| `.docx` field | Rule |
| --- | --- |
| Carteira de identidade/órgão expedidor | **confirmed ignore** — no matching field anywhere in the "Cadastrar Pessoa" modal, dropped silently |

## Low-confidence source data (real example from the mock)

| Field on the site | Issue |
| --- | --- |
| Escolaridade (`codEscolaridade`, required, 13 coded options) | The mock `.docx` has `"5 Ano"` (grade-level notation), which doesn't match any of the coded options (Analfabeto, Alfabetizado, Fundamental, Fundamental Incompleto, Ensino Médio, Ensino Médio Incompleto, Superior, Superior Incompleto, Pós Graduação, Mestrado, Doutorado, Em idade não escolar, Não Informado). **Confirmed by Khalel: low confidence, pause** — don't guess Fundamental vs. Fundamental Incompleto from a bare grade number |
| Estado Civil (`idEstadoCivilIntegrante`, select) | **Confirmed by Khalel: low confidence, human needed** — even though the `.docx` value ("Casado") looks like a clean match to a site option ("Casado(a)"), this field always needs human review rather than being auto-filled |

## Out of scope (already decided at the mapping-session level)

Per-member "Políticas Públicas" fields seen in the same modal area
(`idPoliticaPublicaIntegrante`, `idPoliticaPublicaPolitica`,
`idPoliticaPublicaDataAdesao`) — out of scope, `.docx` Table 7 is
likewise excluded (see top of this document).

## Integrantes panel: fully mapped

Every field now has a confirmed rule (direct copy, fixed value,
low-confidence pause, or dropped for no site/`.docx` match), including
the conditional "Data da União" field. Nothing left open.

---

# Ações Potenciais panel — field-by-field mapping

Pulled from `examples/anater-signup-page-1.html`, from
`<!-- Início tab Ações Pontenciais-->` to `<!-- Fim tab Ações Pontencias
-->` (lines 2814–2843). This is the one panel **not** sourced from the
`.docx` — per the original mapping session, it's fed exclusively by the
loose WhatsApp text (see top of this document). Confirmed by Khalel: the
text is standardized per PA + município (reused across every family
registered there), not written custom per family.

## Structure: 4 plain textareas, no conditional logic

| Field on the site | Site field id (`formularioUpf:...`) | Type |
| --- | --- | --- |
| Eixo Produtivo | `idEixoProdutivo` (required) | textarea, no maxlength |
| Eixo Social | `idEixoSocial` (required) | textarea, no maxlength |
| Eixo Ambiental | `idEixoAmbiental` (required) | textarea, no maxlength |
| Eixo Fundiário | `idEixoFundiario` (required) | textarea, no maxlength |

## Source format (WhatsApp text)

The message has a fixed shape, confirmed with a real example:

```
<PA NAME> - <MUNICÍPIO>

Eixo Produtivo
<paragraph>

Eixo Social
<paragraph>

Eixo Ambiental
<paragraph>

Eixo Fundiário
<paragraph>
```

- **First line** (`<PA NAME> - <MUNICÍPIO>`) identifies which
  PA/município template the text belongs to — e.g. `PA MACIFE - BOM
  JESUS DO ARAGUAIA`. This should be cross-checked against the family's
  own UFPA data (`idNomePa` / `idMunicipio` from the UFPA panel) before
  using the text: **if the header doesn't match the family's actual
  PA/município, that's a low-confidence case** — the extractor likely
  grabbed the wrong template, don't apply it blindly.
- **Four sections**, each starting with the exact header line `Eixo
  Produtivo`, `Eixo Social`, `Eixo Ambiental`, or `Eixo Fundiário`,
  followed by one paragraph of free text running until the next header
  (or end of message). Direct copy, whole paragraph, into the matching
  textarea — no further parsing needed since these are plain multi-line
  text fields on the site.

## Ações Potenciais panel: fully mapped

4 fields, clean 1:1 structure, one cross-check rule (PA/município header
match). Nothing left open.
