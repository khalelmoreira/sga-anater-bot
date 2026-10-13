"""
The payment seam (docs/produto.md, "Payment and licensing").

The pipeline asks an `Entitlement` two things and knows nothing else about
billing:

- `check(inputs)` at the very start of a run, before any review or browser.
  Raise `NotEntitled` (with a message for the person) to stop the run.
- `consume(run_id, inputs, summary)` once a UFPA registration was actually
  saved on the site. Never called for dry runs, failed runs, or runs that
  don't save a registration. `run_id` is unique per run, so an
  implementation can make the charge idempotent.

The billing model isn't decided yet, so the only implementation is
`AlwaysAllow`. A real one (credits, licence key...) goes behind this same
interface and is passed to `run_ufpa(..., entitlement=...)`.
"""

from typing import Protocol


class NotEntitled(Exception):
    """The person can't run right now (no credits, expired licence...).
    The message is shown to them as is."""


class Entitlement(Protocol):
    def check(self, inputs) -> None: ...

    def consume(self, run_id: str, inputs, summary: dict) -> None: ...


class AlwaysAllow:
    def check(self, inputs):
        pass

    def consume(self, run_id, inputs, summary):
        pass
