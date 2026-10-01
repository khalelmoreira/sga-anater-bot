"""
Canonical schema builder — turns the raw extraction records (src/extract/)
into the canonical, per-panel field list the fill layer (src/fill/)
consumes, applying the confidence/review rules documented field-by-field
in docs/mapeamento.md.

Nothing here talks to the site. `option_catalogs` lets a caller (normally
src/fill/, right before it touches a dropdown) hand in that dropdown's
real, live option list so ambiguous values can be upgraded from low to
high confidence; without it, those fields are conservatively flagged low.
"""

from src.schema.model import CanonicalField, IndicadorAnswer
from src.schema.rules import bool_direct, dropdown_match, optional_text, required_text


def _index(records):
    """{section: {field: value}} lookup from a flat list of raw records."""
    idx = {}
    for r in records:
        idx.setdefault(r["section"], {})[r["field"]] = r["value"]
    return idx


def _rows(records, section_prefix):
    """All raw records whose section starts with `section_prefix` (for
    repeatable sections like 'integrantes[1]', 'atividade_produtiva[0]')."""
    return [r for r in records if r["section"].startswith(section_prefix)]


def _f(panel, field, site_id, value, confidence, reason=None, origin="docx", field_type="text"):
    return CanonicalField(panel, field, site_id, value, confidence, reason, origin, field_type)


# --------------------------------------------------------------------- UFPA

def build_ufpa(docx_idx, option_catalogs=None):
    option_catalogs = option_catalogs or {}
    ufpa = docx_idx.get("ufpa", {})
    coord = docx_idx.get("coordenadas", {})
    local = docx_idx.get("entidade.local", {})
    out = []

    # --- direct-copy text fields
    text_fields = [
        ("Nome da UFPA", "idNome", ufpa.get("Denominação da UFPA")),
        ("DAP/CAF", "idDap", ufpa.get("CAF")),
        ("Órgão Emissor", "idOrgaoEmissorDap", ufpa.get("Órgão Emissor")),
        ("Validade da DAP/CAF", "idValidadeDap", ufpa.get("Validade da CAF")),
        ("Área do estabelecimento (ha)", "idAreaEstabelecimento", ufpa.get("Área do estabelecimento (ha)")),
        ("Área do Imóvel Principal (ha)", "idAreaImovelPrincipal", ufpa.get("Área do imóvel principal (ha)")),
        ("Endereço", "idEndereco", ufpa.get("Endereço")),
        ("Complemento", "idComplemento", ufpa.get("Complemento")),
        ("CEP", "idCep", ufpa.get("CEP")),
        ("Nome da gleba", "label:Nome da gleba", ufpa.get("Nome da gleba")),
        ("Nome do Transmitente ou beneficiário", "idNomeTransmitenteBeneficiario", ufpa.get("Nome do Transmitente ou beneficiário")),
        ("CPF (Transmitente/beneficiário)", "idCpfTransmitenteBeneficiario", ufpa.get("CPF (Transmitente/beneficiário)")),
        ("Nome do PA", "idNomePa", ufpa.get("Nome do PA")),
    ]
    for label, site_id, value in text_fields:
        v, conf, reason = optional_text(value)
        out.append(_f("ufpa", label, site_id, v, conf, reason))

    # --- Sim/Não direct-copy fields
    bool_fields = [
        ("Área em terra pública?", "label:A área está inserida em terra pública?", ufpa.get("Área em terra pública?")),
        ("Área em projeto de assentamento – PA?", "idAreaProjetoAssentamentoPa", ufpa.get("Área em projeto de assentamento (PA)?")),
        ("Possui documentos da terra?", "idPossuiDocumentosTerra", ufpa.get("Possui documentos da terra?")),
        ("Documento da terra: CATP", "label:CATP", ufpa.get("Documento da terra: CATP")),
        ("Documento da terra: LO", "label:LO", ufpa.get("Documento da terra: LO")),
        ("Documento da terra: TD", "label:TD", ufpa.get("Documento da terra: TD")),
        ("Documento da terra: CRO", "label:CRO", ufpa.get("Documento da terra: CRO")),
        ("Documento da terra: CDRU", "label:CDRU", ufpa.get("Documento da terra: CDRU")),
        ("Documento da terra: CPCV", "label:CPCV", ufpa.get("Documento da terra: CPCV")),
        ("Área georreferenciada?", "label:A área é georreferenciada?", ufpa.get("Área georreferenciada?")),
        ("Possui CAR?", "idPossuiCar", ufpa.get("Possui CAR?")),
        ("É ocupante primitivo?", "idOcupantePrimitivo", ufpa.get("É ocupante primitivo?")),
        ("Ocupa o imóvel de forma mansa e pacífica?", "label:Ocupa o imóvel de forma mansa e pacífica?", ufpa.get("Ocupa o imóvel de forma mansa e pacífica?")),
        ("Forma de acesso: Terrestre", "idAcessoTerrestre", ufpa.get("Forma de acesso: Terrestre")),
        ("Forma de acesso: Fluvial", "idAcessoFluvial", ufpa.get("Forma de acesso: Fluvial")),
        ("Exerce cargo, emprego ou função pública remunerada?", "idExerceCargoPublico", coord.get("Exerce cargo, emprego ou função pública remunerada?")),
        ("Presta serviço de interesse comunitário à comunidade rural?", "label:Presta Serviço De Interesse Comunitário", coord.get("Presta serviço de interesse comunitário à comunidade rural?")),
        ("É proprietário, cotista ou acionista de sociedade empresária em atividade?", "label:É Proprietário, Cotista Ou Acionista", coord.get("É proprietário, cotista ou acionista de sociedade empresária?")),
        ("É proprietário(a) de outro imóvel rural dentro do território nacional?", "label:É Proprietário (A) De Outro Imóvel Rural", coord.get("É proprietário(a) de outro imóvel rural no território nacional?")),
        ("Aufere renda familiar não agrária acima do limite?", "label:Aufere Renda Familiar", coord.get("Aufere renda familiar não agrária acima do limite?")),
    ]
    for label, site_id, value in bool_fields:
        v, conf, reason = bool_direct(value, label)
        out.append(_f("ufpa", label, site_id, v, conf, reason, field_type="radio_bool"))

    # --- conditional: only meaningful/filled under a specific prior answer
    if ufpa.get("É ocupante primitivo?") is False:
        for label, site_id, key in [
            ("Data da Ocupação Originária", "idDataOcupacaoOriginaria", "Data da Ocupação Originária"),
            ("Data da Ocupação Atual", "idDataOcupacaoAtual", "Data da Ocupação Atual"),
        ]:
            v, conf, reason = required_text(ufpa.get(key), label)
            out.append(_f("ufpa", label, site_id, v, conf, reason))

    # --- nº do recibo do CAR: always low confidence (confirmed by Khalel)
    out.append(_f(
        "ufpa", "Nº do recibo do CAR", "idNumeroReciboCar", ufpa.get("Nº do recibo do CAR"),
        "low", "docx sometimes fills this field and sometimes doesn't — always needs human review, per Khalel",
    ))

    # --- fixed values, not read from the docx
    for label, site_id, value in [
        ("Está em RB?", "label:Está em RB?", True),
        ("Já foi beneficiário(a) do Programa Nacional de Reforma Agrária – PNRA...?", "label:Já Foi Beneficiário", True),
    ]:
        out.append(_f("ufpa", label, site_id, value, "high", None, origin="fixed", field_type="radio_bool"))

    for label, site_id, value in [
        ("Projeto", "idProjeto", "47"),
        ("Instrumento", "idInstrumento", "CTR.GTI.ASS.667.26"),
        ("Meta", "idInstrumentoMeta", "Cod.: 21100 - UCM - Visita de cadastro e diagnóstico da UFPA (P1) - 8/2026 a 10/2026"),
        ("Classificação da UFPA", "idClassificacaoUpf", "Assentados"),
    ]:
        out.append(_f("ufpa", label, site_id, value, "high", None, origin="fixed", field_type="select"))

    # Programa de Fomento uses radio inputs (idPbsm:0..3), not a <select> (see docs/mapeamento.md).
    # value is the exact option label text ("Nenhum."), confirmed from the saved HTML capture —
    # radio_text fields are clicked by matching this text, not the underlying option value (NENHUM)
    out.append(_f("ufpa", "Programa de Fomento", "idPbsm", "Nenhum.", "high", None, origin="fixed", field_type="radio_text"))

    # --- dropdowns needing live-catalog confirmation
    municipio, conf, reason = dropdown_match(local.get("Município"), option_catalogs.get("idMunicipio"))
    out.append(_f("ufpa", "Município", "idMunicipio", municipio, conf, reason, field_type="select"))

    comunidade, conf, reason = dropdown_match(ufpa.get("Grupo"), option_catalogs.get("idComunidade"))
    out.append(_f("ufpa", "Comunidade / Grupo", "idComunidade", comunidade, conf, reason, field_type="select"))

    # Estado (idUf) is pre-set at the site right before Cadastro, not from
    # the docx — not a fill target, deliberately not emitted here.
    # Bairro, Número, and the 3 geographic-coordinate fields are confirmed
    # never filled by the bot — deliberately not emitted here either.

    return out


# -------------------------------------------------------- Atividade Produtiva

def build_atividade_produtiva(records, option_catalogs=None):
    option_catalogs = option_catalogs or {}
    out = []
    atividades = [r for r in records if r["section"].startswith("atividade_produtiva[")]
    for r in atividades:
        panel = r["section"]
        row = r["value"]

        atividade, conf, reason = dropdown_match(row.get("atividade"), option_catalogs.get("idAtividadeProdutivaUpfAtividadeProdutivasAd"))
        out.append(_f(panel, "Atividade", "idAtividadeProdutivaUpfAtividadeProdutivasAd", atividade, conf, reason, field_type="select"))

        producao, conf, reason = required_text(row.get("producao_anual"), "Produção Anual")
        out.append(_f(panel, "Produção Anual", "idProducaoAnualUpfAtividadeProdutivasAd", producao, conf, reason))

        unidade_raw = row.get("unidade")
        if unidade_raw is not None and str(unidade_raw).strip().replace(",", ".").replace(".", "", 1).isdigit():
            # a bare number is never a real unit name (confirmed real example: "45") — never guess it
            out.append(_f(
                panel, "Unidade de Medida", "idUnidMedidaUpfAtividadeProdutivasAd", unidade_raw, "low",
                f"'{unidade_raw}' is a bare number, not a unit name — doesn't match any real option, don't guess",
                field_type="select",
            ))
        else:
            unidade, conf, reason = dropdown_match(unidade_raw, option_catalogs.get("idUnidMedidaUpfAtividadeProdutivasAd"))
            out.append(_f(panel, "Unidade de Medida", "idUnidMedidaUpfAtividadeProdutivasAd", unidade, conf, reason, field_type="select"))

        out.append(_f(panel, "Atividade Principal", "idCheckAtividadePrincipal", bool(row.get("atividade_principal")), "high", field_type="checkbox"))

    return out


# ------------------------------------------------------------------ Diversos

_MEIOS_MAP = {
    "Celular": "Celular?",
    "Rádio": "Rádio?",
    "Internet": "Internet?",
    "Televisão": "TV?",
}
_REDES_SOCIAIS_FANOUT = ["Facebook?", "Whatsapp?", "Youtube?"]

_SANEAMENTO_MAP = {
    "Água para consumo": "Água para consumo?",
    "Água para consumo tratada": "Água para consumo tratada?",
    "Água para produção": "Água para produção?",
    "Captação de água da chuva": "Captação de Água da chuva?",
    "Esgoto tratado": "Esgoto tratado?",
    "Fontes protegidas": "Fontes e nascentes protegidas?",
}


def build_diversos(docx_idx):
    out = []
    meios = docx_idx.get("diversos.meios_comunicacao", {})
    saneamento = docx_idx.get("diversos.saneamento_rural", {})

    for docx_label, site_label in _MEIOS_MAP.items():
        v, conf, reason = bool_direct(meios.get(docx_label), site_label)
        out.append(_f("diversos", site_label, f"label:{site_label}", v, conf, reason, field_type="radio_bool"))

    redes_value, conf, reason = bool_direct(meios.get("Redes Sociais"), "Redes Sociais")
    for site_label in _REDES_SOCIAIS_FANOUT:
        out.append(_f("diversos", site_label, f"label:{site_label}", redes_value, conf, reason, field_type="radio_bool"))

    for docx_label, site_label in _SANEAMENTO_MAP.items():
        v, conf, reason = bool_direct(saneamento.get(docx_label), site_label)
        out.append(_f("diversos", site_label, f"label:{site_label}", v, conf, reason, field_type="radio_bool"))

    # No source in the docx — confirmed by Khalel: always low, human decides
    out.append(_f(
        "diversos", "Utiliza agrotóxicos?", "label:Utiliza agrotóxicos?", None, "low",
        "no source in the .docx for this question — always needs human review, per Khalel",
        field_type="radio_bool",
    ))

    return out


# ---------------------------------------------- Patrimônio / Plantel / Tipo Área

_PATRIMONIO_MAP = {
    "Quantidade de implemento agrícolas": "01-Quantidade de implemento agrícolas",
    "Quantidade de máquinas agrícolas": "02-Quantidade de máquinas agrícolas",
    "Quantidade de veículos de passeio": "03-Quantidade de veículos de passeio",
    "Quantidade de construções rurais": "04-Quantidade de construções rurais",
    "Quantidade de motores elétricos (não pertencente às máquinas)": "05-Quantidade de motores elétricos",
    "Quantidade de conjuntos de irrigação": "06-Quantidade de conjuntos de irrigação",
    "Quantidade de animais de trabalho": "07-Quantidade de animais de trabalho",
    "Quantidade de veículos / maquinário de tração animal": "08-Quantidade de veículos / maquinário de tração animal",
}

_PLANTEL_MAP = {
    "Bovinos": "01-Bovinos",
    "Ovinos": "02-Ovinos",
    "Caprinos": "03-Caprinos",
    "Suínos": "04-Suínos",
    "Aves": "05-Aves",
    "Bubalinos": "06-Bubalinos",
    "Equinos, muares e asininos": "07-Equinos, muares e asininos",
    "Colmeias": "08-Colmeias",
    "Pequenos animais (outros)": "09-Pequenos animais (outros)",
}

# docx row -> (site option, fixed unidade). Confirmed by Khalel as
# provisional for the 4 that DO get a unidade — see docs/mapeamento.md.
_TIPO_AREA_MAP = {
    "Pastagens": ("01-Pastagens", "hectare"),
    "Culturas temporárias": ("02-Culturas Temporárias", "hectare"),
    "Culturas permanentes": ("03-Culturas permanentes", "hectare"),
    "Lâmina d’água": ("04-Lâmina d'água", "m²"),
    "Reserva Legal": ("06-Reserva Legal", "hectare"),
    # Extrativismo, Área de Preservação Permanente - APP, Outros: confirmed
    # ignore — no site option / never filled, dropped silently (not low confidence)
}


def _is_zero(quantidade):
    try:
        return float(str(quantidade).replace(",", ".")) == 0
    except (TypeError, ValueError):
        return False


def build_patrimonio_plantel(docx_idx, section_name, desc_map, site_ids, fixed_unidade_by_option):
    """Shared builder for Patrimônio and Plantel (identical "add row" shape)."""
    out = []
    section = docx_idx.get(section_name, {})
    idx = 0
    for docx_label, site_option in desc_map.items():
        row = section.get(docx_label)
        if row is None or _is_zero(row.get("quantidade")):
            continue  # confirmed: skip rows where Quantidade = 0, don't add them
        panel = f"{section_name}[{idx}]"
        idx += 1
        out.append(_f(panel, "Descrição", site_ids["descricao"], site_option, "high", field_type="select"))
        out.append(_f(panel, "Quantidade", site_ids["quantidade"], row.get("quantidade"), "high"))
        unidade = fixed_unidade_by_option(site_option)
        out.append(_f(panel, "Unidade Medida", site_ids["unidade"], unidade, "high", origin="fixed", field_type="select"))
    return out


def build_patrimonio(docx_idx):
    return build_patrimonio_plantel(
        docx_idx, "patrimonio", _PATRIMONIO_MAP,
        site_ids={"descricao": "idUpfPatrimonioAd", "quantidade": "idUpfPatrimonioQuantidadeAd", "unidade": "idUpfPatrimonioUnidMedidaAd"},
        fixed_unidade_by_option=lambda opt: "unidade animal" if opt.startswith("07-") else "unidade",
    )


def build_plantel(docx_idx):
    return build_patrimonio_plantel(
        docx_idx, "plantel", _PLANTEL_MAP,
        site_ids={"descricao": "idUpfPlantelDescricaoAd", "quantidade": "idUpfPlantelQuantidadeAd", "unidade": "idUpfPlantelUnidMedidaAd"},
        fixed_unidade_by_option=lambda opt: "cabeça",
    )


def build_tipo_area(docx_idx):
    out = []
    section = docx_idx.get("tipo_area", {})
    idx = 0
    for docx_label, (site_option, unidade) in _TIPO_AREA_MAP.items():
        row = section.get(docx_label)
        if row is None or _is_zero(row.get("quantidade")):
            continue
        panel = f"tipo_area[{idx}]"
        idx += 1
        out.append(_f(panel, "Descrição", "idUpfTipoAreaDescricaoAd", site_option, "high", field_type="select"))
        out.append(_f(panel, "Quantidade", "idUpfTipoAreaQuantidadeAd", row.get("quantidade"), "high"))
        out.append(_f(panel, "Unidade Medida", "idUpfTipoAreaUnidMedidaAd", unidade, "high", origin="fixed", field_type="select"))
    return out


# --------------------------------------------------------------- Integrantes

_ESTADO_CIVIL_UNIAO = {"Casado", "União Estável", "Casado(a)", "União estável"}


def build_integrantes(records, option_catalogs=None):
    option_catalogs = option_catalogs or {}
    out = []
    people = sorted({r["section"] for r in records if r["section"].startswith("integrantes[")})
    num_people = sum(
        1 for pnl in people
        if any(v not in (None, "") for v in {r["field"]: r["value"] for r in records if r["section"] == pnl}.values())
    )

    for panel in people:
        p = {r["field"]: r["value"] for r in records if r["section"] == panel}
        if not any(v not in (None, "") for v in p.values()):
            continue  # blank template person slot (e.g. table 6 when only 1 member exists)

        for label, site_id, key, required, field_type in [
            ("CPF", "idCpf", "CPF", True, "text"),
            ("NIS/CAD ÚNICO", "idNis", "NIS/CAD ÚNICO", False, "text"),
            ("Nome", "idNomeBeneficiarioPf", "Nome", True, "text"),
            ("Apelido", "idApelido", "Apelido", False, "text"),
            ("Sexo", "idSexo", "Sexo", True, "radio_text"),
            ("Data de Nascimento", "idDataNasc", "Data de nascimento", True, "text"),
            ("Nome da Mãe", "idNomeMae", "Nome da mãe", True, "text"),
            ("Nome do Pai", "idNomePai", "Nome do pai", False, "text"),
            ("Email", "idEmailBeneficiarioPf", "E-mail", False, "text"),
            ("Celular", "idCelular", "Telefones", False, "text"),
        ]:
            rule = required_text if required else optional_text
            v, conf, reason = rule(p.get(key), label)
            out.append(_f(panel, label, site_id, v, conf, reason, field_type=field_type))

        estado_civil_raw = p.get("Estado Civil")
        casado_like = bool(estado_civil_raw) and any(w in estado_civil_raw for w in ("Casado", "União", "Uniao"))
        # confirmed by Khalel: if marital status is Casado/União but the spouse isn't
        # registered as a separate Integrante in the .docx, leave Estado Civil (and
        # its dependents, Regime de Bens / Data da União) completely unfilled — don't
        # select Casado(a) with no partner on record
        spouse_missing = casado_like and num_people < 2

        if not spouse_missing:
            # confirmed by Khalel: Estado Civil always needs human review before
            # filling, even when the .docx value looks like a clean dropdown match
            # (e.g. "Casado" -> "Casado(a)") — never auto-resolved to high confidence
            out.append(_f(
                panel, "Estado Civil", "idEstadoCivilIntegrante", estado_civil_raw, "low",
                "always needs human review before filling, per Khalel — even a clean-looking match isn't auto-filled",
                field_type="select",
            ))

        classificacao, conf, reason = dropdown_match(
            p.get("Classificação da pessoa"), option_catalogs.get("idClassificacaoBeneficiario"),
            known_transforms={"Assentado": "Assentado"},
        )
        out.append(_f(panel, "Classificação da Pessoa", "idClassificacaoBeneficiario", classificacao, conf, reason, field_type="select"))

        modo_raw = p.get("Modo preferencial de comunicação")
        modo_labels = {"E-mail": "E-mail", "Correio": "Correio"}
        v, conf, reason = required_text(modo_labels.get(modo_raw), "Modo preferencial (Correio/E-mail)")
        out.append(_f(panel, "Modo preferencial (Correio/E-mail)", "idModoComunicacaoIntegrante", v, conf, reason, field_type="radio_text"))

        resp, conf, reason = bool_direct(p.get("Responsável pela UFPA"), "Resp. pela Família")
        out.append(_f(panel, "Resp. pela Família", "idRespFamilia", resp, conf, reason, field_type="radio_bool"))

        escolaridade_raw = p.get("Escolaridade")
        escolaridade, conf, reason = dropdown_match(escolaridade_raw, option_catalogs.get("codEscolaridade"))
        out.append(_f(panel, "Escolaridade", "codEscolaridade", escolaridade, conf, reason, field_type="select"))

        # confirmed fixed values, not read from the docx
        out.append(_f(panel, "Orientação sexual", "idOrientacaoSexual", "Heterossexual", "high", origin="fixed", field_type="select"))
        out.append(_f(panel, "Identidade de gênero", "idIdentidadeGenero", "Cysgênero", "high", origin="fixed", field_type="select"))

        if not spouse_missing and estado_civil_raw and "Casado" in estado_civil_raw:
            out.append(_f(panel, "Regime de Bens", "idRegimeBensIntegrante", "Comunhão parcial de bens", "high", origin="fixed", field_type="select"))

        if not spouse_missing and estado_civil_raw in _ESTADO_CIVIL_UNIAO:
            v, conf, reason = required_text(p.get("Data do Casamento/União"), "Data da União")
            out.append(_f(panel, "Data da União", "idDataCasamentoIntegrante", v, conf, reason))

        # confirmed by Khalel: always low, no source and no default
        out.append(_f(
            panel, "Parentesco", "idParentesco", p.get("Parentesco"), "low",
            "no source in the .docx and no fixed default — always needs human input, per Khalel",
        ))

    return out


# --------------------------------------------------------------- Ações Potenciais

def build_acoes_potenciais(whatsapp_data, docx_idx):
    if not whatsapp_data:
        return []
    out = []
    ufpa = docx_idx.get("ufpa", {})
    local = docx_idx.get("entidade.local", {})

    from src.schema.rules import normalize
    header_ok = (
        normalize(whatsapp_data.get("pa_nome")) == normalize(ufpa.get("Nome do PA"))
        and normalize(whatsapp_data.get("municipio")) == normalize(local.get("Município"))
    )

    site_ids = {
        "Eixo Produtivo": "idEixoProdutivo",
        "Eixo Social": "idEixoSocial",
        "Eixo Ambiental": "idEixoAmbiental",
        "Eixo Fundiário": "idEixoFundiario",
    }
    for axis, site_id in site_ids.items():
        paragraph = (whatsapp_data.get("eixos") or {}).get(axis)
        if not header_ok:
            out.append(_f(
                "acoes_potenciais", axis, site_id, paragraph, "low",
                "WhatsApp header (PA/município) doesn't match the family's own UFPA data — "
                "likely the wrong template, don't apply blindly",
                origin="whatsapp",
            ))
        else:
            v, conf, reason = required_text(paragraph, axis)
            out.append(_f("acoes_potenciais", axis, site_id, v, conf, reason, origin="whatsapp"))
    return out


# ------------------------------------------------------------------ Indicadores

def build_indicadores(records):
    """Diagnóstico T0 (Table 9). A mismatched question/answer count inside
    one eixo/indicador block means that block's per-question alignment
    can't be trusted — emit one low-confidence summary record for it
    rather than guessing a pairing. A clean 1:1 count is split into one
    IndicadorAnswer per question."""
    out = []
    for r in [x for x in records if x["section"] == "indicadores"]:
        v = r["value"]
        eixo, indicador = v["eixo"], v["indicador"]
        questions, answers = v["questions"], v["answers"]
        if len(questions) != len(answers):
            out.append(IndicadorAnswer(
                eixo, indicador, "(all questions in this indicador)", None, "low",
                f"question count ({len(questions)}) doesn't match answer count ({len(answers)}) "
                f"in the source .docx — misalignment, needs human review before filling",
            ))
            continue
        for q, a in zip(questions, answers):
            out.append(IndicadorAnswer(eixo, indicador, q, a, "high"))
    return out


# ---------------------------------------------------------------- Orchestrator

def build_schema(docx_records, whatsapp_data=None, option_catalogs=None):
    """Builds the full canonical schema from raw extraction records.

    Returns {"panels": [CanonicalField, ...], "indicadores": [IndicadorAnswer, ...]}
    """
    docx_idx = _index(docx_records)
    panels = []
    panels += build_ufpa(docx_idx, option_catalogs)
    panels += build_atividade_produtiva(docx_records, option_catalogs)
    panels += build_diversos(docx_idx)
    panels += build_patrimonio(docx_idx)
    panels += build_plantel(docx_idx)
    panels += build_tipo_area(docx_idx)
    panels += build_integrantes(docx_records, option_catalogs)
    panels += build_acoes_potenciais(whatsapp_data, docx_idx)
    indicadores = build_indicadores(docx_records)
    return {"panels": panels, "indicadores": indicadores}
