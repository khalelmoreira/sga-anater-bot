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

- [ ] Map field by field (real names/ids, input type, validations) each of the 8 fillable panels of the registration — do this in separate sessions per panel, given the volume
- [ ] Confirm whether the "Recursos disponíveis" and "Participação em atividades coletivas" sub-blocks (within Table 3 of the `.docx`) have a corresponding panel on the site, or are out of scope
- [ ] Decide the bot's login/session strategy: manual login (person authenticates and the bot takes over the session) vs. automated login with stored credentials
- [ ] Investigate the other data sources the user still needs to identify, and how they fit into the extraction layer
- [ ] Define in detail the high/low confidence rules of the canonical schema, per field type
- [ ] Confirm browser automation tool (Playwright is the current recommendation)
- [ ] Only start writing code after this mapping is done

---

# UFPA panel — field-by-field mapping

Draft made from what we've seen so far (site screenshots + Table 1 of the
`.docx`). Instead of you describing each field, I've already put together
the mapping and only flag where I'm not sure — you just need to
correct/confirm the marked points.

## Fields with a direct match (high confidence)

| Field on the site | Type | Source in the `.docx` (Table 1) | Rule |
| --- | --- | --- | --- |
| Nome da UFPA | text | Denominação da UFPA | direct copy |
| DAP/CAF | text | CAF | direct copy (different names, same data) |
| Órgão Emissor | text | Órgão Emissor (next to CAF) | direct copy |
| Validade da DAP/CAF | text/date | Validade (next to CAF) | direct copy |
| Área do estabelecimento (ha) | number | Área do estabelecimento(ha) | direct copy |
| Área do Imóvel Principal (ha) | number | Área do imóvel principal (ha) | direct copy |
| Endereço | text | Endereço | direct copy |
| Complemento | text | Complemento | direct copy |
| CEP | text | CEP | direct copy |
| A área está inserida em terra pública? | Sim/Não | same question | direct copy |
| Nome da gleba | text | Nome da gleba | only fill in if the question above = Sim |
| A área está inserida em projeto de assentamento – PA? | Sim/Não | same question | direct copy |
| Possui documentos da terra expedido por órgão público? | Sim/Não + 6 checkboxes (CATP, LO, TD, CRO, CDRU, CPCV) | same question + same list of 6 documents | direct copy, field by field |
| A área é georreferenciada? | Sim/Não | same question | direct copy |
| A área possui CAR? | Sim/Não | same question | direct copy |
| É ocupante primitivo | Sim/Não | same question | direct copy |
| Nome do Transmitente ou beneficiário | text | same field | direct copy |
| CPF | text | same field | direct copy |
| Está em RB? | Sim/Não | same question | direct copy |
| Ocupa o imóvel de forma mansa e pacífica? | Sim/Não | same question | direct copy |
| Forma de acesso — Terrestre / Fluvial | Sim/Não each | same question (2 sub-answers) | direct copy |

## Out of scope in this panel

The panel's final 6 fields (public office, PRNA, business partner, two about property ownership, non-farm income) — already decided these are left out.

## Site fields with no clear source in the `.docx` (need your confirmation)

| Field on the site | Type | What I saw in Table 1 | Question |
| --- | --- | --- | --- |
| Projeto / Instrumento / Meta | dropdown | Not in Table 1 (comes from Table 0 — Entidade executora — or is selected manually beforehand) | Already confirmed Projeto/Instrumento have a single option. What about **Meta**? Also single, or does it vary per registration? |
| Estado / Município | dropdown | Appear loose in Table 7 (UF: MT, Município: Bom Jesus Do Araguaia), not in Table 1 | Confirming this comes from Table 7 ("Local de realização da atividade")? |
| Bairro | text | Not found in Table 1 (only Endereço, Complemento, CEP, Grupo) | Is it always left blank, or is it somewhere else in the file I haven't seen yet? |
| Número | text | Not found in Table 1 | Same question as Bairro |
| Comunidade / Grupo | **dropdown** (list of pre-registered options) | Table 1 has a "Grupo" field as **blank free text** | Possible type mismatch: if the `.docx` value doesn't match any dropdown option, this becomes a manual-review case. Confirming this reasoning? |
| Classificação da UFPA | dropdown | Not found in Table 1 | Where does this data come from? |
| Programa de Fomento | 4 options (radio): Já fez uso / Pertence ao Programa / Fará uso / Nenhum | Not found in Table 1 | Where does this data come from? |
| nº do recibo do CAR | text | Exists in Table 1 (next to the CAR question) | Didn't see this field in the site screenshots — does it exist, or is it hidden until "Sim" is marked for CAR? |
| Data da Ocupação Originária / Data da Ocupação Atual | date | Exist in Table 1 (next to "É ocupante primitivo") | Didn't see these fields in the site screenshots — do they exist somewhere in the panel, or is this data not captured by the site? |

## How I want to proceed from here

For the next panels, I plan to repeat this format: I put together the mapping table draft from what we've already seen, and only ask you about the points that had no clear source or a possible inconsistency — instead of asking you to describe field by field. Does that make sense? If so, I just need the answers above to close the UFPA panel.
