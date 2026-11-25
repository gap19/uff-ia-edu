"""Testes dos endpoints TIC Educação."""

import pytest


# -----------------------------------------------------------------------
# Indicadores
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_indicators(client):
    resp = await client.get("/api/tic/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0
    assert len(data["data"]) == data["count"]
    assert "indicador" in data["data"][0]
    assert "titulo" in data["data"][0]


@pytest.mark.anyio
async def test_get_indicator(client):
    resp = await client.get("/api/tic/indicator/A1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "A1"
    assert data["count"] > 0
    assert len(data["data"]) == data["count"]


@pytest.mark.anyio
async def test_get_indicator_case_insensitive(client):
    """Código do indicador deve ser normalizado com strip().upper() (F-04)."""
    upper = (await client.get("/api/tic/indicator/A1")).json()
    lower = (await client.get("/api/tic/indicator/a1")).json()
    assert lower["indicator"] == "A1"
    assert lower["count"] > 0
    assert lower == upper


# -----------------------------------------------------------------------
# Grupos temáticos
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_infrastructure(client):
    resp = await client.get("/api/tic/infrastructure")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0 and len(data["data"]) == data["count"]


@pytest.mark.anyio
async def test_ai_indicators(client):
    resp = await client.get("/api/tic/ai")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0 and len(data["data"]) == data["count"]


@pytest.mark.anyio
async def test_privacy(client):
    resp = await client.get("/api/tic/privacy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0 and len(data["data"]) == data["count"]


@pytest.mark.anyio
async def test_teacher_training(client):
    resp = await client.get("/api/tic/teacher-training")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0 and len(data["data"]) == data["count"]


@pytest.mark.anyio
async def test_digital_literacy(client):
    resp = await client.get("/api/tic/digital-literacy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0 and len(data["data"]) == data["count"]


@pytest.mark.anyio
async def test_invalid_group_returns_404(client):
    resp = await client.get("/api/tic/group/inexistente")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_tic_groups_match_official_tables(client):
    """Valores conferidos nas tabelas oficiais (tic_educacao_2023_escolas_tabela_proporcao_v1.0)."""
    from backend.analysis.tic import TIC_GROUPS

    resp = await client.get("/api/tic/infrastructure")
    data = resp.json()["data"]
    assert len(data) > 0
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
        assert len(got["data"]) == len(cfg["indicators"]), key
        assert all(d["sudeste"] is not None and d["brasil"] is not None for d in got["data"])


@pytest.mark.anyio
async def test_tic_universe_footnote_only_when_needed(client):
    infra = (await client.get("/api/tic/infrastructure")).json()
    ai = (await client.get("/api/tic/ai")).json()
    assert len(infra["data"]) > 0
    assert "¹" in infra["note"]
    assert "¹" not in ai["note"]
