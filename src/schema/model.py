"""Canonical record shapes produced by the schema layer."""

from dataclasses import dataclass
from typing import Any


@dataclass
class CanonicalField:
    """One fillable field on one of the 8 registration panels."""

    panel: str  # e.g. "ufpa", "atividade_produtiva[0]", "integrantes[1]"
    field: str  # human label, e.g. "Nome da UFPA"
    site_field_id: str  # real id (formularioUpf:idX) or "label:<exact label text>" when the
    # site renders it with an auto-generated j_idtNNN id (see docs/mapeamento.md)
    value: Any
    confidence: str  # "high" | "low"
    review_reason: str | None = None
    origin: str = "docx"  # "docx" | "whatsapp" | "fixed" | "site_context"
    field_type: str = "text"  # "text" | "select" | "checkbox" | "radio_bool" | "radio_text"
    # radio_bool: value is True/False, clicked via the "Sim"/"Não" option label
    # radio_text: value is the exact option label text to click (e.g. "Masculino", "E-mail")


@dataclass
class IndicadorAnswer:
    """One question of the Diagnóstico T0 questionnaire (Table 9 / Indicadores).

    Separate from CanonicalField because this feeds Diagnóstico T0, not
    one of the 8 registration panels (see docs/mapeamento.md).
    """

    axis: str
    indicator: str
    question: str
    value: str | None
    confidence: str
    review_reason: str | None = None
