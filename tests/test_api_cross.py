"""Testes dos endpoints de cruzamento tecnologia x desempenho."""

import pytest


# -----------------------------------------------------------------------
# Student Tech
# -----------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("serie", ["5EF", "9EF", "34EM"])
@pytest.mark.parametrize("disciplina", ["LP", "MT"])
async def test_student_tech_unified_contract(client, serie, disciplina):
    """R-02: use_precomputed=true e false retornam o mesmo contrato estatístico completo."""
    resp_true = await client.get("/api/cross/student-tech", params={
        "serie": serie, "disciplina": disciplina,
        "variable": "TX_RESP_Q13b", "use_precomputed": "true",
    })
    resp_false = await client.get("/api/cross/student-tech", params={
        "serie": serie, "disciplina": disciplina,
        "variable": "TX_RESP_Q13b", "use_precomputed": "false",
    })
    assert resp_true.status_code == 200
    assert resp_false.status_code == 200
    data = resp_true.json()
    assert data == resp_false.json()

    assert len(data["groups"]) == 2
    for g in data["groups"]:
        for key in ("code", "label", "mean", "se", "ci_low", "ci_high", "n", "weighted_pct"):
            assert key in g
        assert g["mean"] is not None and g["se"] is not None
        assert g["ci_low"] < g["mean"] < g["ci_high"]
        assert g["n"] > 0
    assert sum(g["weighted_pct"] for g in data["groups"]) == pytest.approx(100.0, abs=0.1)

    for key in ("gap", "cohens_d", "t_stat", "p_value", "df"):
        assert data["test"][key] is not None
    assert data["correlation"]["pearson_r"] is not None


@pytest.mark.anyio
async def test_student_tech_ordinal_contract_and_all_variables(client):
    """R-02: variáveis ordinais (Q12b) e chamada sem variable entregam schema completo."""
    resp = await client.get("/api/cross/student-tech", params={
        "serie": "9EF", "disciplina": "LP", "variable": "TX_RESP_Q12b",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["groups"]) == 4
    assert all(g["ci_low"] < g["mean"] < g["ci_high"] for g in data["groups"])
    assert data["test"]["type"] == "anova"
    assert data["test"]["f_stat"] > 0 and data["test"]["df"] > 0
    assert data["correlation"]["pearson_r"] > 0

    resp_all = await client.get("/api/cross/student-tech", params={
        "serie": "9EF", "disciplina": "LP",
    })
    assert resp_all.status_code == 200
    assert len(resp_all.json()["variables"]) == 4


@pytest.mark.anyio
async def test_student_tech_wifi_gap(client):
    """Validação: gap WiFi deve ser ~19 pts (9EF LP RJ)."""
    resp = await client.get("/api/cross/student-tech", params={
        "serie": "9EF", "disciplina": "LP",
        "variable": "TX_RESP_Q13b", "use_precomputed": "true"
    })
    assert resp.status_code == 200
    data = resp.json()
    groups = {g["code"]: g["mean"] for g in data["groups"]}
    assert "A" in groups and "B" in groups
    gap = groups["B"] - groups["A"]
    # Gap esperado: ~19 pts (tolerância de 5 pts)
    assert 14 < gap < 25, f"Gap WiFi inesperado: {gap:.1f} pts"


# -----------------------------------------------------------------------
# Director Tech
# -----------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("serie", ["5EF", "9EF", "34EM"])
async def test_director_tech(client, serie):
    resp = await client.get("/api/cross/director-tech", params={
        "variable": "TX_Q194", "serie": serie, "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["groups"]) == 2
    assert data["test"]["type"] == "t-test"


# -----------------------------------------------------------------------
# Teacher Tech
# -----------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("serie", ["5EF", "9EF", "34EM"])
async def test_teacher_tech(client, serie):
    resp = await client.get("/api/cross/teacher-tech", params={
        "variable": "TX_Q029", "serie": serie, "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["groups"]) == 4
    assert data["test"]["type"] == "anova"


# -----------------------------------------------------------------------
# Digital Index
# -----------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("serie", ["5EF", "9EF", "34EM"])
async def test_digital_index(client, serie):
    """R-02: /api/cross/digital-index unifica use_precomputed=true e false com IC/SE/correlação/ANOVA."""
    resp = await client.get("/api/cross/digital-index", params={
        "serie": serie, "disciplina": "LP", "use_precomputed": "true",
    })
    resp_live = await client.get("/api/cross/digital-index", params={
        "serie": serie, "disciplina": "LP", "use_precomputed": "false",
    })
    assert resp.status_code == 200
    assert resp_live.status_code == 200
    data = resp.json()
    assert data == resp_live.json()

    assert len(data["faixas"]) == 3
    assert len(data["by_level"]) == 9
    for lvl in data["by_level"]:
        for key in ("index", "mean", "se", "ci_low", "ci_high", "n"):
            assert key in lvl
        assert lvl["ci_low"] < lvl["mean"] < lvl["ci_high"]
    for faixa in data["faixas"]:
        assert "code" in faixa and "label" in faixa
        assert faixa["ci_low"] < faixa["mean"] < faixa["ci_high"]
    assert data["correlation"]["pearson_r"] > 0
    assert data["anova"]["f_stat"] > 0
    assert data["test"] == data["anova"]


@pytest.mark.anyio
async def test_digital_index_stratified(client):
    resp = await client.get("/api/cross/digital-index", params={
        "serie": "9EF", "disciplina": "LP", "stratify_inse": "true"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "by_inse" in data
    assert len(data["by_inse"]) > 0


@pytest.mark.anyio
async def test_digital_index_full_analysis_not_precomputed(client):
    """Cobertura de /api/cross/digital-index?use_precomputed=false (F-09)."""
    resp = await client.get("/api/cross/digital-index", params={
        "serie": "9EF", "disciplina": "LP",
        "stratify_inse": "true", "use_precomputed": "false",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["correlation"]["pearson_r"] > 0.1
    assert data["correlation"]["p_value"] < 0.01
    assert data["correlation"]["n"] > 50000
    assert len(data["faixas"]) == 3
    assert all(f["ci_lower"] < f["mean"] < f["ci_upper"] for f in data["faixas"])
    assert len(data["by_level"]) == 9
    assert len(data["by_inse"]) >= 7
    assert "linearização" in data["inference"]


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
    assert len(data["analyses"]) == 11
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
    assert len(data["data"]) > 0
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
    try:
        row = con.execute(
            f"SELECT COUNT(*) FROM '{SAEB_PARQUET_DIR / 'TS_ESCOLA.parquet'}' "
            "WHERE ID_UF = 33 AND MEDIA_9EF_LP IS NOT NULL"
        ).fetchone()
        n_schools = int(row[0]) if row is not None else 0
    finally:
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


# -----------------------------------------------------------------------
# Regressões F-04: validação (serie, disciplina), erros 400/500 e cache
# -----------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        ("/api/cross/student-tech", {"serie": "2EF", "disciplina": "LP", "variable": "TX_RESP_Q13b"}),
        ("/api/cross/student-tech", {"serie": "34EM", "disciplina": "CH", "variable": "TX_RESP_Q13b"}),
        ("/api/cross/student-tech", {"serie": "INVALID", "disciplina": "LP"}),
        ("/api/cross/student-tech", {"serie": "9EF", "disciplina": "LP", "variable": "INVALID"}),
        ("/api/cross/director-tech", {"serie": "2EF", "disciplina": "LP", "variable": "TX_Q194"}),
        ("/api/cross/director-tech", {"serie": "34EM", "disciplina": "CH", "variable": "TX_Q194"}),
        ("/api/cross/teacher-tech", {"serie": "2EF", "disciplina": "LP", "variable": "TX_Q029"}),
        ("/api/cross/teacher-tech", {"serie": "34EM", "disciplina": "CH", "variable": "TX_Q029"}),
        ("/api/cross/digital-index", {"serie": "2EF", "disciplina": "LP"}),
        ("/api/cross/digital-index", {"serie": "34EM", "disciplina": "CH"}),
        ("/api/cross/summary", {"serie": "INVALID", "disciplina": "LP"}),
        ("/api/cross/summary", {"serie": "2EF", "disciplina": "LP"}),
        ("/api/cross/summary", {"serie": "34EM", "disciplina": "CH"}),
        ("/api/cross/school-scatter", {"serie": "2EF", "disciplina": "LP"}),
        ("/api/cross/school-scatter", {"serie": "34EM", "disciplina": "CH"}),
    ],
)
async def test_cross_rejects_unsupported_params_with_400(client, endpoint, params):
    resp = await client.get(endpoint, params=params)
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert ".parquet" not in detail
    assert "Binder" not in detail


@pytest.mark.anyio
async def test_cross_500_does_not_leak_internal_details(client, monkeypatch):
    from backend.api import routes_cross

    def _boom(*args, **kwargs):
        raise RuntimeError("secret /data/processed/saeb/TS_ALUNO.parquet SQL error")

    monkeypatch.setattr(routes_cross, "get_cross_summary", _boom)
    resp = await client.get("/api/cross/summary", params={"serie": "9EF", "disciplina": "LP"})
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert ".parquet" not in detail
    assert "secret" not in detail


def test_cross_analysis_cache_returns_isolated_copies():
    """Mutação do dict retornado não pode corromper o cache (F-04)."""
    from backend.analysis.cross_analysis import get_director_tech_gap

    first = get_director_tech_gap("TX_Q194", "9EF", "LP")
    first["groups"].clear()
    first["label"] = "CORRUPTED"

    second = get_director_tech_gap("TX_Q194", "9EF", "LP")
    assert len(second["groups"]) == 2
    assert second["label"] != "CORRUPTED"
