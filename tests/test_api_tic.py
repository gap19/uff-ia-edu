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


@pytest.mark.anyio
async def test_tic_groups_match_official_tables(client):
    """Valores conferidos nas tabelas oficiais (tic_educacao_2023_escolas_tabela_proporcao_v1.0)."""
    from backend.analysis.tic import TIC_GROUPS

    resp = await client.get("/api/tic/infrastructure")
    data = resp.json()["data"]
    if not data:
        pytest.skip("TIC não processado")
    a1 = next(d for d in data if d["indicador"] == "A1")
    assert "ACESSO À INTERNET" in a1["titulo"]
    assert a1["sudeste"] == pytest.approx(97.9657)
    assert a1["brasil"] == pytest.approx(92.409)
    assert a1["me_sudeste"] is not None

    ai = (await client.get("/api/tic/ai")).json()["data"]
    ia = next(d for d in ai if d["label"] == "Sistemas de IA na gestão")
    assert ia["item"].startswith("Sistemas de Inteligência Artificial")
    assert ia["sudeste"] == pytest.approx(19.16)
    assert ia["brasil"] == pytest.approx(19.569)

    # Todo indicador do catálogo precisa existir nas tabelas
    for key, cfg in TIC_GROUPS.items():
        got = (await client.get(f"/api/tic/group/{key}")).json()
        assert got["count"] == len(cfg["indicators"]), key
        assert all(d["sudeste"] is not None and d["brasil"] is not None for d in got["data"])


@pytest.mark.anyio
async def test_tic_universe_footnote_only_when_needed(client):
    infra = (await client.get("/api/tic/infrastructure")).json()
    ai = (await client.get("/api/tic/ai")).json()
    if not infra.get("data"):
        pytest.skip("TIC não processado")
    assert "¹" in infra["note"]
    assert "¹" not in ai["note"]
