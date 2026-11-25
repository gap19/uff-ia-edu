"""Testes dos endpoints SAEB."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.app import app


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# -----------------------------------------------------------------------
# Health check
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "tables" in data
    assert data["table_count"] > 0


# -----------------------------------------------------------------------
# Overview
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_overview(client):
    resp = await client.get("/api/saeb/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "alunos_por_serie" in data
    assert "escolas" in data
    assert isinstance(data["alunos_por_serie"], list)
    assert len(data["alunos_por_serie"]) > 0
    for item in data["alunos_por_serie"]:
        assert "serie" in item
        assert "total_alunos" in item


# -----------------------------------------------------------------------
# Proficiency
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_proficiency_no_filters(client):
    resp = await client.get("/api/saeb/proficiency")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert len(data["data"]) > 0


@pytest.mark.anyio
async def test_proficiency_with_filters(client):
    resp = await client.get("/api/saeb/proficiency", params={
        "serie": "9EF", "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) > 0
    for row in data["data"]:
        assert row["serie"] == "9EF"
        assert row["disciplina"] == "LP"
        assert "uf_sigla" in row


# -----------------------------------------------------------------------
# Proficiency Comparison
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_proficiency_comparison(client):
    resp = await client.get("/api/saeb/proficiency/comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert "rj" in data
    assert "sudeste" in data
    assert "brasil" in data
    assert len(data["rj"]) > 0


# -----------------------------------------------------------------------
# Proficiency Levels
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_proficiency_levels_rj(client):
    resp = await client.get("/api/saeb/proficiency/levels", params={"scope": "rj"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "rj"
    assert "data" in data


@pytest.mark.anyio
async def test_proficiency_levels_nacional(client):
    resp = await client.get("/api/saeb/proficiency/levels", params={"scope": "nacional"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "nacional"


# -----------------------------------------------------------------------
# Equity Gap
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_equity_gap(client):
    resp = await client.get("/api/saeb/equity/gap", params={
        "serie": "9EF", "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert len(data["data"]) > 0
    gap = data["data"][0]
    assert "media_publica" in gap
    assert "media_privada" in gap
    assert "gap" in gap
    # Gap deve ser positivo (privada > pública)
    assert gap["gap"] > 0


# -----------------------------------------------------------------------
# Equity INSE
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_equity_inse(client):
    resp = await client.get("/api/saeb/equity/inse")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert len(data["data"]) > 0
    for row in data["data"]:
        assert "nivel_inse" in row
        assert "media_proficiencia" in row


# -----------------------------------------------------------------------
# Teachers Formation
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_teachers_formation(client):
    resp = await client.get("/api/saeb/teachers/formation")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


# -----------------------------------------------------------------------
# Questionnaire
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_questionnaire_valid_dataset(client):
    resp = await client.get("/api/saeb/questionnaire/professor")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset"] == "professor"
    assert "data" in data


@pytest.mark.anyio
async def test_questionnaire_with_question(client):
    resp = await client.get("/api/saeb/questionnaire/professor", params={
        "questao": "TX_Q001"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) > 0
    for row in data["data"]:
        assert row["questao"] == "TX_Q001"


@pytest.mark.anyio
async def test_questionnaire_invalid_dataset(client):
    resp = await client.get("/api/saeb/questionnaire/invalid")
    assert resp.status_code == 404


# -----------------------------------------------------------------------
# Ranking
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_proficiency_ranking(client):
    resp = await client.get("/api/saeb/proficiency/ranking", params={
        "serie": "9EF", "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["serie"] == "9EF"
    assert data["disciplina"] == "LP"
    assert "rj_ranking" in data
    assert "total_ufs" in data
    assert data["total_ufs"] > 0
    assert data["rj_ranking"] is not None
    assert len(data["data"]) == data["total_ufs"]
    # Verificar que está ordenado decrescente
    medias = [r["media_proficiencia"] for r in data["data"]]
    assert medias == sorted(medias, reverse=True)


# -----------------------------------------------------------------------
# Regressões da revisão
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_overview_series_in_pedagogical_order(client):
    resp = await client.get("/api/saeb/overview")
    series = [r["serie"] for r in resp.json()["alunos_por_serie"]]
    assert series == ["5EF", "9EF", "34EM"]


@pytest.mark.anyio
async def test_proficiency_rede_filter(client):
    """rede é textual na API e inteiro (IN_PUBLICA) na tabela."""
    resp = await client.get("/api/saeb/proficiency", params={
        "serie": "9EF", "disciplina": "LP", "rede": "publica"
    })
    assert resp.status_code == 200
    assert resp.json()["data"]
    assert all(r["rede"] == 1 for r in resp.json()["data"])

    resp = await client.get("/api/saeb/proficiency/ranking", params={
        "serie": "9EF", "disciplina": "LP", "rede": "privada"
    })
    assert resp.status_code == 200
    assert all(r["rede"] == 0 for r in resp.json()["data"])

    resp = await client.get("/api/saeb/proficiency", params={"rede": "xyz"})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_comparison_weighted_mean_matches_kpi(client):
    """Combinar redes pela soma dos pesos reproduz a média ponderada do RJ."""
    comp = (await client.get("/api/saeb/proficiency/comparison")).json()
    rows = [r for r in comp["rj"] if r["serie"] == "9EF" and r["disciplina"] == "LP"]
    assert all("soma_pesos" in r for r in rows)
    weighted = sum(r["media_proficiencia"] * r["soma_pesos"] for r in rows) / sum(
        r["soma_pesos"] for r in rows
    )
    kpi = (await client.get("/api/saeb/overview")).json()["alunos_por_serie"]
    media_lp = next(r["media_lp"] for r in kpi if r["serie"] == "9EF")
    assert weighted == pytest.approx(media_lp, abs=0.01)


@pytest.mark.anyio
async def test_teachers_formation_one_row_per_school(client):
    import duckdb
    from backend.config import SAEB_PARQUET_DIR

    resp = await client.get("/api/saeb/teachers/formation")
    assert resp.status_code == 200
    data = resp.json()
    con = duckdb.connect()
    n_schools = con.execute(
        f"SELECT COUNT(*) FROM '{SAEB_PARQUET_DIR / 'TS_ESCOLA.parquet'}' WHERE ID_UF = 33"
    ).fetchone()[0]
    con.close()
    assert data["unit"] == "escola"
    assert len(data["data"]) == n_schools


@pytest.mark.anyio
async def test_filters_are_case_insensitive(client):
    upper = (await client.get("/api/saeb/equity/gap", params={"serie": "9EF", "disciplina": "LP"})).json()
    lower = (await client.get("/api/saeb/equity/gap", params={"serie": "9ef", "disciplina": "lp"})).json()
    assert upper["data"] and upper == lower
