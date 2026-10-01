"""
Pre-flight gate — stops the whole registration before the browser ever
opens if a "key" field is missing for an Integrante, instead of pausing
field-by-field 80 fields into a live session.

Confirmed by Khalel: **CPF, Nome, and Data de Nascimento** are the only
fields that block the whole run when missing — these aren't something a
human can resolve mid-fill the way a dropdown mismatch can; they mean the
source `.docx` itself is incomplete for that person. Everything else
(ambiguous checkboxes, dropdown values that don't match an option, etc.)
stays a per-field pause-and-continue via src/fill/review.py.
"""

BLOCKING_FIELDS = {"CPF", "Nome", "Data de Nascimento"}


class BlockingIssue:
    def __init__(self, panel, field, reason):
        self.panel = panel
        self.field = field
        self.reason = reason

    def __repr__(self):
        return f"{self.panel}/{self.field}: {self.reason}"


class MissingKeyDataError(RuntimeError):
    """Raised by src.fill.register_ufpa() before login when check_blocking()
    finds any issue — fix the source .docx and re-run, nothing was
    touched on the site."""

    def __init__(self, issues):
        self.issues = issues
        summary = "\n".join(f"  - {issue}" for issue in issues)
        super().__init__(
            f"{len(issues)} Integrante(s) missing key data (CPF/Nome/Data de "
            f"Nascimento) — fix the source .docx before registering:\n{summary}"
        )


def check_blocking(panels):
    """Returns every BlockingIssue found among the canonical panel fields
    (src.schema.build_schema()["panels"]). A non-empty result means: don't
    start the browser."""
    return [
        BlockingIssue(field.panel, field.field, field.review_reason)
        for field in panels
        if field.panel.startswith("integrantes") and field.field in BLOCKING_FIELDS and field.confidence == "low"
    ]
