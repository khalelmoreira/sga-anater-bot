"""
Local web app: FastAPI endpoints + the single-page UI in static/index.html.

One run at a time. The pipeline (src.pipeline.run_ufpa) runs in a worker
thread with a WebUI; the page polls GET /api/state and answers prompts with
POST /api/answer. Bound to 127.0.0.1 only, and every /api call needs the
per-process token that is embedded in the served page, so another website
open in the browser can't drive it.
"""

import secrets
import tempfile
import threading
import traceback
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from src.fill.action_gate import AbortRun
from src.fill.credentials import MissingCredentialsError
from src.fill.diagnostico import UfpaAlreadyFinalized, UfpaNotFound, WrongUfpa
from src.pipeline import RunInputs, run_ufpa
from src.schema.gate import MissingKeyDataError
from src.schema.rules import normalize
from src.web import creds
from src.web.ui import WebUI

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 20 * 1024 * 1024

# Município options on the Consultar UFPA screen (docs/mapeamento.md)
MUNICIPIOS = ["Bom Jesus Do Araguaia", "Claudia", "Feliz Natal", "Nova Ubiratã",
              "Peixoto De Azevedo", "Querencia", "São Jose Do Xingu"]


def _error_payload(exc):
    """Plain-language error for the page."""
    if isinstance(exc, MissingKeyDataError):
        return {
            "kind": "preflight",
            "message": "O arquivo está incompleto. Corrija o .docx e tente de novo — nada foi aberto no navegador.",
            "issues": [f"{i.panel} / {i.field}: {i.reason}" for i in exc.issues],
        }
    if isinstance(exc, AbortRun):
        return {"kind": "cancelled", "message": "Execução cancelada."}
    if isinstance(exc, MissingCredentialsError):
        return {"kind": "credentials", "message": "Configure seu CPF e senha do SGA antes de começar."}
    if isinstance(exc, UfpaNotFound):
        return {"kind": "not_found", "message": f"Não encontrei essa UFPA no Diagnóstico T0: {exc}"}
    if isinstance(exc, UfpaAlreadyFinalized):
        return {"kind": "finalized", "message": f"Este diagnóstico já está finalizado: {exc}"}
    if isinstance(exc, WrongUfpa):
        return {"kind": "wrong_ufpa", "message": f"Abriu o diagnóstico de outra pessoa; nada foi preenchido. {exc}"}
    return {"kind": "unexpected", "message": f"Erro inesperado: {exc}"}


class Job:
    def __init__(self):
        self.ui = WebUI()
        self.status = "running"  # running | done | error
        self.error = None
        self.thread = None


def create_app(runner=run_ufpa, work_dir=None, credentials=creds):
    """`runner(inputs, ui)` and `credentials` (load/save/clear) are injectable
    so tests don't need a browser or the OS keyring."""
    token = secrets.token_urlsafe(24)
    work = Path(work_dir or tempfile.mkdtemp(prefix="sga-bot-"))
    (work / "uploads").mkdir(parents=True, exist_ok=True)
    state = {"job": None, "uploads": {}}
    lock = threading.Lock()

    app = FastAPI(title="SGA ANATER Bot", docs_url=None, redoc_url=None, openapi_url=None)

    def auth(x_token: str = Header(default="")):
        if not secrets.compare_digest(x_token, token):
            raise HTTPException(403, "bad token")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)

    @app.get("/api/config", dependencies=[Depends(auth)])
    def config():
        return {"municipios": MUNICIPIOS}

    @app.get("/api/state", dependencies=[Depends(auth)])
    def get_state():
        job = state["job"]
        out = {"credentials": credentials.load() is not None, "status": "idle",
               "events": [], "prompt": None, "summary": None, "error": None}
        if job:
            out.update(job.ui.snapshot(), status=job.status, error=job.error)
        return out

    @app.post("/api/upload", dependencies=[Depends(auth)])
    async def upload(request: Request, name: str = "registro.docx"):
        if not name.lower().endswith(".docx"):
            raise HTTPException(400, "Envie um arquivo .docx")
        data = await request.body()
        if not data or len(data) > MAX_UPLOAD:
            raise HTTPException(400, "Arquivo vazio ou grande demais")
        upload_id = uuid.uuid4().hex
        path = work / "uploads" / f"{upload_id}.docx"
        path.write_bytes(data)
        state["uploads"][upload_id] = path

        pa = municipio = None
        try:
            from src.extract import find_pa_municipio
            pa, found = find_pa_municipio(str(path))
            municipio = next((m for m in MUNICIPIOS if found and normalize(m) == normalize(found)), None)
        except Exception:
            pass  # not fatal: the person picks the município by hand
        return {"upload_id": upload_id, "pa": pa, "municipio": municipio}

    @app.post("/api/run", dependencies=[Depends(auth)])
    def start(body: dict):
        creds_pair = credentials.load()
        if not creds_pair:
            raise HTTPException(400, "Configure seu CPF e senha do SGA antes de começar.")
        path = state["uploads"].get(body.get("upload_id"))
        if not path:
            raise HTTPException(400, "Envie o arquivo .docx primeiro.")
        if body.get("municipio") not in MUNICIPIOS:
            raise HTTPException(400, "Escolha o município.")

        with lock:
            if state["job"] and state["job"].status == "running":
                raise HTTPException(409, "Já existe uma execução em andamento.")
            job = state["job"] = Job()

        inputs = RunInputs(
            docx_path=str(path), municipio=body["municipio"],
            whatsapp_text=(body.get("whatsapp_text") or "").strip() or None,
            dry_run=bool(body.get("dry_run")),
            auto_allow=True,  # no per-click prompts for end users; every action is still logged
            credentials=creds_pair,
        )

        def work_fn():
            try:
                runner(inputs, job.ui)
                job.status = "done"
            except Exception as e:  # shown to the person; details stay in the server console
                if not isinstance(e, (AbortRun, MissingKeyDataError, UfpaNotFound,
                                      UfpaAlreadyFinalized, WrongUfpa, MissingCredentialsError)):
                    traceback.print_exc()
                job.error = _error_payload(e)
                job.status = "error"

        job.thread = threading.Thread(target=work_fn, daemon=True)
        job.thread.start()
        return {"ok": True}

    @app.post("/api/answer", dependencies=[Depends(auth)])
    def answer(body: dict):
        job = state["job"]
        if not job or not job.ui.answer(body.get("id"), body.get("answer") or {}):
            raise HTTPException(409, "Nada para responder agora.")
        return {"ok": True}

    @app.post("/api/cancel", dependencies=[Depends(auth)])
    def cancel():
        job = state["job"]
        if job and job.status == "running":
            job.ui.cancel()
        return {"ok": True}

    @app.post("/api/reset", dependencies=[Depends(auth)])
    def reset():
        job = state["job"]
        if job and job.status != "running":
            state["job"] = None
        return {"ok": True}

    @app.post("/api/credentials", dependencies=[Depends(auth)])
    def set_credentials(body: dict):
        usuario = "".join(ch for ch in str(body.get("usuario", "")) if ch.isdigit())
        senha = str(body.get("senha", ""))
        if len(usuario) != 11 or not senha:
            raise HTTPException(400, "Informe o CPF (11 dígitos) e a senha.")
        try:
            credentials.save(usuario, senha)
        except Exception as e:
            raise HTTPException(500, f"Não consegui guardar as credenciais: {e}")
        return {"ok": True}

    @app.delete("/api/credentials", dependencies=[Depends(auth)])
    def delete_credentials():
        credentials.clear()
        return {"ok": True}

    return app
