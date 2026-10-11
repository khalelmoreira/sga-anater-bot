"""SGA credentials in the OS credential store (Windows Credential Manager on
Windows) via `keyring`; falls back to SGA_USUARIO / SGA_SENHA from the
environment. The password is never sent back to the browser."""

import os

SERVICE = "sga-anater-bot"


def _kr():
    try:
        import keyring
        return keyring
    except Exception:
        return None


def load():
    """-> (usuario, senha) or None."""
    kr = _kr()
    if kr is not None:
        try:
            u, s = kr.get_password(SERVICE, "usuario"), kr.get_password(SERVICE, "senha")
            if u and s:
                return u, s
        except Exception:
            pass
    u, s = os.environ.get("SGA_USUARIO"), os.environ.get("SGA_SENHA")
    return (u, s) if u and s else None


def save(usuario, senha):
    kr = _kr()
    if kr is None:
        raise RuntimeError("keyring is not available")
    kr.set_password(SERVICE, "usuario", usuario)
    kr.set_password(SERVICE, "senha", senha)


def clear():
    kr = _kr()
    if kr is None:
        return
    for name in ("usuario", "senha"):
        try:
            kr.delete_password(SERVICE, name)
        except Exception:
            pass
