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

A narrower set of fields (gate.py: CPF/Nome/Data de Nascimento on any
Integrante) is stricter than a regular pause — missing one of those means
the source .docx itself is incomplete, so gate.check_blocking() stops the
whole run before the browser even opens, rather than pausing mid-fill.

See docs/mapeamento.md, section "Arquitetura proposta", for the full
rationale, and each panel's section there for the field-by-field rules
implemented in build.py.
"""

from src.schema.build import build_schema
from src.schema.gate import BlockingIssue, MissingKeyDataError, check_blocking
from src.schema.model import CanonicalField, IndicadorAnswer

__all__ = [
    "build_schema", "CanonicalField", "IndicadorAnswer",
    "check_blocking", "BlockingIssue", "MissingKeyDataError",
]
