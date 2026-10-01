"""
Login credentials — stored, not entered interactively (confirmed by
Khalel: automated login with stored credentials, not manual handoff).

Read from environment variables so nothing secret is ever committed:

    SGA_USUARIO   the SGA login (CPF/e-mail/username — exact field TBD,
                  see Site.login())
    SGA_SENHA     the SGA password

A `.env` file (untracked, see .gitignore) is the expected way to set
these locally; src/fill/ does not load one itself to avoid adding a
dependency decision here — wire up python-dotenv in the entrypoint
script if that's preferred.
"""

import os


class MissingCredentialsError(RuntimeError):
    pass


def load_credentials():
    usuario = os.environ.get("SGA_USUARIO")
    senha = os.environ.get("SGA_SENHA")
    if not usuario or not senha:
        raise MissingCredentialsError(
            "SGA_USUARIO and SGA_SENHA must be set in the environment — "
            "see src/fill/credentials.py"
        )
    return usuario, senha
