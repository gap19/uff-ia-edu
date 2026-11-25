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


@pytest.mark.anyio
async def test_generate_report_with_cross_section_and_appendix(client):
    resp = await client.get("/api/reports/generate", params={
        "secoes": ["cruzamentos", "tecnologia"],
        "series": ["9EF"],
        "disciplinas": ["LP"],
        "incluir_apendice": "true",
    })
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


def test_appendix_gap_has_effect_size_and_ci():
    from backend.reports.pdf_generator import _compute_gap_with_stats

    rows = _compute_gap_with_stats(["9EF"], ["LP"])
    assert len(rows) == 1
    r = rows[0]
    assert r["cohens_d"] is not None and r["cohens_d"] > 0
    assert r["ci_lower"] < r["gap"] < r["ci_upper"]
    # IC centrado na lacuna exibida
    assert (r["ci_lower"] + r["ci_upper"]) / 2 == pytest.approx(r["gap"])
    # Mesma lacuna da tabela pré-computada
    from backend.reports.pdf_generator import _compute_gap

    pre = next(g for g in _compute_gap(["9EF"], ["LP"]) if g["serie"] == "9EF" and g["disciplina"] == "LP")
    assert r["gap"] == pytest.approx(pre["gap"], abs=0.01)
