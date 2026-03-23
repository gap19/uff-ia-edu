"""Aplicação FastAPI principal do dashboard."""

from contextlib import asynccontextmanager
from pathlib import Path

import duckdb
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.config import DUCKDB_PATH, PROJECT_ROOT

# Conexão DuckDB compartilhada (read-only)
_db: duckdb.DuckDBPyConnection | None = None


def get_db() -> duckdb.DuckDBPyConnection:
    """Retorna a conexão DuckDB compartilhada."""
    global _db
    if _db is None:
        _db = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    return _db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    global _db
    _db = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    yield
    if _db:
        _db.close()
        _db = None


app = FastAPI(
    title="Dashboard IA e Educação - UFF",
    description="API para análise de microdados SAEB 2023 e TIC Educação 2023",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Arquivos estáticos e templates
frontend_dir = PROJECT_ROOT / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(frontend_dir / "templates"))

# Registrar rotas
from backend.api.routes_saeb import router as saeb_router
from backend.api.routes_tic import router as tic_router
from backend.api.routes_cross import router as cross_router
from backend.api.routes_reports import router as reports_router

app.include_router(saeb_router, prefix="/api/saeb", tags=["SAEB"])
app.include_router(tic_router, prefix="/api/tic", tags=["TIC"])
app.include_router(cross_router, prefix="/api/cross", tags=["Cruzamentos"])
app.include_router(reports_router, prefix="/api/reports", tags=["Relatórios"])


@app.get("/")
async def index():
    """Redireciona para o dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
async def dashboard(request: Request):
    """Página principal do dashboard."""
    import logging
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception:
        logging.exception("Failed to render dashboard template")
        raise


@app.get("/api/health")
async def health():
    """Health check."""
    db = get_db()
    tables = db.execute("SHOW TABLES").fetchall()
    return {
        "status": "ok",
        "tables": [t[0] for t in tables],
        "table_count": len(tables),
    }


@app.get("/api/debug/template")
async def debug_template(request: Request):
    """Debug endpoint — testa renderização do template."""
    import traceback
    try:
        resp = templates.TemplateResponse("dashboard.html", {"request": request})
        return {"status": "ok", "body_length": len(resp.body)}
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
