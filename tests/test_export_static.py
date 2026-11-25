"""Testes do contrato de exportação estática (scripts/export_static.py <-> frontend)."""

import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_STATIC_PY = PROJECT_ROOT / "scripts" / "export_static.py"
APP_JS = PROJECT_ROOT / "frontend" / "static" / "js" / "app.js"
PAGES_JS = PROJECT_ROOT / "frontend" / "static" / "js" / "pages.js"
DASHBOARD_HTML = PROJECT_ROOT / "frontend" / "templates" / "dashboard.html"


def _load_export_static() -> Any:
    """Carrega scripts/export_static.py sem criar colisão de namespace no mypy."""
    spec = importlib.util.spec_from_file_location("export_static_mod", EXPORT_STATIC_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


export_static: Any = _load_export_static()


def _run_node_json(script: str) -> Any:
    """Executa um script Node.js e retorna o JSON impresso em stdout."""
    proc = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, f"Node falhou:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    return json.loads(proc.stdout)


def _eval_js_static_data_urls(cases: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """Executa a função real staticDataURL() de app.js via Node.js."""
    payload = json.dumps(cases)
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync({json.dumps(str(APP_JS))}, 'utf8');
const ctx = vm.createContext({{
    window: {{ STATIC_DATA: true, location: {{ origin: 'http://localhost' }} }},
    document: {{ addEventListener: () => {{}} }},
    localStorage: {{ getItem: () => null, setItem: () => {{}} }},
    console,
    URL,
    AbortController,
    setTimeout,
    clearTimeout,
}});
vm.runInContext(code, ctx);
const cases = {payload};
const results = cases.map(([path, params]) => ctx.staticDataURL(path, params));
process.stdout.write(JSON.stringify(results));
"""
    result = _run_node_json(node_script)
    assert isinstance(result, list)
    return [str(x) for x in result]


def _extract_select_values(html: str, select_id: str) -> list[str]:
    """Extrai os valores de <option value=...> de um <select id=...>."""
    match = re.search(
        rf'<select[^>]*id="{re.escape(select_id)}"[^>]*>(.*?)</select>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None, f"Select #{select_id} não encontrado em dashboard.html"
    return [v for v in re.findall(r'<option[^>]*value="([^"]*)"', match.group(1)) if v]


def test_slug_path_matches_app_js_static_data_url() -> None:
    """Garante paridade 1:1 entre slug_path() em Python e staticDataURL() real em app.js."""
    cases: list[tuple[str, dict[str, Any]]] = [
        *export_static.enumerate_calls(),
        ("/saeb/questionnaire/professor", {}),
        ("/saeb/questionnaire/professor", {"questao": "TX_Q001"}),
        ("/saeb/questionnaire/diretor", {"questao": "TX_Q194"}),
        ("/cross/student-tech", {"variable": "TX_RESP_Q13b", "serie": "9EF", "disciplina": "LP"}),
        ("/test/order", {"z": "last", "a": "first", "m": "mid"}),
        ("/test/booleans", {"use_precomputed": True, "stratify_inse": False}),
        ("/test/empty-values", {"keep": "ok", "empty": "", "none_val": None}),
    ]

    js_urls = _eval_js_static_data_urls(cases)
    assert len(js_urls) == len(cases)

    for (path, params), js_url in zip(cases, js_urls, strict=True):
        py_url = "/" + export_static.slug_path(path, params)
        assert py_url == js_url, f"Divergência para ({path!r}, {params!r}): py={py_url!r} != js={js_url!r}"


def test_enumerate_calls_has_unique_slugs() -> None:
    """Todas as combinações de enumerate_calls() devem gerar caminhos de arquivo únicos."""
    calls = export_static.enumerate_calls()
    assert len(calls) > 0
    slugs = [export_static.slug_path(path, params) for path, params in calls]
    assert len(slugs) == len(set(slugs)), "Colisão de nomes de arquivos JSON em enumerate_calls()"


def test_dashboard_filter_options_covered_by_export_static() -> None:
    """Todas as opções de série, disciplina e dataset de dashboard.html estão cobertas."""
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    series_opts = _extract_select_values(html, "filter-serie")
    disc_opts = _extract_select_values(html, "filter-disciplina")
    dataset_opts = _extract_select_values(html, "quest-dataset")

    assert set(series_opts) <= set(export_static.SERIES)
    assert set(disc_opts) <= set(export_static.DISCIPLINAS)
    assert set(dataset_opts) <= set(export_static.QUESTIONNAIRE_DATASETS)


def test_every_fetch_api_pattern_in_pages_js_is_covered() -> None:
    """Garante que todo endpoint chamado via fetchAPI(...) em pages.js é exportado."""
    pages_src = PAGES_JS.read_text(encoding="utf-8")
    raw_paths = re.findall(r"fetchAPI\(\s*['\"`]([^'\"`]+)['\"`]", pages_src)
    assert len(raw_paths) >= 20, "Esperava encontrar todas as chamadas fetchAPI em pages.js"

    calls = export_static.enumerate_calls()
    exported_paths = {path for path, _ in calls}
    exported_slugs = {export_static.slug_path(path, params) for path, params in calls}

    for path in raw_paths:
        if path == "/saeb/questionnaire/${dataset}":
            assert len(export_static.QUESTIONNAIRE_DATASETS) == 5
        elif path.startswith("/saeb/questionnaire/"):
            dataset = path.removeprefix("/saeb/questionnaire/")
            assert dataset in export_static.QUESTIONNAIRE_DATASETS
        else:
            assert path in exported_paths, f"Endpoint {path!r} usado em pages.js não está em enumerate_calls()"

    # Verificar parâmetros exatos de cada chamada parametrizada em pages.js
    assert export_static.slug_path("/saeb/proficiency/levels", {"scope": "rj"}) in exported_slugs
    assert export_static.slug_path("/saeb/equity/gap", {}) in exported_slugs

    for serie in export_static.SERIES:
        for disc in export_static.DISCIPLINAS:
            base = {"serie": serie, "disciplina": disc}
            expected = [
                ("/saeb/proficiency", base),
                ("/saeb/proficiency/ranking", base),
                ("/saeb/equity/gap", base),
                ("/cross/summary", base),
                ("/cross/digital-index", {**base, "use_precomputed": True}),
                ("/cross/digital-index", {**base, "stratify_inse": True}),
                ("/cross/student-tech", {**base, "variable": "TX_RESP_Q12b", "use_precomputed": True}),
                ("/cross/student-tech", {**base, "variable": "TX_RESP_Q13b", "use_precomputed": True}),
                ("/cross/student-tech", {**base, "variable": "TX_RESP_Q12g", "use_precomputed": True}),
                (
                    "/cross/student-tech",
                    {
                        **base,
                        "variable": "TX_RESP_Q13b",
                        "stratify_inse": True,
                        "use_precomputed": False,
                    },
                ),
                ("/cross/director-tech", {**base, "variable": "TX_Q194"}),
                ("/cross/director-tech", {**base, "variable": "TX_Q219"}),
                ("/cross/director-tech", {**base, "variable": "TX_Q035"}),
                ("/cross/director-tech", {**base, "variable": "TX_Q036"}),
                ("/cross/teacher-tech", {**base, "variable": "TX_Q029"}),
                ("/cross/teacher-tech", {**base, "variable": "TX_Q037"}),
            ]
            for path, params in expected:
                slug = export_static.slug_path(path, params)
                assert slug in exported_slugs, f"Combinação ausente no export estático: {path} {params}"


def test_inject_static_flag_injects_meta_in_head_without_inline_script() -> None:
    """_inject_static_flag injeta <meta name="static-data" content="true"> no <head> sem <script> inline."""
    sample = "<html><head><title>Painel</title></head><body><script src='/static/js/app.js'></script></body></html>"
    injected = export_static._inject_static_flag(sample)
    meta_pos = injected.find('<meta name="static-data" content="true">')
    head_close_pos = injected.find("</head>")
    app_pos = injected.find("<script src='/static/js/app.js'>")
    assert 0 <= meta_pos < head_close_pos < app_pos
    assert "window.STATIC_DATA" not in injected


def test_inject_static_flag_fallbacks_without_closing_head() -> None:
    """Quando o HTML não possui </head> ou <head>, a meta tag ainda é injetada sem erro."""
    open_only = "<html><head><body><h1>Parcial</h1></body></html>"
    injected_open = export_static._inject_static_flag(open_only)
    assert '<meta name="static-data" content="true">' in injected_open
    assert "window.STATIC_DATA" not in injected_open

    no_head = "<html><body><h1>Sem head</h1></body></html>"
    injected_no_head = export_static._inject_static_flag(no_head)
    assert injected_no_head.startswith('<meta name="static-data" content="true">')
    assert no_head in injected_no_head


def test_inject_static_flag_on_real_dashboard_template() -> None:
    """No dashboard.html real, <meta name="static-data" content="true"> fica no <head> antes dos scripts."""
    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    injected = export_static._inject_static_flag(html)
    meta_pos = injected.find('<meta name="static-data" content="true">')
    head_close_pos = injected.find("</head>")
    charts_pos = injected.find("/static/js/charts.js")
    app_pos = injected.find("/static/js/app.js")
    assert 0 <= meta_pos < head_close_pos < charts_pos < app_pos
    assert "window.STATIC_DATA" not in injected


def test_app_js_detects_static_mode_from_meta_tag_and_window_fallback() -> None:
    """app.js ativa STATIC_MODE via <meta name="static-data" content="true"> e mantém fallback window.STATIC_DATA."""
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync({json.dumps(str(APP_JS))}, 'utf8');

function evalMode(opts) {{
    let fetchedUrl = null;
    const ctx = vm.createContext({{
        window: {{ ...(opts.windowProps || {{}}), location: {{ origin: 'http://localhost' }} }},
        document: {{
            addEventListener: () => {{}},
            querySelector: (sel) => {{
                if (sel === 'meta[name="static-data"]' && opts.metaContent !== null) {{
                    return {{ getAttribute: (k) => (k === 'content' ? opts.metaContent : null) }};
                }}
                return null;
            }},
        }},
        localStorage: {{ getItem: () => null, setItem: () => {{}} }},
        fetch: async (url) => {{
            fetchedUrl = String(url);
            return {{ ok: true, json: async () => ({{ ok: true }}) }};
        }},
        console,
        URL,
        AbortController,
        setTimeout,
        clearTimeout,
    }});
    vm.runInContext(code, ctx);
    const mode = vm.runInContext('STATIC_MODE', ctx);
    return ctx.fetchAPI('/saeb/overview', {{ serie: '9EF' }}).then(() => ({{ mode, fetchedUrl }}));
}}

(async () => {{
    const viaMeta = await evalMode({{ metaContent: 'true', windowProps: {{}} }});
    const viaWindow = await evalMode({{ metaContent: null, windowProps: {{ STATIC_DATA: true }} }});
    const dynamicMode = await evalMode({{ metaContent: null, windowProps: {{}} }});
    const metaFalse = await evalMode({{ metaContent: 'false', windowProps: {{}} }});
    process.stdout.write(JSON.stringify({{ viaMeta, viaWindow, dynamicMode, metaFalse }}));
}})();
"""
    res = _run_node_json(node_script)
    assert res["viaMeta"] == {"mode": True, "fetchedUrl": "/api/saeb/overview__serie-9EF.json"}
    assert res["viaWindow"] == {"mode": True, "fetchedUrl": "/api/saeb/overview__serie-9EF.json"}
    assert res["dynamicMode"] == {"mode": False, "fetchedUrl": "http://localhost/api/saeb/overview?serie=9EF"}
    assert res["metaFalse"] == {"mode": False, "fetchedUrl": "http://localhost/api/saeb/overview?serie=9EF"}


def test_export_uses_api_and_writes_only_to_tmp_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valida contrato de export() gravando exclusivamente em tmp_path (nunca em dist/)."""
    # Confirmar que export_static.py não consulta DuckDB diretamente
    export_src = (PROJECT_ROOT / "scripts" / "export_static.py").read_text(encoding="utf-8")
    assert "duckdb" not in export_src.lower()

    # Criar arquivo obsoleto em tmp_path/api para validar limpeza automática
    stale = tmp_path / "api" / "obsolete.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text('{"stale": true}', encoding="utf-8")

    monkeypatch.setattr(
        export_static,
        "enumerate_calls",
        lambda: [("/saeb/overview", {}), ("/tic/ai", {})],
    )
    monkeypatch.setattr(export_static, "QUESTIONNAIRE_DATASETS", [])

    rc = export_static.export(tmp_path, skip_pdf=True)
    assert rc == 0
    assert not stale.exists(), "Arquivos obsoletos em api/ devem ser removidos"

    index_html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<meta name="static-data" content="true">' in index_html
    assert "window.STATIC_DATA" not in index_html
    assert (tmp_path / "static" / "js" / "app.js").is_file()
    assert (tmp_path / "static" / "vendor" / "bootstrap" / "bootstrap.min.css").is_file()
    assert (tmp_path / "static" / "vendor" / "echarts" / "echarts.min.js").is_file()

    overview = json.loads((tmp_path / "api" / "saeb" / "overview.json").read_text(encoding="utf-8"))
    assert "alunos_por_serie" in overview
    tic_ai = json.loads((tmp_path / "api" / "tic" / "ai.json").read_text(encoding="utf-8"))
    assert "data" in tic_ai
