"""
Low-confidence pause/resolve handling.

Per docs/mapeamento.md: the bot runs start to finish on its own and only
pauses on individual fields flagged `confidence: low` — never for
field-by-field approval of everything. src/fill/site.py calls
`review(field)` only for those flagged fields, in the order it's about to
fill them, and uses whatever value comes back (or skips the field
entirely if told to).
"""

import difflib
from dataclasses import dataclass
from typing import Any

from src.schema.rules import normalize

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


def _rank_options(wanted, options):
    """Options sorted by closeness to `wanted` (shared words first,
    character similarity as a tiebreaker)."""
    target = normalize(wanted)
    words = set(target.split())

    def score(opt):
        n = normalize(opt)
        overlap = len(words & set(n.split())) / max(len(words), 1)
        return overlap + 0.2 * difflib.SequenceMatcher(None, target, n).ratio()

    return sorted(options, key=score, reverse=True)


def pick_option(field_label, wanted, options, show=8):
    """Human picker for a dropdown whose wanted value matches no live
    option. Returns the chosen option text, or SKIP. Type a number to
    pick, any other text to filter the full list, or 'skip'."""
    print(f"\n--- NO MATCHING OPTION: {field_label} ---")
    print(f"  source value  : {wanted!r}  ({len(options)} options on the site)")
    shown = _rank_options(wanted, options)[:show]
    while True:
        for i, opt in enumerate(shown, 1):
            print(f"  {i:>2}. {opt}")
        answer = input("  number to pick, text to search the full list, or 'skip': ").strip()
        if answer.lower() == "skip":
            return SKIP
        if answer.isdigit() and 1 <= int(answer) <= len(shown):
            return shown[int(answer) - 1]
        if answer:
            found = [o for o in options if normalize(answer) in normalize(o)]
            if found:
                shown = found[:30]
            else:
                print("  (nothing matches that)")


@dataclass
class _AnswerView:
    """Lets the CLI review handler (written for CanonicalField) show an
    IndicadorAnswer."""
    panel: str
    field: str
    value: Any
    review_reason: str | None


def resolve_indicadores(answers, review_handler=cli_review, notify=print):
    """Same idea as resolve(), for Diagnóstico T0 answers: runs the handler
    on every low-confidence IndicadorAnswer and returns a new list where a
    reviewed answer is a clean 'Sim' / 'Não' / 'Não se Aplica' with high
    confidence. Skipped answers — and reviews that don't come out as one of
    the three options — are dropped, which leaves that question unanswered
    on the site."""
    from src.schema.rules import parse_choice

    resolved = []
    for a in answers:
        if a.confidence != "low":
            resolved.append(a)
            continue
        decision = review_handler(_AnswerView(f"diagnostico_t0 / {a.indicator}", a.question, a.value, a.review_reason))
        choice = None if decision.value is SKIP else parse_choice(decision.value)
        if choice is None:
            notify(f"  (left unanswered: {a.question[:70]})")
            continue
        a.value, a.confidence, a.review_reason = choice, "high", None
        resolved.append(a)
    return resolved
