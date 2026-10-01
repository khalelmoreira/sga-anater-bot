"""
Extractor for the loose WhatsApp text — the exclusive source for the
"Ações Potenciais" panel (4 textareas: Eixo Produtivo/Social/Ambiental/
Fundiário). See docs/mapeamento.md for the fixed message shape:

    <PA NAME> - <MUNICÍPIO>

    Eixo Produtivo
    <paragraph>

    Eixo Social
    <paragraph>

    Eixo Ambiental
    <paragraph>

    Eixo Fundiário
    <paragraph>

Confirmed by Khalel: this text is standardized per PA + município (reused
across every family registered there), not written custom per family.
"""

import re

_AXES = ["Eixo Produtivo", "Eixo Social", "Eixo Ambiental", "Eixo Fundiário"]


def extract_whatsapp_text(text: str) -> dict:
    """Extracts the header (PA/município) and the 4 axis paragraphs.

    Returns:
        {
            "pa_nome": str | None,
            "municipio": str | None,
            "eixos": {"Eixo Produtivo": str, "Eixo Social": str,
                      "Eixo Ambiental": str, "Eixo Fundiário": str},
        }

    Cross-checking the header against the family's actual PA/município
    (from the UFPA panel data) is a schema-layer concern, not extraction —
    this only parses what's on the page.
    """
    text = text.strip()
    lines = text.splitlines()

    pa_nome, municipio = None, None
    if lines and " - " in lines[0]:
        pa_nome, _, municipio = lines[0].partition(" - ")
        pa_nome, municipio = pa_nome.strip(), municipio.strip()

    header_pattern = "|".join(re.escape(h) for h in _AXES)
    parts = re.split(rf"^({header_pattern})\s*$", text, flags=re.MULTILINE)

    eixos = {axis: None for axis in _AXES}
    # re.split with a capturing group yields [pre, header1, body1, header2, body2, ...]
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if header in eixos:
            eixos[header] = body

    return {"pa_nome": pa_nome, "municipio": municipio, "eixos": eixos}
