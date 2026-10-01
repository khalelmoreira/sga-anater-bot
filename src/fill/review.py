"""
Low-confidence pause/resolve handling.

Per docs/mapeamento.md: the bot runs start to finish on its own and only
pauses on individual fields flagged `confidence: low` — never for
field-by-field approval of everything. src/fill/site.py calls
`review(field)` only for those flagged fields, in the order it's about to
fill them, and uses whatever value comes back (or skips the field
entirely if told to).
"""

from dataclasses import dataclass
from typing import Any

SKIP = object()  # sentinel: leave this field unfilled on the site


@dataclass
class ReviewDecision:
    value: Any  # the value to fill (possibly unchanged), or SKIP


def cli_review(field) -> ReviewDecision:
    """Default review handler: pauses the terminal and asks a human.

    `field` is a src.schema.model.CanonicalField. Typing nothing keeps
    the extracted value as-is (useful when the flag was precautionary,
    e.g. a dropdown match that just couldn't be confirmed statically);
    typing "skip" leaves the field unfilled.
    """
    print(f"\n--- LOW CONFIDENCE: {field.panel} / {field.field} ---")
    print(f"  current value : {field.value!r}")
    print(f"  reason        : {field.review_reason}")
    answer = input("  enter a corrected value, blank to keep as-is, or 'skip': ").strip()
    if answer.lower() == "skip":
        return ReviewDecision(SKIP)
    if answer == "":
        return ReviewDecision(field.value)
    return ReviewDecision(answer)


def resolve(fields, review_handler=cli_review):
    """Runs `review_handler` over every low-confidence field in `fields`,
    returning a new list where each field's value has been resolved (or
    marked for skipping) and confidence bumped to "high" (a human just
    confirmed it). High-confidence fields pass through untouched."""
    resolved = []
    for field in fields:
        if field.confidence != "low":
            resolved.append(field)
            continue
        decision = review_handler(field)
        if decision.value is SKIP:
            continue
        field.value = decision.value
        field.confidence = "high"
        field.review_reason = None
        resolved.append(field)
    return resolved
