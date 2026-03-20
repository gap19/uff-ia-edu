"""Testes dos endpoints TIC Educação."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.app import app


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# -----------------------------------------------------------------------
# Indicadores
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_indicators(client):
    resp = await client.get("/api/tic/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    if data["data"]:  # pode estar vazio se TIC não processado
        assert "indicador" in data["data"][0]


@pytest.mark.anyio
async def test_get_indicator(client):
    resp = await client.get("/api/tic/indicator/A1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "A1"


# -----------------------------------------------------------------------
# Grupos temáticos
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_infrastructure(client):
    resp = await client.get("/api/tic/infrastructure")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


@pytest.mark.anyio
async def test_ai_indicators(client):
    resp = await client.get("/api/tic/ai")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


@pytest.mark.anyio
async def test_privacy(client):
    resp = await client.get("/api/tic/privacy")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


@pytest.mark.anyio
async def test_teacher_training(client):
    resp = await client.get("/api/tic/teacher-training")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


@pytest.mark.anyio
async def test_digital_literacy(client):
    resp = await client.get("/api/tic/digital-literacy")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
