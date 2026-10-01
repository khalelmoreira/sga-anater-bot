# Ações Potenciais — WhatsApp text templates

One `.txt` file per PA + município, holding the standardized text pasted
from WhatsApp (see `docs/mapeamento.md` → "Ações Potenciais panel").
Confirmed by Khalel: this text is reused across every family registered in
that PA/município, not written custom per family — so it's kept here once
per template instead of being pasted fresh for every registration run.

File contents are the raw WhatsApp message, unmodified:

```
<PA NAME> - <MUNICÍPIO>

Eixo Produtivo
<paragraph>

Eixo Social
<paragraph>

Eixo Ambiental
<paragraph>

Eixo Fundiário
<paragraph>
```

File **names** are just for humans browsing this folder — matching is done
by `src/extract/whatsapp_source.py:load_whatsapp_text()` on the file's own
first line (`<PA NAME> - <MUNICÍPIO>`), normalized the same
accent/case/punctuation-insensitive way the schema layer cross-checks it.
A reasonable naming convention is the header line itself, e.g.:

```
PA MACIFE - BOM JESUS DO ARAGUAIA.txt
```

The `.txt` templates themselves are gitignored (`data/acoes_potenciais/*.txt`)
— same treatment as the real `.docx` files in `data/`, kept off git even
though Khalel confirmed this text isn't written per family. This README
and the folder structure stay tracked either way.
