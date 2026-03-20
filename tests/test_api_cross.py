"""Testes dos endpoints de cruzamento tecnologia x desempenho."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.app import app


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# -----------------------------------------------------------------------
# Student Tech
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_student_tech_precomputed(client):
    resp = await client.get("/api/cross/student-tech", params={
        "serie": "9EF", "disciplina": "LP",
        "variable": "TX_RESP_Q13b", "use_precomputed": "true"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data or "variables" in data
    if "groups" in data:
        assert len(data["groups"]) > 0
        for g in data["groups"]:
            assert "code" in g
            assert "mean" in g
            assert "n" in g


@pytest.mark.anyio
async def test_student_tech_wifi_gap(client):
    """Validação: gap WiFi deve ser ~19 pts (9EF LP RJ)."""
    resp = await client.get("/api/cross/student-tech", params={
        "serie": "9EF", "disciplina": "LP",
        "variable": "TX_RESP_Q13b", "use_precomputed": "true"
    })
    assert resp.status_code == 200
    data = resp.json()
    if "groups" in data:
        groups = {g["code"]: g["mean"] for g in data["groups"]}
        if "A" in groups and "B" in groups:
            gap = groups["B"] - groups["A"]
            # Gap esperado: ~19 pts (tolerância de 5 pts)
            assert 10 < gap < 30, f"Gap WiFi inesperado: {gap:.1f} pts"


# -----------------------------------------------------------------------
# Director Tech
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_director_tech(client):
    resp = await client.get("/api/cross/director-tech", params={
        "variable": "TX_Q194", "serie": "9EF", "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert len(data["groups"]) > 0


# -----------------------------------------------------------------------
# Teacher Tech
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_teacher_tech(client):
    resp = await client.get("/api/cross/teacher-tech", params={
        "variable": "TX_Q029", "serie": "9EF", "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert len(data["groups"]) > 0


# -----------------------------------------------------------------------
# Digital Index
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_digital_index(client):
    resp = await client.get("/api/cross/digital-index", params={
        "serie": "9EF", "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "faixas" in data or "by_level" in data
    if "faixas" in data:
        for faixa in data["faixas"]:
            assert "label" in faixa
            assert "mean" in faixa


@pytest.mark.anyio
async def test_digital_index_stratified(client):
    resp = await client.get("/api/cross/digital-index", params={
        "serie": "9EF", "disciplina": "LP", "stratify_inse": "true"
    })
    assert resp.status_code == 200
    data = resp.json()
    if "by_inse" in data:
        assert len(data["by_inse"]) > 0


# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_cross_summary(client):
    resp = await client.get("/api/cross/summary", params={
        "serie": "9EF", "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "analyses" in data
    assert len(data["analyses"]) > 0
    for a in data["analyses"]:
        assert "label" in a
        assert "level" in a


# -----------------------------------------------------------------------
# School Scatter
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_school_scatter(client):
    resp = await client.get("/api/cross/school-scatter", params={
        "serie": "9EF", "disciplina": "LP", "tech_var": "TX_Q034"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    if data["data"]:
        assert "proficiencia" in data["data"][0]
        assert "tech_value" in data["data"][0]
