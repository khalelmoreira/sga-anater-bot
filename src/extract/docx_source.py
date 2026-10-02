"""
Extractor for the registration `.docx` file (main source).

Walks the document's 10 tables (see docs/mapeamento.md for the full
mapping) and returns a list of raw records — one per field/question
found. This layer does NOT decide confidence or resolve mismatches;
that's the schema layer's job (src/schema/). Here we only parse what's
literally on the page, as faithfully as possible, keeping the original
text alongside the parsed value so the schema layer (or a human) can
always trace a decision back to the source.

Table index -> section, per docs/mapeamento.md:
  0  Entidade executora          -> "entidade"
  1  Dados da UFPA                -> "ufpa"
  2  Coordenadas/individual Qs,
     Atividades produtivas,
     Diversos                     -> "coordenadas", "atividade_produtiva", "diversos"
  3  Patrimônio (patrimônio, plantel, tipo_area, + 2 always-empty blocks)
  4  Ações Potenciais             -> always empty in the .docx; real source is WhatsApp text (see whatsapp_source.py)
  5, 6 Integrantes (one per person) -> "integrantes"
  7  Políticas Públicas           -> out of scope, not extracted
  8  Proteção de Dados (LGPD)     -> out of scope, not extracted
  9  Indicadores                  -> "indicadores" (feeds Diagnóstico T0, not the registration panels)
"""

import re

from docx import Document


def _cells(row):
    """Row cells with merged-cell duplicates collapsed, in document order."""
    out = []
    prev = None
    for c in row.cells:
        text = c.text.strip()
        if text != prev:
            out.append(text)
        prev = text
    return out


def _label_value(cell_text):
    """Splits a 'Label: value' cell (possibly multi-line) into (label, value).

    Returns (None, cell_text) when there's no ':' to split on (e.g. a
    section header cell like "Entidade executora").
    """
    if ":" not in cell_text:
        return None, cell_text.strip()
    label, _, value = cell_text.partition(":")
    return label.strip(), value.strip()


def _parse_sim_nao_bracket(text):
    """Parses '[ x ] S  [  ] N' style checkboxes -> True/False/None.

    None covers both "neither marked" and "both marked" — an ambiguous
    source, left for the schema layer to flag as low confidence rather
    than guessed here.
    """
    m = re.search(r"\[\s*([xX]?)\s*\]\s*S\D*?\[\s*([xX]?)\s*\]\s*N", text)
    if not m:
        return None
    s_marked, n_marked = bool(m.group(1)), bool(m.group(2))
    if s_marked and not n_marked:
        return True
    if n_marked and not s_marked:
        return False
    return None


def _parse_sim_nao_paren(text):
    """Parses '( x ) Sim ( ) Não [( ) Não se aplica]' -> 'Sim'/'Não'/'Não se aplica'/None."""
    m = re.search(
        r"\(\s*([xX]?)\s*\)\s*Sim\s*\(\s*([xX]?)\s*\)\s*N[ãa]o"
        r"(?:\s*\(\s*([xX]?)\s*\)\s*N[ãa]o se aplica)?",
        text,
    )
    if not m:
        return None
    flags = [bool(m.group(1)), bool(m.group(2)), bool(m.group(3))]
    labels = ["Sim", "Não", "Não se aplica"]
    marked = [label for label, flag in zip(labels, flags) if flag]
    return marked[0] if len(marked) == 1 else None


def _parse_xs_n(s_cell, n_cell):
    """Parses the Diversos-table 'xS' / 'N' mini-cell pair -> True/False/None."""
    s_marked = s_cell.strip().lower().startswith("x")
    n_marked = n_cell.strip().lower().startswith("x")
    if s_marked and not n_marked:
        return True
    if n_marked and not s_marked:
        return False
    return None


def _rec(section, field, value, raw):
    return {"source": "docx", "section": section, "field": field, "value": value, "raw": raw}


def _extract_entidade(table):
    """Table 0 — Entidade executora / Agente de Ater / Local de realização."""
    records = []
    agente_idx = 0
    section = "entidade"
    for row in table.rows:
        for cell_text in _cells(row):
            if cell_text == "Agente de Ater":
                section = "entidade.agente_ater"
                continue
            if cell_text == "Local de realização da atividade":
                section = "entidade.local"
                continue
            label, value = _label_value(cell_text)
            if label is None:
                continue
            sec = section
            if section == "entidade.agente_ater" and label == "Nome":
                agente_idx += 1
                sec = f"entidade.agente_ater[{agente_idx}]"
            elif section == "entidade.agente_ater":
                sec = f"entidade.agente_ater[{agente_idx}]"
            records.append(_rec(sec, label, value, cell_text))
    return records


def _extract_ufpa(table):
    """Table 1 — Dados da UFPA."""
    records = []
    rows = [_cells(r) for r in table.rows]

    def find_row(*needles):
        for r in rows:
            if r and any(n in r[0] for n in needles):
                return r
        return None

    section = "ufpa"

    r = find_row("Denominação da UFPA")
    if r:
        records.append(_rec(section, "Denominação da UFPA", r[1] if len(r) > 1 else None, str(r)))

    r = find_row("inserida em terra pública")
    if r:
        records.append(_rec(section, "Área em terra pública?", _parse_sim_nao_bracket(r[1]), str(r)))
        records.append(_rec(section, "Nome da gleba", r[3] if len(r) > 3 else None, str(r)))

    r = find_row("projeto de assentamento")
    if r:
        records.append(_rec(section, "Área em projeto de assentamento (PA)?", _parse_sim_nao_bracket(r[1]), str(r)))
        records.append(_rec(section, "Nome do PA", r[3] if len(r) > 3 else None, str(r)))

    r = find_row("documentos da terra")
    if r:
        records.append(_rec(section, "Possui documentos da terra?", _parse_sim_nao_bracket(r[1]), str(r)))
        docs_text = r[2] if len(r) > 2 else ""
        doc_labels = {
            "CATP": "Contrato de Alienação de Terras Públicas",
            "LO": "Licença de ocupação",
            "TD": "Titulo Definitivo",
            "CRO": "Certidão de reconhecimento de ocupação",
            "CDRU": "Contrato de Concessão de Direito Real de Uso",
            "CPCV": "Contrato de promessa de Compra e venda",
        }
        for chunk in docs_text.split("\n"):
            chunk = chunk.strip()
            for abbr in doc_labels:
                if re.search(rf"\b{abbr}\b", chunk):
                    records.append(_rec(section, f"Documento da terra: {abbr}", _parse_sim_nao_bracket(chunk), chunk))
                    break

    r = find_row("georreferenciada")
    if r:
        records.append(_rec(section, "Área georreferenciada?", _parse_sim_nao_bracket(r[1]), str(r)))
        records.append(_rec(section, "Possui CAR?", _parse_sim_nao_bracket(r[3]) if len(r) > 3 else None, str(r)))
        records.append(_rec(section, "Nº do recibo do CAR", r[5] if len(r) > 5 else None, str(r)))

    r = find_row("CAF")
    if r:
        records.append(_rec(section, "CAF", r[1] if len(r) > 1 else None, str(r)))
        records.append(_rec(section, "Órgão Emissor", r[3] if len(r) > 3 else None, str(r)))
        records.append(_rec(section, "Validade da CAF", r[5] if len(r) > 5 else None, str(r)))

    r = find_row("ocupante primitivo")
    if r:
        records.append(_rec(section, "É ocupante primitivo?", _parse_sim_nao_bracket(r[1]), str(r)))
        records.append(_rec(section, "Data da Ocupação Originária", r[3] if len(r) > 3 else None, str(r)))
        records.append(_rec(section, "Data da Ocupação Atual", r[5] if len(r) > 5 else None, str(r)))

    r = find_row("Nome do Transmitente")
    if r:
        records.append(_rec(section, "Nome do Transmitente ou beneficiário", r[1] if len(r) > 1 else None, str(r)))

    r = None
    for row_cells in rows:
        if row_cells and row_cells[0].strip() == "CPF:":
            r = row_cells
            break
    if r:
        records.append(_rec(section, "CPF (Transmitente/beneficiário)", r[1] if len(r) > 1 else None, str(r)))

    r = find_row("Está em RB")
    if r:
        records.append(_rec(section, "Está em RB?", _parse_sim_nao_bracket(r[1]), str(r)))
        records.append(_rec(section, "Ocupa o imóvel de forma mansa e pacífica?", _parse_sim_nao_bracket(r[3]) if len(r) > 3 else None, str(r)))
        acesso = r[5] if len(r) > 5 else ""
        if "Terrestre" in acesso and "Fluvial" in acesso:
            terrestre_part, _, fluvial_part = acesso.partition("|")
            records.append(_rec(section, "Forma de acesso: Terrestre", _parse_sim_nao_bracket(terrestre_part), terrestre_part))
            records.append(_rec(section, "Forma de acesso: Fluvial", _parse_sim_nao_bracket(fluvial_part), fluvial_part))

    r = find_row("Área do estabelecimento")
    if r:
        records.append(_rec(section, "Área do estabelecimento (ha)", r[1] if len(r) > 1 else None, str(r)))
        records.append(_rec(section, "Área do imóvel principal (ha)", r[3] if len(r) > 3 else None, str(r)))

    r = find_row("Endereço")
    if r:
        records.append(_rec(section, "Endereço", r[1] if len(r) > 1 else None, str(r)))

    r = find_row("Complemento")
    if r:
        records.append(_rec(section, "Complemento", r[1] if len(r) > 1 else None, str(r)))

    r = find_row("CEP")
    if r:
        records.append(_rec(section, "CEP", r[1] if len(r) > 1 else None, str(r)))
        records.append(_rec(section, "Grupo", r[3] if len(r) > 3 else None, str(r)))

    return records


def _extract_atividade_diversos(table):
    """Table 2 — Coordenadas/individual questions, Atividades produtivas, Diversos."""
    records = []
    rows = [_cells(r) for r in table.rows]
    section = "coordenadas"

    individual_questions = {
        "Exerce Cargo": "Exerce cargo, emprego ou função pública remunerada?",
        "Presta Serviço": "Presta serviço de interesse comunitário à comunidade rural?",
        "Já Foi Beneficiário": "Já foi beneficiário(a) do PNRA/regularização fundiária/crédito fundiário?",
        "proprietário, cotista ou acionista": "É proprietário, cotista ou acionista de sociedade empresária?",
        "proprietário (a) de outro imóvel": "É proprietário(a) de outro imóvel rural no território nacional?",
        "Aufere Renda Familiar": "Aufere renda familiar não agrária acima do limite?",
    }

    mode = None
    for r in rows:
        if not r or not r[0]:
            continue
        head = r[0]

        if head == "Coordenadas Geográficas (decimais)":
            mode = "coordenadas"
            continue
        if head == "Atividades produtivas da UFPA (Produção agrícola, não agrícolas e serviços)":
            mode = "atividade_produtiva"
            continue
        if head == "Diversos":
            mode = "diversos"
            continue

        if mode == "coordenadas":
            head_lower = head.lower()
            for key, label in individual_questions.items():
                if key.lower() in head_lower:
                    records.append(_rec("coordenadas", label, _parse_sim_nao_bracket(r[1]) if len(r) > 1 else None, str(r)))
                    break

        elif mode == "atividade_produtiva":
            continue  # activity rows are handled by _extract_atividades_produtivas_fixed

        elif mode == "diversos":
            if head in ("Meios de comunicação", "Diversos"):
                continue
            # Meios de comunicação column (label, S-cell, N-cell) then Saneamento rural column
            if len(r) >= 3:
                label1, s1, n1 = r[0], r[1], r[2]
                records.append(_rec("diversos.meios_comunicacao", label1, _parse_xs_n(s1, n1), str(r[:3])))
            if len(r) >= 6:
                label2, s2, n2 = r[3], r[4], r[5]
                records.append(_rec("diversos.saneamento_rural", label2, _parse_xs_n(s2, n2), str(r[3:6])))

    return records


def _extract_atividades_produtivas_fixed(table):
    """Table 2, activity rows — re-walked with a clean per-row index.

    Split out from _extract_atividade_diversos to keep each activity row's
    (Atividade, Produção anual, Unidade, Atividade principal) fields
    together as one record per row, which is what src/fill/ needs to loop
    over ("fill row -> click Adicionar -> repeat").
    """
    records = []
    rows = [_cells(r) for r in table.rows]
    in_block = False
    idx = 0
    for r in rows:
        if not r:
            continue
        if r[0] == "Atividades produtivas da UFPA (Produção agrícola, não agrícolas e serviços)":
            in_block = True
            continue
        if r[0] == "Diversos":
            in_block = False
            continue
        if not in_block:
            continue
        if r[0] == "Atividade":
            continue  # column header row
        atividade = r[0] if len(r) > 0 else ""
        # blank template rows only have the "Sim/Não" cell (activity name empty) -> skip
        if not atividade.strip():
            continue
        producao = r[1] if len(r) > 1 else None
        unidade = r[2] if len(r) > 2 else None
        principal_raw = r[3] if len(r) > 3 else ""
        principal = None
        m = re.search(r"\[\s*([xX]?)\s*\]\s*Sim\s*\[\s*([xX]?)\s*\]\s*N[ãa]o", principal_raw)
        if m:
            principal = bool(m.group(1)) and not bool(m.group(2))
        records.append({
            "source": "docx",
            "section": f"atividade_produtiva[{idx}]",
            "field": "atividade",
            "value": {
                "atividade": atividade,
                "producao_anual": producao,
                "unidade": unidade,
                "atividade_principal": principal,
            },
            "raw": str(r),
        })
        idx += 1
    return records


def _extract_patrimonio_block(table):
    """Table 3 — Patrimônio / Plantel / Área destinada a: (skips the two
    always-empty blocks, Recursos disponíveis and Participação em
    atividades coletivas — confirmed by Khalel, see docs/mapeamento.md).
    """
    records = []
    rows = [_cells(r) for r in table.rows]
    section = None
    for r in rows:
        if not r or not r[0]:
            continue
        head = r[0]

        if head == "Patrimônio":
            section = "patrimonio"
            continue
        if head == "Quantidade de cabeças no plantel":
            section = "plantel"
            continue
        if head == "Área destinada a:":
            section = "tipo_area"
            continue
        if head.startswith("Recursos disponíveis") or head.startswith("Participação em atividades coletivas"):
            section = None  # confirmed always-empty blocks, ignore
            continue
        if head in ("Descrição", "Recursos disponíveis", "Atividade Coletiva"):
            continue
        if section is None:
            continue

        descricao = r[0]
        quantidade = r[1] if len(r) > 1 else None
        unidade = r[2] if len(r) > 2 else None
        records.append({
            "source": "docx",
            "section": section,
            "field": descricao,
            "value": {"quantidade": quantidade, "unidade_docx": unidade},
            "raw": str(r),
        })
    return records


def _extract_integrantes(table, person_index):
    """Tables 5/6 — Integrantes (one table per person)."""
    rows = [_cells(r) for r in table.rows]
    section = f"integrantes[{person_index}]"
    records = []

    def find_row(*needles):
        for r in rows:
            if r and any(n in r[0] for n in needles):
                return r
        return None

    r = find_row("CPF")
    if r:
        records.append(_rec(section, "CPF", r[1] if len(r) > 1 else None, str(r)))
        records.append(_rec(section, "NIS/CAD ÚNICO", r[3] if len(r) > 3 else None, str(r)))

    r = find_row("Nome")
    if r and r[0].strip() == "Nome":
        records.append(_rec(section, "Nome", r[1] if len(r) > 1 else None, str(r)))

    r = find_row("Apelido")
    if r:
        records.append(_rec(section, "Apelido", r[1] if len(r) > 1 else None, str(r)))
        records.append(_rec(section, "Sexo", r[3] if len(r) > 3 else None, str(r)))

    r = find_row("Estado Civil")
    if r:
        records.append(_rec(section, "Estado Civil", r[1] if len(r) > 1 else None, str(r)))
        records.append(_rec(section, "Regime de Bens (docx)", r[3] if len(r) > 3 else None, str(r)))

    r = find_row("Data do Casamento")
    if r:
        records.append(_rec(section, "Data do Casamento/União", r[1] if len(r) > 1 else None, str(r)))
        records.append(_rec(section, "Data de nascimento", r[3] if len(r) > 3 else None, str(r)))

    r = find_row("Carteira de identidade")
    if r:
        records.append(_rec(section, "Carteira de identidade/órgão expedidor", r[1] if len(r) > 1 else None, str(r)))
        records.append(_rec(section, "Escolaridade", r[3] if len(r) > 3 else None, str(r)))

    r = find_row("Nome da mãe")
    if r:
        records.append(_rec(section, "Nome da mãe", r[1] if len(r) > 1 else None, str(r)))

    r = find_row("Nome do pai")
    if r:
        records.append(_rec(section, "Nome do pai", r[1] if len(r) > 1 else None, str(r)))

    r = find_row("Classificação da pessoa")
    if r:
        records.append(_rec(section, "Classificação da pessoa", r[1] if len(r) > 1 else None, str(r)))

    r = find_row("Telefones")
    if r:
        records.append(_rec(section, "Telefones", r[1] if len(r) > 1 else None, str(r)))
        email_cell = r[2] if len(r) > 2 else ""
        _, _, email = email_cell.partition(":")
        records.append(_rec(section, "E-mail", email.strip(), email_cell))

    r = find_row("Modo preferencial")
    if r:
        pref_cell = r[1] if len(r) > 1 else ""
        pref = None
        if re.search(r"E-?mail\s*\(\s*[xX]", pref_cell):
            pref = "E-mail"
        elif re.search(r"Correio\s*\(\s*[xX]", pref_cell):
            pref = "Correio"
        records.append(_rec(section, "Modo preferencial de comunicação", pref, pref_cell))

    r = find_row("Responsável pela UFPA")
    if r:
        # ['Responsável pela UFPA', 'Sim', 'x', 'Não', '', 'Parentesco', '']
        resp = None
        if len(r) >= 7:
            if r[2].strip().lower() == "x":
                resp = True
            elif r[4].strip().lower() == "x":
                resp = False
            records.append(_rec(section, "Responsável pela UFPA", resp, str(r)))
            records.append(_rec(section, "Parentesco", r[6] if len(r) > 6 else None, str(r)))

    return records


def _extract_indicadores(table):
    """Table 9 — Indicadores (feeds Diagnóstico T0, not the registration panels).

    Question/answer counts sometimes don't match (per docs/mapeamento.md,
    a known real-world data-quality issue) — that alignment/mismatch
    detection belongs to the schema layer, not here. This extractor just
    hands over the raw question list and raw answer list per
    eixo/indicador, unmodified.
    """
    records = []
    rows = [_cells(r) for r in table.rows]
    current_eixo = None
    for r in rows[2:]:  # skip "Indicadores" title row + header row
        if not r or len(r) < 3:
            continue
        eixo, indicador, questoes = r[0], r[1], r[2]
        respostas = r[3] if len(r) > 3 else ""
        if eixo:
            current_eixo = eixo
        questions = [q.strip() for q in questoes.split("\n") if q.strip()]
        answers = [a.strip() for a in respostas.split("\n") if a.strip()]
        records.append({
            "source": "docx",
            "section": "indicadores",
            "field": f"{current_eixo}:{indicador}",
            "value": {"eixo": current_eixo, "indicador": indicador, "questions": questions, "answers": answers},
            "raw": str(r),
        })
    return records


def extract_docx(path: str) -> list[dict]:
    """Extracts data from a registration .docx file (main source).

    Returns a flat list of raw records, each shaped as:
        {"source": "docx", "section": str, "field": str, "value": Any, "raw": str}

    `value` is parsed as far as extraction can go unambiguously (Sim/Não
    checkboxes -> bool, "Label: value" cells -> the value text). It does
    NOT resolve ambiguity, mismatches, or confidence — that's
    src/schema/'s job, working off these raw records.
    """
    doc = Document(path)
    tables = doc.tables
    if len(tables) < 10:
        raise ValueError(f"expected 10 tables in the registration .docx, found {len(tables)}")

    records = []
    records += _extract_entidade(tables[0])
    records += _extract_ufpa(tables[1])
    records += _extract_atividades_produtivas_fixed(tables[2])
    records += _extract_atividade_diversos(tables[2])  # coordenadas + diversos only (activity rows come from the fixed pass above)
    records += _extract_patrimonio_block(tables[3])
    records += _extract_integrantes(tables[5], person_index=1)
    records += _extract_integrantes(tables[6], person_index=2)
    records += _extract_indicadores(tables[9])

    return records


def find_pa_municipio(path: str) -> tuple[str | None, str | None]:
    """Pulls just Nome do PA / Município from the .docx -- the two values
    the WhatsApp "Ações Potenciais" template is matched against (see
    whatsapp_source.py:load_whatsapp_text()). Lighter than a full
    extract_docx() + schema build when that's all a caller needs up front
    (e.g. before deciding which WhatsApp template file to load)."""
    records = extract_docx(path)
    idx = {}
    for r in records:
        idx.setdefault(r["section"], {})[r["field"]] = r["value"]
    pa_nome = idx.get("ufpa", {}).get("Nome do PA")
    municipio = idx.get("entidade.local", {}).get("Município")
    return pa_nome, municipio
