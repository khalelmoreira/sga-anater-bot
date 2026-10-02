"""
Per-action allow/deny gate + sanitized action log for live runs against
the real site (sga.anater.org).

Confirmed by Khalel before the first live test against the real site:
every state-changing Playwright call (click/fill/select/check) pauses
for an explicit allow/deny/quit, and every attempt — prompted, allowed,
denied, or errored — is written to a log file for review afterward,
including by Claude. Because of that last part, personal data (CPF,
names, birthdates, addresses, contact info...) is never written to the
log verbatim: see `sanitize()`.

Not meant to get in the way of the existing mock-page smoke tests or any
future automated test — pass `ActionGate.noop()` (or no gate at all,
every site.py function defaults to one) to run unattended with no
prompting and no log file.

Optional screenshots (`screenshot=True`, then `attach_page(page)` once
the Playwright page exists): one .png after every executed/errored
action, for runs with no visible browser window (headless, or a
devcontainer with broken GUI forwarding). Unlike the JSONL log,
screenshots are a picture of the real, filled form — NOT sanitized, and
not meant to be read by Claude. They're for a human to open locally;
logs/ (which holds both) is gitignored.
"""

import datetime
import json
import re
from pathlib import Path

DEFAULT_LOG_DIR = "logs"

# Field names that hold personally identifiable data, per the field-by-
# field tables in docs/mapeamento.md. Matched case-insensitively against
# the CanonicalField.field name (or the ad-hoc label passed to confirm()
# for non-field actions like login). When in doubt, add it here rather
# than ever letting a raw value reach the log.
SENSITIVE_FIELD_NAMES = {
    "cpf", "cpf (login)", "senha",
    "nome", "apelido", "nome da ufpa",
    "nome da mãe", "nome do pai",
    "nome do transmitente ou beneficiário", "cpf transmitente ou beneficiário",
    "nis/cad único", "e-mail", "email", "celular",
    "data de nascimento", "data da união", "data de ocupação originária",
    "data de ocupação atual",
    "endereço", "complemento", "cep", "nome da gleba",
}


def _is_sensitive(label):
    return bool(label) and label.strip().lower() in SENSITIVE_FIELD_NAMES


def sanitize(label, value):
    """Replaces a sensitive value with a shape-only placeholder (type +
    length); passes through anything not recognized as personal data
    (dropdown choices, booleans, quantities, confidence flags, etc)."""
    if value is None:
        return None
    if _is_sensitive(label):
        return f"<redacted {type(value).__name__} len={len(str(value))}>"
    return value


class AbortRun(Exception):
    """Raised when the human denies-and-quits a live run mid-way."""


class ActionGate:
    """Call confirm() before every state-changing Playwright action."""

    def __init__(self, log_path=None, *, auto_allow=False, screenshot=False):
        self.auto_allow = auto_allow
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        if log_path is None:
            log_path = f"{DEFAULT_LOG_DIR}/run-{stamp}.jsonl"
        self.path = Path(log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.page = None
        self._shot_count = 0
        self.screenshot_dir = Path(DEFAULT_LOG_DIR) / "screenshots" / stamp if screenshot else None
        if self.screenshot_dir is not None:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def noop(cls):
        """No prompting, no log file, no screenshots — for mock-page
        smoke tests / CI."""
        gate = cls.__new__(cls)
        gate.auto_allow = True
        gate.path = None
        gate.page = None
        gate.screenshot_dir = None
        gate._shot_count = 0
        return gate

    def attach_page(self, page):
        """Lets confirm() screenshot the live page after each action.
        Call once the Playwright `page` exists (the gate itself is
        normally created before the browser launches)."""
        self.page = page

    def _write(self, **record):
        if self.path is None:
            return
        record["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _save_screenshot(self, description, tag):
        if self.screenshot_dir is None or self.page is None:
            return None
        self._shot_count += 1
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", description).strip("-").lower()[:60]
        path = self.screenshot_dir / f"{self._shot_count:04d}-{tag}-{slug}.png"
        try:
            # The action that just ran may have kicked off a page navigation
            # or a JSF AJAX round-trip (mojarra.ab) that isn't done yet --
            # without this, screenshots routinely capture a half-loaded or
            # stale page. networkidle is best-effort (some actions trigger
            # no network activity at all, so this just times out and moves
            # on), plus a short fixed pause for the DOM/paint to catch up.
            try:
                self.page.wait_for_load_state("networkidle", timeout=2000)
            except Exception:
                pass
            self.page.wait_for_timeout(150)
            self.page.screenshot(path=str(path))
        except Exception:
            return None  # a screenshot failure must never break the actual run
        return str(path)

    def confirm(self, description, action_fn, *, label=None, value=None):
        """Prompts allow/deny/quit for `description`, logs the decision
        and outcome, and only then runs `action_fn()`.

        `label`/`value`, if given, are sanitized (see `sanitize()`) and
        logged alongside the description for traceability (e.g. which
        field this action was about to fill). Typing 'a' allows this and
        every remaining action for the rest of the run, without further
        prompting — still logged, just not interactively confirmed.
        """
        safe_value = sanitize(label, value) if label is not None else None
        self._write(event="prompt", description=description, field=label, value=safe_value)

        if self.auto_allow:
            answer = "y"
        else:
            prompt = f"\n[ACTION] {description}"
            if label is not None:
                prompt += f"  (field={label!r}, value={safe_value!r})"
            answer = input(prompt + "\n  allow? [Y/n/q/a=allow remaining]: ").strip().lower()

        if answer == "a":
            self.auto_allow = True
            self._write(event="allow_remaining_enabled", description=description)
            answer = "y"

        if answer == "q":
            self._write(event="aborted", description=description)
            raise AbortRun(description)
        if answer == "n":
            self._write(event="denied", description=description)
            return None

        try:
            result = action_fn()
        except Exception as e:
            shot = self._save_screenshot(description, "error")
            self._write(event="error", description=description, error=str(e), screenshot=shot)
            raise
        shot = self._save_screenshot(description, "ok")
        self._write(event="executed", description=description, screenshot=shot)
        return result
