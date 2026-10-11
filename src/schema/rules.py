"""
Shared confidence-rule helpers used across every panel builder in
src/schema/build.py.

`option_catalogs` note: several site fields are long dropdowns (Atividade
~300 options, Unidade de Medida ~130, Classificação da Pessoa ~29, etc.).
Their option lists aren't available statically in this repo — they only
exist on the live site. src/fill/ can scrape a dropdown's real <option>
list right before filling it and pass it in here as a catalog, upgrading
a field from low to high confidence just-in-time. Called without a
catalog (e.g. for a dry-run / review pass), dropdown-dependent fields
default to low confidence rather than guessing.
"""

import re
import unicodedata


def normalize(text: str | None) -> str:
    """Case/accent/punctuation-insensitive normalization for fuzzy dropdown matching."""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def dropdown_match(raw_value, catalog=None, known_transforms=None):
    """Resolves a raw source value against a site dropdown's option list.

    Returns (value, confidence, reason):
      - raw_value in known_transforms (exact, pre-confirmed mapping from
        docs/mapeamento.md) -> (mapped value, "high", None)
      - catalog given and a normalized match is found -> (matching option, "high", None)
      - catalog given and no match -> (raw_value, "low", "no dropdown option matches source value")
      - no catalog and no known transform -> (raw_value, "low", "dropdown option not confirmed against the live site")
    """
    if raw_value is None or str(raw_value).strip() == "":
        return raw_value, "low", "required dropdown value missing in source"

    known_transforms = known_transforms or {}
    if raw_value in known_transforms:
        return known_transforms[raw_value], "high", None

    if catalog:
        target = normalize(raw_value)
        for option in catalog:
            if normalize(option) == target:
                return option, "high", None
        return raw_value, "low", f"'{raw_value}' doesn't match any known dropdown option"

    return raw_value, "low", "dropdown option not confirmed against the live site (no catalog supplied)"


def bool_direct(value, field_label):
    """Direct-copy rule for a Sim/Não field already parsed to True/False/None."""
    if value is None:
        return None, "low", f"'{field_label}': neither Sim nor Não unambiguously marked in source"
    return value, "high", None


def required_text(value, field_label):
    """Direct-copy rule for a required text field."""
    if value is None or str(value).strip() == "":
        return value, "low", f"'{field_label}' is required but empty in source"
    return value, "high", None


def optional_text(value, field_label=None):
    return value, "high", None


# ------------------------------------------------------- Sim/Não answers

_CHOICE_RE = re.compile(r"\(\s*([xX]?)\s*\)\s*(N[ãa]o\s+se\s+aplica|N/?A|Sim|N[ãa]o)", re.IGNORECASE)


def read_choice(raw):
    """-> (choice, state). state is 'ok' (choice is 'Sim' / 'Não' / 'Não se
    Aplica'), 'blank' (no option marked) or 'ambiguous' (more than one
    marked, or unreadable text)."""
    if raw is None:
        return None, "blank"
    text = str(raw).strip()
    clean = {"sim": "Sim", "nao": "Não", "nao se aplica": "Não se Aplica", "na": "Não se Aplica"}
    if normalize(text) in clean:
        return clean[normalize(text)], "ok"
    found = _CHOICE_RE.findall(text)
    if not found:
        return None, "ambiguous" if text else "blank"
    marked = []
    for mark, label in found:
        if mark:
            n = normalize(label)
            marked.append("Não se Aplica" if n in ("na", "nao se aplica") else ("Sim" if n == "sim" else "Não"))
    if len(marked) == 1:
        return marked[0], "ok"
    return None, "blank" if not marked else "ambiguous"


def parse_choice(raw):
    """'( x ) Sim ( ) Não' -> 'Sim'; None when blank or ambiguous."""
    return read_choice(raw)[0]
