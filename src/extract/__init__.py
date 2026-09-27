"""
Extraction layer — data source -> raw data.

Each extractor reads a specific source (registration .docx file, loose
WhatsApp text, etc.) and returns the same output format, regardless of
origin, for the schema/validation layer to consume.

See docs/mapeamento.md for the full mapping of known sources so far.
"""


def extract_docx(path: str) -> list[dict]:
    """Extracts data from a registration .docx file (main source).

    Should walk the document's tables (see docs/mapeamento.md for the list
    of ~10 tables and what each contains) and return a list of raw
    records, one per field/question found.

    TODO: implement with python-docx.
    """
    raise NotImplementedError


def extract_whatsapp_text(text: str) -> dict:
    """Extracts the 4 fixed paragraphs (Eixo Produtivo/Social/Ambiental/
    Fundiário) from loose text received via WhatsApp, used exclusively to
    fill the "Ações Potenciais" panel.

    TODO: implement parsing of the 4 paragraphs by axis header.
    """
    raise NotImplementedError
