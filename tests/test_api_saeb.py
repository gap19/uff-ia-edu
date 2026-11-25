"""Testes dos endpoints SAEB."""

import pytest


# -----------------------------------------------------------------------
# Health check & Security headers
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_health(client):
    from backend.api.app import CONTENT_SECURITY_POLICY

    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "tables" in data
    assert data["table_count"] == 14
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert resp.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert "script-src 'self';" in resp.headers["content-security-policy"]


@pytest.mark.anyio
async def test_dashboard_security_headers(client):
    from backend.api.app import CONTENT_SECURITY_POLICY

    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert resp.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


@pytest.mark.anyio
async def test_cors_origins_configurable_and_restricted(client, monkeypatch):
    """CORS usa lista explícita de origens via CORS_ORIGINS em vez de wildcard '*' (R-05b)."""
    from backend.api import app as app_mod

    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert app_mod._get_cors_origins() == ["http://localhost:8000", "http://127.0.0.1:8000"]

    monkeypatch.setenv("CORS_ORIGINS", "https://ia-edu.uff.br, https://staging.uff.br ")
    assert app_mod._get_cors_origins() == ["https://ia-edu.uff.br", "https://staging.uff.br"]

    ok_resp = await client.get("/api/health", headers={"Origin": "http://localhost:8000"})
    assert ok_resp.headers.get("access-control-allow-origin") == "http://localhost:8000"

    blocked_resp = await client.get("/api/health", headers={"Origin": "https://untrusted.example.com"})
    assert "access-control-allow-origin" not in blocked_resp.headers


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
    assert len(data["alunos_por_serie"]) == 3
    for item in data["alunos_por_serie"]:
        assert "serie" in item
        assert "total_alunos" in item
        assert item["total_alunos"] > 0
    assert data["escolas"]["total_escolas"] == 4215


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
@pytest.mark.parametrize("serie", ["5EF", "9EF", "34EM"])
@pytest.mark.parametrize("disciplina", ["LP", "MT"])
async def test_proficiency_with_filters(client, serie, disciplina):
    resp = await client.get("/api/saeb/proficiency", params={
        "serie": serie, "disciplina": disciplina
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 27
    for row in data["data"]:
        assert row["serie"] == serie
        assert row["disciplina"] == disciplina
        assert "uf_sigla" in row and row["uf_sigla"] != "??"


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
    assert len(data["sudeste"]) > 0
    assert len(data["brasil"]) > 0


# -----------------------------------------------------------------------
# Proficiency Levels
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_proficiency_levels_rj(client):
    resp = await client.get("/api/saeb/proficiency/levels", params={"scope": "rj"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "rj"
    assert len(data["data"]) > 0
    row = data["data"][0]
    assert "nivel_0_lp5" in row
    # R-04b: níveis de Ensino Médio (34EM) expostos em LP (0..8) e MT (0..10)
    lp_34em = [row[f"nivel_{n}_lp34em"] for n in range(9)]
    mt_34em = [row[f"nivel_{n}_mt34em"] for n in range(11)]
    assert all(v is not None for v in lp_34em)
    assert all(v is not None for v in mt_34em)
    assert sum(lp_34em) == pytest.approx(100.0, abs=1.0)
    assert sum(mt_34em) == pytest.approx(100.0, abs=1.0)


@pytest.mark.anyio
async def test_proficiency_levels_nacional(client):
    resp = await client.get("/api/saeb/proficiency/levels", params={"scope": "nacional"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "nacional"
    assert len(data["data"]) == 1
    row = data["data"][0]
    assert row["n_escolas"] > 0
    assert sum(row[f"nivel_{n}_lp34em"] for n in range(9)) == pytest.approx(100.0, abs=1.0)
    assert sum(row[f"nivel_{n}_mt34em"] for n in range(11)) == pytest.approx(100.0, abs=1.0)


@pytest.mark.anyio
async def test_proficiency_levels_invalid_scope_returns_400(client):
    resp = await client.get("/api/saeb/proficiency/levels", params={"scope": "invalid"})
    assert resp.status_code == 400


# -----------------------------------------------------------------------
# Equity Gap
# -----------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("serie", ["5EF", "9EF", "34EM"])
@pytest.mark.parametrize("disciplina", ["LP", "MT"])
async def test_equity_gap(client, serie, disciplina):
    resp = await client.get("/api/saeb/equity/gap", params={
        "serie": serie, "disciplina": disciplina
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 1
    gap = data["data"][0]
    assert "media_publica" in gap
    assert "media_privada" in gap
    assert "gap" in gap
    # Gap deve ser positivo (privada > pública)
    assert gap["gap"] > 0


# -----------------------------------------------------------------------
# Equity INSE & Location
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_equity_inse(client):
    resp = await client.get("/api/saeb/equity/inse")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) > 0
    for row in data["data"]:
        assert "nivel_inse" in row
        assert "media_proficiencia" in row


@pytest.mark.anyio
async def test_equity_location(client):
    resp = await client.get("/api/saeb/equity/location")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 12
    assert {r["localizacao_label"] for r in data["data"]} == {"Urbana", "Rural"}
    assert {r["serie"] for r in data["data"]} == {"5EF", "9EF", "34EM"}


# -----------------------------------------------------------------------
# Teachers Formation
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_teachers_formation(client):
    resp = await client.get("/api/saeb/teachers/formation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit"] == "escola"
    assert len(data["data"]) == 4215


# -----------------------------------------------------------------------
# Questionnaire (inclui regressão F-02: excluir 5 colunas dissertativas abertas)
# -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_questionnaire_valid_dataset(client):
    resp = await client.get("/api/saeb/questionnaire/professor")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset"] == "professor"
    assert len(data["data"]) > 0
    assert len(data["questions"]) == 140
    q_codes = {q["code"] for q in data["questions"]}
    row_codes = {r["questao"] for r in data["data"]}
    assert "TX_Q148" not in q_codes
    assert "TX_Q148" not in row_codes


@pytest.mark.anyio
async def test_questionnaire_diretor_excludes_open_text_columns(client):
    resp = await client.get("/api/saeb/questionnaire/diretor")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["questions"]) == 205
    open_cols = {"TX_Q089", "TX_Q168", "TX_Q211", "TX_Q224"}
    q_codes = {q["code"] for q in data["questions"]}
    row_codes = {r["questao"] for r in data["data"]}
    assert q_codes.isdisjoint(open_cols)
    assert row_codes.isdisjoint(open_cols)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("dataset", "open_col"),
    [
        ("professor", "TX_Q148"),
        ("diretor", "TX_Q089"),
        ("diretor", "TX_Q168"),
        ("diretor", "TX_Q211"),
        ("diretor", "TX_Q224"),
    ],
)
async def test_questionnaire_open_column_query_returns_empty(client, dataset, open_col):
    resp = await client.get(f"/api/saeb/questionnaire/{dataset}", params={"questao": open_col})
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.anyio
async def test_questionnaire_with_question(client):
    resp = await client.get("/api/saeb/questionnaire/professor", params={
        "questao": "TX_Q001"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) > 0
    assert "question_text" in data
    for row in data["data"]:
        assert row["questao"] == "TX_Q001"
    # R-01: deduplicado por ID_PROFESSOR (~10.239 docentes únicos, nunca ~16.478 turmas)
    total_prof = sum(r["contagem"] for r in data["data"])
    assert 9000 < total_prof <= 10239

    resp_dir = await client.get("/api/saeb/questionnaire/diretor", params={
        "questao": "TX_Q194"
    })
    assert resp_dir.status_code == 200
    # R-01: deduplicado por ID_ESCOLA (~3.776 escolas únicas, nunca ~4.879 séries)
    total_dir = sum(r["contagem"] for r in resp_dir.json()["data"])
    assert 3000 < total_dir <= 3776


@pytest.mark.anyio
async def test_questionnaire_invalid_dataset(client):
    resp = await client.get("/api/saeb/questionnaire/invalid")
    assert resp.status_code == 404


# -----------------------------------------------------------------------
# Ranking
# -----------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("serie", ["5EF", "9EF", "34EM"])
async def test_proficiency_ranking(client, serie):
    resp = await client.get("/api/saeb/proficiency/ranking", params={
        "serie": serie, "disciplina": "LP"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["serie"] == serie
    assert data["disciplina"] == "LP"
    assert data["total_ufs"] == 27
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
    rows_pub = resp.json()["data"]
    assert len(rows_pub) == 27
    assert all(r["rede"] == 1 for r in rows_pub)

    resp = await client.get("/api/saeb/proficiency/ranking", params={
        "serie": "9EF", "disciplina": "LP", "rede": "privada"
    })
    assert resp.status_code == 200
    rows_priv = resp.json()["data"]
    assert len(rows_priv) == 27
    assert all(r["rede"] == 0 for r in rows_priv)

    resp = await client.get("/api/saeb/proficiency", params={"rede": "xyz"})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_comparison_weighted_mean_matches_kpi(client):
    """Combinar redes pela soma dos pesos reproduz a média ponderada do RJ."""
    comp = (await client.get("/api/saeb/proficiency/comparison")).json()
    rows = [r for r in comp["rj"] if r["serie"] == "9EF" and r["disciplina"] == "LP"]
    assert len(rows) == 2
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
    try:
        row = con.execute(
            f"SELECT COUNT(*) FROM '{SAEB_PARQUET_DIR / 'TS_ESCOLA.parquet'}' WHERE ID_UF = 33"
        ).fetchone()
        n_schools = int(row[0]) if row is not None else 0
    finally:
        con.close()
    assert data["unit"] == "escola"
    assert len(data["data"]) == n_schools


@pytest.mark.anyio
async def test_filters_are_case_insensitive(client):
    upper = (await client.get("/api/saeb/equity/gap", params={"serie": "9EF", "disciplina": "LP"})).json()
    lower = (await client.get("/api/saeb/equity/gap", params={"serie": "9ef", "disciplina": "lp"})).json()
    assert upper["data"] and upper == lower


@pytest.mark.anyio
async def test_saeb_500_does_not_leak_internal_details(client, monkeypatch):
    """Erros 500 não podem vazar SQL, caminhos ou mensagens internas (F-04)."""
    from backend.api import routes_saeb

    def _boom(*args, **kwargs):
        raise RuntimeError("secret /internal/path/saeb.duckdb SQL syntax")

    monkeypatch.setattr(routes_saeb, "_query", _boom)
    resp = await client.get("/api/saeb/overview")
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "/internal/path" not in detail
    assert "secret" not in detail


def test_teachers_formation_cache_returns_isolated_copy():
    """Mutação do retorno de teachers_formation não pode corromper o cache (F-04)."""
    from backend.api import routes_saeb

    first = routes_saeb.teachers_formation()
    assert len(first["data"]) == 4215
    first["data"].clear()

    second = routes_saeb.teachers_formation()
    assert len(second["data"]) == 4215
