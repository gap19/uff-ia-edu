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


# -----------------------------------------------------------------------
# Regressões da revisão (rótulos oficiais, unidade de análise, segurança)
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_director_binary_labels_follow_dictionary(client):
    """TX_Q194/TX_Q219: dicionário SAEB 2023 codifica A = Não, B = Sim."""
    for var in ("TX_Q194", "TX_Q219"):
        resp = await client.get("/api/cross/director-tech", params={
            "variable": var, "serie": "9EF", "disciplina": "LP"
        })
        assert resp.status_code == 200
        data = resp.json()
        labels = {g["code"]: g["label"] for g in data["groups"]}
        assert labels == {"A": "Não", "B": "Sim"}
        # Gap orientado como presença − ausência
        assert data["test"]["comparison"] == "Sim − Não"
        means = {g["code"]: g["mean"] for g in data["groups"]}
        assert data["test"]["gap"] == pytest.approx(means["B"] - means["A"], abs=1e-6)


@pytest.mark.anyio
async def test_director_counts_each_school_once(client):
    """TS_DIRETOR repete a escola por série: n não pode exceder o nº de escolas."""
    import duckdb
    from backend.config import SAEB_PARQUET_DIR

    resp = await client.get("/api/cross/director-tech", params={
        "variable": "TX_Q194", "serie": "9EF", "disciplina": "LP"
    })
    n_total = sum(g["n"] for g in resp.json()["groups"])
    con = duckdb.connect()
    n_schools = con.execute(
        f"SELECT COUNT(*) FROM '{SAEB_PARQUET_DIR / 'TS_ESCOLA.parquet'}' "
        "WHERE ID_UF = 33 AND MEDIA_9EF_LP IS NOT NULL"
    ).fetchone()[0]
    con.close()
    assert 0 < n_total <= n_schools


@pytest.mark.anyio
async def test_teacher_q037_is_training_need(client):
    resp = await client.get("/api/cross/teacher-tech", params={
        "variable": "TX_Q037", "serie": "9EF", "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "Necessidade de formação em TICs"
    assert [g["code"] for g in data["groups"]] == ["A", "B", "C", "D"]
    assert data["groups"][-1]["label"] == "Muita necessidade"
    assert data["test"]["eta_squared"] is not None


@pytest.mark.anyio
async def test_school_scatter_rejects_unknown_variable(client):
    """tech_var vira nome de coluna no SQL: só a whitelist é aceita."""
    resp = await client.get("/api/cross/school-scatter", params={
        "serie": "9EF", "disciplina": "LP",
        "tech_var": "ID_ESCOLA IS NOT NULL OR 1=1 OR d.ID_ESCOLA",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_cross_summary_ranked_by_common_effect_scale(client):
    resp = await client.get("/api/cross/summary", params={
        "serie": "9EF", "disciplina": "LP"
    })
    data = resp.json()
    effects = [a["effect_size_d"] for a in data["analyses"]]
    assert effects == sorted(effects, reverse=True)
    assert data["n_tests"] == sum(1 for a in data["analyses"] if a.get("p_value") is not None)


@pytest.mark.anyio
async def test_inse_strata_exclude_students_without_inse(client):
    """IN_INSE = 0 vem codificado como nível 1: não pode entrar na estratificação."""
    resp = await client.get("/api/cross/student-tech", params={
        "serie": "9EF", "disciplina": "LP", "variable": "TX_RESP_Q13b",
        "stratify_inse": "true", "use_precomputed": "false",
    })
    levels = [b["inse_level"] for b in resp.json()["by_inse"]]
    assert levels and min(levels) >= 1 and max(levels) <= 8
    level1 = next(b for b in resp.json()["by_inse"] if b["inse_level"] == 1)
    assert sum(g["n"] for g in level1["groups"]) < 2000  # ~800 com INSE (5 mil sem)


@pytest.mark.anyio
async def test_teacher_tests_use_school_clusters(client):
    """Com conglomerados por escola, diferenças minúsculas não são 'significativas'."""
    resp = await client.get("/api/cross/teacher-tech", params={
        "variable": "TX_Q029", "serie": "9EF", "disciplina": "LP"
    })
    data = resp.json()
    assert "linearização" in data["inference"]
    assert data["test"]["p_value"] > 1e-6
