"""Aplicação FastAPI principal do dashboard."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.config import PROJECT_ROOT
from backend.db import close_db, db_query, get_db  # noqa: F401  (get_db: compatibilidade)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    get_db()  # abre a conexão compartilhada na inicialização
    yield
    close_db()


app = FastAPI(
    title="Dashboard IA e Educação - UFF",
    description="API para análise de microdados SAEB 2023 e TIC Educação 2023",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — API pública somente leitura, sem cookies/credenciais
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Arquivos estáticos e templates
frontend_dir = PROJECT_ROOT / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(frontend_dir / "templates"))


def _asset_version() -> str:
    """Hash curto do conteúdo de CSS/JS, usado como ``?v=`` (cache busting).

    O Firebase Hosting guarda JS/CSS em cache por 1 h: sem a versão, um
    navegador poderia combinar JS antigo com JSONs novos após um deploy.
    """
    import hashlib

    digest = hashlib.sha256()
    for path in sorted((frontend_dir / "static").rglob("*")):
        if path.is_file() and path.suffix in (".js", ".css"):
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]

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
    return templates.TemplateResponse(
        request, "dashboard.html", {"asset_version": _asset_version()}
    )


@app.get("/api/health")
def health():
    """Health check."""
    tables = db_query("SHOW TABLES")
    return {
        "status": "ok",
        "tables": [t["name"] for t in tables],
        "table_count": len(tables),
    }
