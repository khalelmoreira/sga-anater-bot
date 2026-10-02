"""
Extraction layer — data source -> raw data.

Each extractor reads a specific source (registration .docx file, loose
WhatsApp text, etc.) and returns the same output format, regardless of
origin, for the schema/validation layer to consume.

See docs/mapeamento.md for the full mapping of known sources so far.
"""

from src.extract.docx_source import extract_docx, find_pa_municipio
from src.extract.whatsapp_source import extract_whatsapp_text, load_whatsapp_text

__all__ = ["extract_docx", "find_pa_municipio", "extract_whatsapp_text", "load_whatsapp_text"]
