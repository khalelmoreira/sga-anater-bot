"""
Fill-in layer — canonical data -> form on the SGA/ANATER site
(sga.anater.org), via Playwright.

The site is JSF (.xhtml, with viewstate) and the session expires after
~20 minutes, with no captcha. See docs/mapeamento.md, section "Fluxo de
telas do site SGA/ANATER", for the full step-by-step (login -> Consultar
UFPA -> Cadastrar UFPA with 9 accordion panels -> Diagnóstico T0).

General rule: for each field, look up the corresponding canonical record.
  - confidence == "high" -> fill in and keep going on its own.
  - confidence == "low" -> pause, flag the field, and wait for a human
    decision before continuing.
"""


def fill_registration(records: list) -> None:
    """Fills the UFPA Registration form (9 panels) from the canonical
    records, pausing only on low-confidence fields.

    TODO: implement with Playwright. Login and navigation to "Cadastrar
    UFPA" still need to be mapped field by field (see open points in
    docs/mapeamento.md).
    """
    raise NotImplementedError


def fill_diagnosis_t0(records: list) -> None:
    """Fills the ~140 Sim/Não/Não se aplica questions of the Diagnóstico
    T0, pausing only on low-confidence fields.

    TODO: implement with Playwright.
    """
    raise NotImplementedError
