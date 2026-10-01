"""
Canonical schema + validation — the process's "brain".

Turns the raw records from src/extract/ into per-panel canonical fields
(CanonicalField) ready for src/fill/, plus the Diagnóstico T0 questionnaire
(IndicadorAnswer). Each gets a confidence:

  - "high" -> fills in automatically, no human involved.
  - "low"  -> src/fill/ pauses on that one field and waits for a human
              decision, then continues (misaligned question/answer count,
              empty required field, ambiguous Sim/Não, dropdown value that
              doesn't match any known option, etc).

See docs/mapeamento.md, section "Arquitetura proposta", for the full
rationale, and each panel's section there for the field-by-field rules
implemented in build.py.
"""

from src.schema.build import build_schema
from src.schema.model import CanonicalField, IndicadorAnswer

__all__ = ["build_schema", "CanonicalField", "IndicadorAnswer"]
