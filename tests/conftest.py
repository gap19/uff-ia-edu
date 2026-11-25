"""Fixtures compartilhadas para os testes."""

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Garantir que o projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def _db_session_lifecycle():
    """Abre a conexão DuckDB compartilhada na sessão e fecha ao final."""
    from backend.db import close_db, get_db

    get_db()
    yield
    close_db()


@pytest.fixture()
async def client():
    """Cliente ASGI assíncrono compartilhado pelos testes de API."""
    from backend.api.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
