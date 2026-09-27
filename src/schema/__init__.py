"""
Canonical schema + validation — the process's "brain".

Each extracted answer becomes a canonical record:

    {
        "axis": str,
        "indicator": str,
        "question": str,
        "value": str | None,
        "confidence": "high" | "low",
        "review_reason": str | None,
    }

`confidence: high` -> goes straight to automatic fill-in.
`confidence: low`  -> flagged for pause and human approval at just that
                       point (misaligned question/answer count, empty
                       field, ambiguous answer, text that didn't match
                       1:1 with the format the site expects).

See docs/mapeamento.md, section "Arquitetura proposta", for the full
rationale.
"""

from dataclasses import dataclass


@dataclass
class CanonicalRecord:
    axis: str
    indicator: str
    question: str
    value: str | None
    confidence: str  # "high" | "low"
    review_reason: str | None = None


def validate(records: list[dict]) -> list[CanonicalRecord]:
    """Applies confidence rules to the extracted raw records and returns
    the list of canonical records, already classified.

    TODO: implement confidence rules per field type (see
    docs/mapeamento.md, table "Campos do site sem origem clara" in the
    UFPA panel for the first known cases).
    """
    raise NotImplementedError
