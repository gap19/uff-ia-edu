"""Testes dos endpoints de geração de relatórios PDF."""

import base64

import pytest

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


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


@pytest.mark.anyio
async def test_generate_report_lowercase_and_dedup_hits_cache(client):
    """Parâmetros em minúsculas/duplicados geram resultado idêntico aos canônicos (F-03)."""
    from backend.reports.pdf_generator import _generate_pdf_cached

    _generate_pdf_cached.cache_clear()
    upper = await client.get("/api/reports/generate", params={
        "secoes": ["proficiencia"],
        "series": ["9EF"],
        "disciplinas": ["LP"],
        "incluir_apendice": "false",
    })
    lower = await client.get("/api/reports/generate", params={
        "secoes": ["PROFICIENCIA", "proficiencia"],
        "series": ["9ef", "9EF"],
        "disciplinas": ["lp", "LP"],
        "incluir_apendice": "false",
    })
    assert upper.status_code == 200
    assert lower.status_code == 200
    assert lower.content == upper.content
    assert _generate_pdf_cached.cache_info().hits >= 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {"secoes": ["invalida"], "series": ["9EF"], "disciplinas": ["LP"]},
        {"secoes": ["proficiencia"], "series": ["2EF"], "disciplinas": ["LP"]},
        {"secoes": ["proficiencia"], "series": ["9EF"], "disciplinas": ["CH"]},
    ],
)
async def test_generate_report_rejects_invalid_params_with_400(client, params):
    for method in (client.get, client.post):
        resp = await method("/api/reports/generate", params=params)
        assert resp.status_code == 400


def test_build_report_data_all_sections_produce_valid_pngs_and_8_inse_colors():
    """Todas as 5 seções geram PNGs base64 válidos e INSE usa 8 cores distintas (F-03)."""
    from backend.reports.pdf_generator import (
        ALL_SECTIONS,
        PALETTE,
        _build_report_data,
    )

    assert len(PALETTE) == 8
    assert len(set(PALETTE)) == 8

    upper = _build_report_data(list(ALL_SECTIONS), ["9EF"], ["LP"], True)
    lower = _build_report_data(
        [s.upper() for s in ALL_SECTIONS], ["9ef"], ["lp"], True
    )

    assert upper["series"] == lower["series"] == ["9EF"]
    assert upper["disciplinas"] == lower["disciplinas"] == ["LP"]
    assert len(upper["apendice"]["gap"]) == len(lower["apendice"]["gap"]) == 1
    assert len(upper["apendice"]["inse"]) == 8
    assert upper["apendice"]["inse"] == lower["apendice"]["inse"]
    assert upper["secoes"]["etica"] is True

    expected_charts = {
        "proficiencia": ("chart_bars", "chart_ranking"),
        "equidade": ("chart_gap", "chart_inse"),
        "tecnologia": ("chart_infra", "chart_ai", "chart_privacy", "chart_training"),
        "cruzamentos": ("chart_wifi", "chart_digital_index", "chart_director", "chart_forest"),
    }
    for sec, keys in expected_charts.items():
        for key in keys:
            b64 = upper["secoes"][sec][key]
            assert isinstance(b64, str) and len(b64) > 100, f"{sec}.{key} vazio"
            raw = base64.b64decode(b64)
            assert raw[:8] == _PNG_MAGIC, f"{sec}.{key} não é PNG válido"


def test_chart_inse_uses_8_distinct_bar_colors(monkeypatch: pytest.MonkeyPatch):
    """Gráfico INSE deve renderizar 8 cores distintas para os 8 níveis socioeconômicos (F-03)."""
    from backend.reports import pdf_generator

    captured_colors: list[tuple[float, ...]] = []
    orig_fig_to_b64 = pdf_generator._fig_to_base64

    def _spy(fig):
        patches = fig.axes[0].patches
        captured_colors.extend(tuple(p.get_facecolor()) for p in patches)
        return orig_fig_to_b64(fig)

    monkeypatch.setattr(pdf_generator, "_fig_to_base64", _spy)
    b64 = pdf_generator.chart_inse(["9EF"], ["LP"])
    assert len(b64) > 100
    assert len(captured_colors) == 8
    assert len(set(captured_colors)) == 8


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


def test_executive_summary_filters_kpis_by_requested_series():
    """R-04c: Resumo Executivo filtra KPIs pelas séries solicitadas e preserva 3 séries em PDF_SERIES."""
    from backend.reports.pdf_generator import _build_report_data

    single = _build_report_data(["proficiencia"], ["9EF"], ["LP"], False)
    assert [r["serie"] for r in single["kpis"]] == ["9EF"]
    assert single["total_alunos"] == single["kpis"][0]["presentes_lp"]

    all_three = _build_report_data(["proficiencia"], ["9EF", "5EF", "34EM"], ["LP", "MT"], False)
    assert [r["serie"] for r in all_three["kpis"]] == ["5EF", "9EF", "34EM"]
    assert all_three["total_alunos"] == sum(r["presentes_lp"] for r in all_three["kpis"])
    assert all_three["total_alunos"] > single["total_alunos"]
