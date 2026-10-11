"""
The one interface the pipeline uses to talk to a person.

Nothing under src/ should call print()/input() for anything a user needs to
see or answer: it goes through a UI. `CliUI` is the terminal behaviour the
scripts always had; a GUI implements the same methods (see docs/produto.md).

`review` has the same contract as the older `review_handler` callback
(`field -> ReviewDecision`), so `ui.review` can be passed anywhere a
`review_handler` is accepted.
"""

from typing import Protocol

from src.fill.review import ReviewDecision, cli_review, pick_option


class UI(Protocol):
    def progress(self, step: str, detail: str = "") -> None:
        """A step started / something worth telling the person."""

    def review(self, field) -> ReviewDecision:
        """Low-confidence field: return the value to use (or SKIP)."""

    def pick_option(self, field_label: str, wanted, options: list[str]):
        """Dropdown with no match: return the chosen option text, or SKIP."""

    def confirm_action(self, n: int, description: str, label: str | None, safe_value) -> str:
        """Per-action prompt. Return 'y' (allow), 'n' (deny), 'q' (abort the
        run) or 'a' (allow this and every remaining action)."""

    def confirm_save(self, kind: str, message: str) -> bool:
        """Before the final Salvar of 'registration' / 'diagnostico'.
        False = leave the page unsaved."""

    def report(self, summary: dict) -> None:
        """End-of-run summary (see src.pipeline.run_ufpa)."""


class CliUI:
    """Terminal implementation: the prompts the scripts always used."""

    def progress(self, step, detail=""):
        print(f"{step}{': ' + detail if detail else ''}")

    def review(self, field):
        return cli_review(field)

    def pick_option(self, field_label, wanted, options):
        return pick_option(field_label, wanted, options)

    def confirm_action(self, n, description, label, safe_value):
        prompt = f"\n[ACTION {n}] {description}"
        if label is not None:
            prompt += f"  (field={label!r}, value={safe_value!r})"
        return input(prompt + "\n  allow? [Y/n/q/a=allow remaining]: ").strip().lower()

    def confirm_save(self, kind, message):
        try:
            input(f"\n{message}\nPress Enter to Salvar (Ctrl+C to leave without saving): ")
        except KeyboardInterrupt:
            print()
            return False
        return True

    def report(self, summary):
        reg = summary.get("registration")
        if reg:
            print(f"\nRegistration: {reg['fields']} fields, {reg['reviewed']} reviewed by hand, "
                  f"{reg['options_picked']} dropdown picks, {reg['skipped']} skipped, "
                  f"{'SAVED' if reg['saved'] else 'NOT saved'}")
            for panel, n in reg["per_panel"].items():
                rows = reg["rows"].get(panel)
                print(f"  - {panel}: {n} fields" + (f" in {rows} row(s)" if rows else ""))
        diag = summary.get("diagnostico")
        if diag:
            _print_diagnostico(diag)
        if summary.get("log"):
            print(f"\nFull action log: {summary['log']}")


def _print_diagnostico(s):
    print(f"\nDiagnóstico opened as: {s['opened_as']}  |  answered now: {s['filled']}  |  already answered: {s['already_answered']}")
    for title, items in (
        ("Left blank (blank in the .docx / skipped)", s["left_blank"]),
        ("Site questions with no .docx answer", s["unmatched_site"]),
    ):
        if items:
            print(f"\n{title}: {len(items)}")
            for label, why in items:
                print(f"  - {label[:110]}  [{why}]")
    if s["discrepancies"]:
        print(f"\nExisting answers that differ from the .docx (NOT changed): {len(s['discrepancies'])}")
        for label, have, wanted in s["discrepancies"]:
            print(f"  - {label[:90]}: site={have}, docx={wanted}")
    if s["unused_answers"]:
        print(f"\n.docx rows that matched no site question (headers/extra options): {len(s['unused_answers'])}")
    print("\nSaved. Finalizar is yours to click." if s.get("saved") else "\nNot saved.")
