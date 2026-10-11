"""
JSON (de)serialization for a built canonical schema.

Lets extraction + schema-build + low-confidence review run as a separate
step from the actual site fill (see scripts/extract_schema.py) instead of
always happening in memory inside a single register_ufpa() call -- so a
family's data only needs to be extracted and reviewed once, and a crashed
fill run can be retried from a saved schema without repeating either.

NOT sanitized -- a saved file holds the real, resolved field values
(CPF, names, etc.) for one family. Treat it exactly like a real .docx in
data/: local, gitignored (it naturally lands under logs/, already
ignored), not something to hand to Claude.
"""

import json
from dataclasses import asdict
from pathlib import Path

from src.schema.model import CanonicalField, IndicadorAnswer


def save_panels(panels, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in panels], f, ensure_ascii=False, indent=2)
    return str(path)


def load_panels(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [CanonicalField(**d) for d in data]


def indicadores_path(panels_path):
    """Where the Diagnóstico T0 answers live next to a saved panels file:
    logs/schema-x.json -> logs/schema-x.diagnostico.json (the panels file
    keeps its original format so run_registration --schema is unaffected)."""
    p = Path(panels_path)
    return str(p.with_name(p.stem + ".diagnostico.json"))


def save_indicadores(answers, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(a) for a in answers], f, ensure_ascii=False, indent=2)
    return str(path)


def load_indicadores(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [IndicadorAnswer(**d) for d in data]
