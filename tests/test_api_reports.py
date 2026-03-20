"""Testes dos endpoints de geração de relatórios PDF."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.app import app


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_generate_report_get(client):
    """Testa geração de relatório PDF via GET."""
    resp = await client.get("/api/reports/generate", params={
        "secoes": ["proficiencia"],
        "series": ["9EF"],
        "disciplinas": ["LP"],
        "incluir_apendice": "false",
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 0
    # Verificar que começa com magic bytes PDF
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.anyio
async def test_generate_report_post(client):
    """Testa geração de relatório PDF via POST."""
    resp = await client.post("/api/reports/generate", params={
        "secoes": ["proficiencia", "equidade"],
        "series": ["9EF"],
        "disciplinas": ["LP"],
        "incluir_apendice": "false",
    })
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
