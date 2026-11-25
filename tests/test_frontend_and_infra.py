"""Testes de frontend JS (sintaxe e comportamento via Node) e infraestrutura."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "frontend" / "static"
JS_DIR = STATIC_DIR / "js"
VENDOR_DIR = STATIC_DIR / "vendor"
DASHBOARD_HTML = PROJECT_ROOT / "frontend" / "templates" / "dashboard.html"
FIREBASE_JSON = PROJECT_ROOT / "firebase.json"
DOCKER_COMPOSE_YML = PROJECT_ROOT / "docker-compose.yml"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"

EXPECTED_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


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


def _node_browser_harness_prefix() -> str:
    """Retorna trecho JS que inicializa um contexto VM com charts, glossary, explanations, app e pages."""
    files = [
        str(JS_DIR / "charts.js"),
        str(JS_DIR / "glossary.js"),
        str(JS_DIR / "explanations.js"),
        str(JS_DIR / "app.js"),
        str(JS_DIR / "pages.js"),
    ]
    return f"""
const fs = require('fs');
const vm = require('vm');

function makeElement(id, opts = {{}}) {{
    const classes = new Set(opts.classes || []);
    return {{
        id,
        innerHTML: '',
        textContent: '',
        value: opts.value || '',
        style: {{}},
        clientWidth: opts.clientWidth ?? 800,
        offsetWidth: opts.offsetWidth ?? 800,
        offsetHeight: 400,
        children: [],
        parentNode: {{ appendChild(child) {{ this.children.push(child); }}, children: [] }},
        classList: {{
            add(c) {{ classes.add(c); }},
            remove(c) {{ classes.delete(c); }},
            toggle(c, force) {{
                if (force === undefined) {{
                    if (classes.has(c)) classes.delete(c); else classes.add(c);
                }} else if (force) classes.add(c); else classes.delete(c);
            }},
            contains(c) {{ return classes.has(c); }},
        }},
        appendChild(child) {{ this.children.push(child); }},
        addEventListener() {{}},
        querySelector() {{ return null; }},
        querySelectorAll() {{ return []; }},
        getAttribute() {{ return null; }},
        setAttribute() {{}},
        removeAttribute() {{}},
    }};
}}

const elements = Object.create(null);
function ensureEl(id, opts = {{}}) {{
    if (!elements[id]) elements[id] = makeElement(id, opts);
    return elements[id];
}}

let currentThemeAttr = null;
const resizeListeners = [];
const initCalls = [];
const chartRecords = [];

const fakeEcharts = {{
    themes: {{}},
    registerTheme(name, obj) {{ this.themes[name] = obj; }},
    init(el, theme) {{
        let disposed = false;
        let lastOption = null;
        let resizeCount = 0;
        const inst = {{
            setOption(opt) {{ lastOption = opt; }},
            dispose() {{ disposed = true; }},
            isDisposed() {{ return disposed; }},
            resize() {{ resizeCount += 1; }},
            _meta: () => ({{ id: el.id, theme, disposed, lastOption, resizeCount }}),
        }};
        initCalls.push({{ id: el.id, theme }});
        chartRecords.push(inst);
        return inst;
    }},
}};

const fakeDocument = {{
    documentElement: {{
        getAttribute(k) {{ return k === 'data-theme' ? currentThemeAttr : null; }},
        setAttribute(k, v) {{ if (k === 'data-theme') currentThemeAttr = v; }},
        removeAttribute(k) {{ if (k === 'data-theme') currentThemeAttr = null; }},
    }},
    getElementById(id) {{ return elements[id] || null; }},
    querySelector() {{ return null; }},
    querySelectorAll() {{ return []; }},
    createElement(tag) {{ return makeElement(tag); }},
    addEventListener() {{}},
}};

const fakeWindow = {{
    innerWidth: 1200,
    location: {{ origin: 'http://localhost' }},
    addEventListener(evt, fn) {{ if (evt === 'resize') resizeListeners.push(fn); }},
}};

const ctx = vm.createContext({{
    window: fakeWindow,
    document: fakeDocument,
    echarts: fakeEcharts,
    bootstrap: {{ Popover: {{ getInstance: () => null }} }},
    localStorage: {{ getItem: () => null, setItem: () => {{}} }},
    console: {{ log: () => {{}}, warn: () => {{}}, error: () => {{}} }},
    URL,
    AbortController,
    setTimeout,
    clearTimeout,
    Promise,
    Number,
    Math,
    Object,
    Array,
    Set,
    String,
    Boolean,
    fetch: async () => ({{ ok: false, status: 500 }}),
}});

for (const filePath of {json.dumps(files)}) {{
    vm.runInContext(fs.readFileSync(filePath, 'utf8'), ctx, {{ filename: filePath }});
}}
"""


# ---------------------------------------------------------------------------
# 1. Sintaxe JS (node --check)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "js_file",
    sorted([*JS_DIR.glob("*.js"), *VENDOR_DIR.rglob("*.js")]),
    ids=lambda p: str(p.relative_to(STATIC_DIR)),
)
def test_js_files_syntax_valid(js_file: Path) -> None:
    """Todos os arquivos JS do frontend (próprios e vendorizados) devem passar em `node --check`."""
    proc = subprocess.run(
        ["node", "--check", str(js_file)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode == 0, f"Erro de sintaxe em {js_file}:\n{proc.stderr}"


# ---------------------------------------------------------------------------
# 2. Testes comportamentais JS via Node.js
# ---------------------------------------------------------------------------


def test_js_escape_html_and_show_empty_escaping() -> None:
    """escapeHtml escapa caracteres perigosos e showEmpty escapa a mensagem."""
    script = (
        _node_browser_harness_prefix()
        + """
ensureEl('box');
ctx.showEmpty('box', '<img src=x onerror="alert(1)"> & \\'ok\\'');
const out = {
    xss: ctx.escapeHtml('<script>alert("xss")</script>'),
    mixed: ctx.escapeHtml(`a & b 'c' "d" <e>`),
    nullVal: ctx.escapeHtml(null),
    undefVal: ctx.escapeHtml(undefined),
    zeroVal: ctx.escapeHtml(0),
    boxHtml: elements['box'].innerHTML,
};
process.stdout.write(JSON.stringify(out));
"""
    )
    res = _run_node_json(script)
    assert res["xss"] == "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;"
    assert res["mixed"] == "a &amp; b &#39;c&#39; &quot;d&quot; &lt;e&gt;"
    assert res["nullVal"] == ""
    assert res["undefVal"] == ""
    assert res["zeroVal"] == "0"
    assert "<img" not in res["boxHtml"]
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &#39;ok&#39;" in res["boxHtml"]


def test_js_show_empty_and_dispose_prevent_chart_resurrection_on_theme_toggle() -> None:
    """showEmpty() + disposeChart() impede que rerenderAllCharts() ressuscite gráfico obsoleto."""
    script = (
        _node_browser_harness_prefix()
        + """
ensureEl('chart-prof-levels', { offsetWidth: 800 });
ensureEl('chart-hidden', { offsetWidth: 0 });
ensureEl('chart-loading', { offsetWidth: 800 });

// 1. Renderiza gráficos ativos
ctx.renderChart('chart-prof-levels', { series: [{ type: 'bar', data: [10, 20] }] });
ctx.renderChart('chart-hidden', { series: [{ type: 'bar', data: [1, 2] }] });
ctx.renderChart('chart-loading', { series: [{ type: 'bar', data: [3, 4] }] });

// Troca tema enquanto chart-hidden está oculto -> vai para _staleThemeCharts
fakeDocument.documentElement.setAttribute('data-theme', 'dark');
ctx.rerenderAllCharts();
const staleBeforeEmpty = vm.runInContext('_staleThemeCharts.has("chart-hidden")', ctx);

const initCountBeforeEmpty = initCalls.length;
const firstVisibleInstance = chartRecords[chartRecords.length - 2];

// 2. Entra em estado vazio e em loading
ctx.showEmpty('chart-prof-levels', 'Níveis não disponíveis para esta série/disciplina');
ctx.showEmpty('chart-hidden', 'Sem dados');
ctx.showLoading('chart-loading');

const stateAfterEmpty = vm.runInContext(`({
    hasVisibleOpt: Object.prototype.hasOwnProperty.call(_chartOptions, 'chart-prof-levels'),
    hasVisibleInst: Object.prototype.hasOwnProperty.call(_chartInstances, 'chart-prof-levels'),
    hasHiddenOpt: Object.prototype.hasOwnProperty.call(_chartOptions, 'chart-hidden'),
    hasHiddenStale: _staleThemeCharts.has('chart-hidden'),
    hasLoadingOpt: Object.prototype.hasOwnProperty.call(_chartOptions, 'chart-loading'),
    hasLoadingInst: Object.prototype.hasOwnProperty.call(_chartInstances, 'chart-loading'),
})`, ctx);

// 3. Alterna Dark Mode novamente e chama rerenderAllCharts()
fakeDocument.documentElement.removeAttribute('data-theme');
ctx.rerenderAllCharts();

const out = {
    staleBeforeEmpty,
    stateAfterEmpty,
    prevDisposed: firstVisibleInstance.isDisposed(),
    initCallsAfterRerender: initCalls.length - initCountBeforeEmpty,
    visibleStillEmpty: elements['chart-prof-levels'].innerHTML.includes('Níveis não disponíveis'),
    hiddenStillEmpty: elements['chart-hidden'].innerHTML.includes('Sem dados'),
    loadingStillSpinner: elements['chart-loading'].innerHTML.includes('loading-skeleton'),
    hiddenStaleAfterRerender: vm.runInContext('_staleThemeCharts.has("chart-hidden")', ctx),
};
process.stdout.write(JSON.stringify(out));
"""
    )
    res = _run_node_json(script)
    assert res["staleBeforeEmpty"] is True
    assert res["prevDisposed"] is True
    assert res["stateAfterEmpty"] == {
        "hasVisibleOpt": False,
        "hasVisibleInst": False,
        "hasHiddenOpt": False,
        "hasHiddenStale": False,
        "hasLoadingOpt": False,
        "hasLoadingInst": False,
    }
    assert res["initCallsAfterRerender"] == 0, "rerenderAllCharts() não deve ressuscitar gráficos descartados"
    assert res["visibleStillEmpty"] is True
    assert res["hiddenStillEmpty"] is True
    assert res["loadingStillSpinner"] is True
    assert res["hiddenStaleAfterRerender"] is False


def test_js_resize_listener_is_debounced() -> None:
    """Múltiplos eventos resize consecutivos devem disparar apenas 1 chart.resize() após debounce."""
    script = (
        _node_browser_harness_prefix()
        + """
ensureEl('chart-r', { offsetWidth: 800 });
const chart = ctx.renderChart('chart-r', { series: [{ type: 'bar', data: [1] }] });
for (let i = 0; i < 5; i++) {
    resizeListeners.forEach(fn => fn());
}
const immediateCount = chart._meta().resizeCount;
setTimeout(() => {
    const finalCount = chart._meta().resizeCount;
    process.stdout.write(JSON.stringify({ immediateCount, finalCount }));
}, 220);
"""
    )
    res = _run_node_json(script)
    assert res["immediateCount"] == 0
    assert res["finalCount"] == 1


def test_js_teach_corr_nan_guard_for_small_n_and_zero_variance() -> None:
    """_renderTeachCorr nunca produz NaN para n < 2 ou variância zero e funciona no caso válido."""
    script = (
        _node_browser_harness_prefix()
        + """
ensureEl('corr-serie', { value: '5EF' });
ensureEl('corr-disciplina', { value: 'LP' });
ensureEl('corr-formation-note');
ensureEl('chart-teach-corr', { offsetWidth: 800 });

function runCase(rows) {
    const startInit = initCalls.length;
    ctx._renderTeachCorr({ data: rows });
    const rendered = initCalls.length > startInit;
    const meta = rendered ? chartRecords[chartRecords.length - 1]._meta() : null;
    const opt = meta ? meta.lastOption : null;
    const graphicText = opt && opt.graphic && opt.graphic[0] ? opt.graphic[0].children[0].style.text : null;
    const seriesTypes = opt ? opt.series.map(s => s.type) : [];
    const hasNan = opt ? JSON.stringify(opt, (_, v) => (Number.isNaN(v) ? '__NAN__' : v)).includes('__NAN__') : false;
    return {
        rendered,
        html: elements['chart-teach-corr'].innerHTML,
        graphicText,
        seriesTypes,
        hasNan,
    };
}

const out = {
    n0: runCase([]),
    n1: runCase([{ pc_formacao_docente_inicial: 80, media_5ef_lp: 220 }]),
    zeroVarX: runCase([
        { pc_formacao_docente_inicial: 50, media_5ef_lp: 200 },
        { pc_formacao_docente_inicial: 50, media_5ef_lp: 230 },
        { pc_formacao_docente_inicial: 50, media_5ef_lp: 260 },
    ]),
    zeroVarY: runCase([
        { pc_formacao_docente_inicial: 20, media_5ef_lp: 210 },
        { pc_formacao_docente_inicial: 50, media_5ef_lp: 210 },
        { pc_formacao_docente_inicial: 80, media_5ef_lp: 210 },
    ]),
    valid: runCase([
        { pc_formacao_docente_inicial: 10, media_5ef_lp: 100 },
        { pc_formacao_docente_inicial: 20, media_5ef_lp: 200 },
        { pc_formacao_docente_inicial: 30, media_5ef_lp: 300 },
    ]),
};
process.stdout.write(JSON.stringify(out));
"""
    )
    res = _run_node_json(script)
    assert res["n0"]["rendered"] is False
    assert "Dados não disponíveis" in res["n0"]["html"]
    assert res["n1"]["rendered"] is False
    assert "Dados insuficientes" in res["n1"]["html"]

    for key in ("zeroVarX", "zeroVarY"):
        assert res[key]["rendered"] is True
        assert res[key]["seriesTypes"] == ["scatter"]
        assert res[key]["hasNan"] is False
        assert "NaN" not in (res[key]["graphicText"] or "")
        assert "r = —" in (res[key]["graphicText"] or "")

    assert res["valid"]["rendered"] is True
    assert res["valid"]["seriesTypes"] == ["scatter", "line"]
    assert res["valid"]["hasNan"] is False
    assert "1,000" in (res["valid"]["graphicText"] or "") or "1.000" in (res["valid"]["graphicText"] or "")


def test_js_questionnaire_truncation_interval_and_escaping() -> None:
    """renderQuestionnaireChart trunca rótulos > 45 chars, escapa tooltip e usa interval dinâmico."""
    script = (
        _node_browser_harness_prefix()
        + """
ensureEl('quest-question-text', { classes: ['d-none'] });
ensureEl('quest-question-label');
ensureEl('chart-questionnaire', { offsetWidth: 800 });

const longLabel = 'Texto muito longo com <script>alert(1)</script> que passa de quarenta e cinco caracteres';
let mockPayload = null;
ctx.fetchAPI = async () => mockPayload;

(async () => {
    mockPayload = {
        question_text: 'Pergunta de teste',
        data: [
            { resposta: 'A<1>', resposta_label: longLabel, contagem: 30 },
            { resposta: 'B', resposta_label: 'Curto', contagem: 70 },
        ],
    };
    await ctx.renderQuestionnaireChart('professor', 'TX_Q001')();
    const optSmall = chartRecords[chartRecords.length - 1]._meta().lastOption;
    const tipHtml = optSmall.tooltip.formatter([{ dataIndex: 0, value: 30 }]);

    // Agora com 30 categorias (> 25) -> interval deve ser 'auto'
    mockPayload = {
        question_text: 'Muitas categorias',
        data: Array.from({ length: 30 }, (_, i) => ({
            resposta: `R${i}`,
            resposta_label: `Opção ${i}`,
            contagem: i + 1,
        })),
    };
    await ctx.renderQuestionnaireChart('professor', 'TX_Q002')();
    const optLarge = chartRecords[chartRecords.length - 1]._meta().lastOption;

    process.stdout.write(JSON.stringify({
        xLabel0: optSmall.xAxis.data[0],
        xLabel1: optSmall.xAxis.data[1],
        intervalSmall: optSmall.xAxis.axisLabel.interval,
        intervalLarge: optLarge.xAxis.axisLabel.interval,
        tipHtml,
    }));
})();
"""
    )
    res = _run_node_json(script)
    assert len(res["xLabel0"]) == 45
    assert res["xLabel0"].endswith("…")
    assert res["xLabel1"] == "Curto"
    assert res["intervalSmall"] == 0
    assert res["intervalLarge"] == "auto"
    assert "<script>" not in res["tipHtml"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in res["tipHtml"]
    assert "quarenta e cinco caracteres" in res["tipHtml"]
    assert "(&lt;" not in res["tipHtml"]  # codigo é A<1> -> A&lt;1&gt;
    assert "(A&lt;1&gt;)" in res["tipHtml"]


def test_js_failed_fetches_clear_spinners_and_abort_question_controller() -> None:
    """Falhas em loadOverview/loadProficiency exibem showEmpty; startPageLoad aborta _questionController."""
    script = (
        _node_browser_harness_prefix()
        + """
for (const id of [
    'chart-overview-bars', 'chart-overview-ranking',
    'chart-prof-distribution', 'chart-prof-levels', 'chart-prof-compare',
    'chart-questionnaire', 'quest-question', 'quest-dataset',
    'quest-question-text', 'quest-question-label',
    'ethics-cross-findings', 'table-cross-summary', 'chart-cross-forest',
]) {
    ensureEl(id, { offsetWidth: 800, value: id === 'quest-dataset' ? 'professor' : '' });
}

ctx.fetchAPI = async () => null;

(async () => {
    await ctx.loadOverview();
    await ctx.loadProficiency();

    // Testa abort de _questionController em startPageLoad
    const aborted = vm.runInContext(`(() => {
        _questionController = new AbortController();
        const sig = _questionController.signal;
        startPageLoad('home');
        return sig.aborted;
    })()`, ctx);

    // Testa limpeza de #chart-questionnaire em loadQuestionnaires
    ctx.renderChart('chart-questionnaire', { series: [{ type: 'bar', data: [5] }] });
    await ctx.loadQuestionnaires();
    const questCleared = vm.runInContext(
        '!Object.prototype.hasOwnProperty.call(_chartOptions, "chart-questionnaire")',
        ctx
    );

    // Testa escapeHtml preservando statTerm em _loadCrossOverviewTab e _loadEthicsCrossFindings
    ctx.fetchAPI = async () => ({
        bonferroni_alpha: 0.0045,
        note: 'Nota <script>bad()</script>',
        analyses: [{
            level: 'aluno',
            label: 'Wi-Fi <b>malicioso</b>',
            test_type: 't-test',
            p_value: 0.0001,
            cohens_d: 0.42,
        }],
    });
    await ctx._loadEthicsCrossFindings();
    await ctx._loadCrossOverviewTab();
    const forestOpt = chartRecords[chartRecords.length - 1]._meta().lastOption;
    const forestTip = forestOpt.tooltip.formatter([{ name: 'Wi-Fi <img onerror=1>', value: 0.42 }]);

    // Testa escapeHtml no tooltip de _plotTicComparison
    ensureEl('chart-tech-infra', { offsetWidth: 800 });
    ctx._plotTicComparison('chart-tech-infra', {
        regions: { primary: 'Sudeste<1>', reference: 'Brasil&Co' },
        data: [{
            indicador: 'A1<b>',
            label: 'Acesso <script>x</script>',
            item: 'Detalhe <img src=x>',
            sudeste: 80,
            brasil: 70,
            me_sudeste: 1.5,
            me_brasil: 1.2,
            universo_especifico: true,
            universo: 'Escolas <urbanas>',
        }],
    }, '#4e79a7');
    const ticOpt = chartRecords[chartRecords.length - 1]._meta().lastOption;
    const ticTip = ticOpt.tooltip.formatter([{ dataIndex: 0 }]);

    process.stdout.write(JSON.stringify({
        overviewBarsHasSpinner: elements['chart-overview-bars'].innerHTML.includes('loading-skeleton'),
        overviewRankHasSpinner: elements['chart-overview-ranking'].innerHTML.includes('loading-skeleton'),
        profCompareHasSpinner: elements['chart-prof-compare'].innerHTML.includes('loading-skeleton'),
        profDistHasSpinner: elements['chart-prof-distribution'].innerHTML.includes('loading-skeleton'),
        profLevelsHasSpinner: elements['chart-prof-levels'].innerHTML.includes('loading-skeleton'),
        aborted,
        questCleared,
        ethicsHtml: elements['ethics-cross-findings'].innerHTML,
        summaryHtml: elements['table-cross-summary'].innerHTML,
        forestTip,
        ticTip,
    }));
})();
"""
    )
    res = _run_node_json(script)
    assert res["overviewBarsHasSpinner"] is False
    assert res["overviewRankHasSpinner"] is False
    assert res["profCompareHasSpinner"] is False
    assert res["profDistHasSpinner"] is False
    assert res["profLevelsHasSpinner"] is False
    assert res["aborted"] is True
    assert res["questCleared"] is True

    # statTerm preservado e dados escapados
    assert 'class="stat-term"' in res["ethicsHtml"]
    assert "<b>malicioso</b>" not in res["ethicsHtml"]
    assert "&lt;b&gt;malicioso&lt;/b&gt;" in res["ethicsHtml"]

    assert 'class="stat-term"' in res["summaryHtml"]
    assert "<script>bad()</script>" not in res["summaryHtml"]
    assert "&lt;script&gt;bad()&lt;/script&gt;" in res["summaryHtml"]
    assert "&lt;b&gt;malicioso&lt;/b&gt;" in res["summaryHtml"]

    assert 'class="stat-term"' in res["forestTip"]
    assert "<img" not in res["forestTip"]
    assert "&lt;img onerror=1&gt;" in res["forestTip"]

    assert "<script>" not in res["ticTip"]
    assert "<img" not in res["ticTip"]
    assert "A1&lt;b&gt;" in res["ticTip"]
    assert "&lt;script&gt;x&lt;/script&gt;" in res["ticTip"]
    assert "Brasil&amp;Co" in res["ticTip"]
    assert "Escolas &lt;urbanas&gt;" in res["ticTip"]


def test_js_scroll_links_delegation_replaces_onclick() -> None:
    """initScrollLinks() faz scroll suave via data-scroll-to sem depender de onclick inline."""
    script = (
        _node_browser_harness_prefix()
        + """
let docClickHandler = null;
fakeDocument.addEventListener = (evt, fn) => {
    if (evt === 'click') docClickHandler = fn;
};

let scrolledOpts = null;
const sec9 = ensureEl('dd-sec-9');
sec9.scrollIntoView = (opts) => { scrolledOpts = opts; };

ctx.initScrollLinks();

let prevented = false;
const anchor = {
    getAttribute: (k) => (k === 'data-scroll-to' ? 'dd-sec-9' : null),
};
const nestedChild = {
    closest: (sel) => (sel === '[data-scroll-to]' ? anchor : null),
};
docClickHandler({
    target: nestedChild,
    preventDefault: () => { prevented = true; },
});

process.stdout.write(JSON.stringify({
    hasHandler: typeof docClickHandler === 'function',
    prevented,
    scrolledOpts,
}));
"""
    )
    res = _run_node_json(script)
    assert res["hasHandler"] is True
    assert res["prevented"] is True
    assert res["scrolledOpts"] == {"behavior": "smooth"}


def test_js_cross_student_tab_and_plot_cross_gap_error_bars_and_stats() -> None:
    """R-02: _loadCrossStudentTab e _plotCrossGap renderizam IC 95%, Gap | d | p e r = ... | p = ..."""
    script = (
        _node_browser_harness_prefix()
        + """
for (const id of [
    'chart-cross-computers', 'chart-cross-wifi', 'chart-cross-phones', 'chart-cross-index',
]) {
    ensureEl(id, { offsetWidth: 800 });
}

ctx.fetchAPI = async (path, params) => {
    if (path === '/cross/student-tech' && params.variable === 'TX_RESP_Q13b') {
        return {
            variable: 'TX_RESP_Q13b',
            groups: [
                { code: 'A', label: 'Não', mean: 244.2, ci_low: 241.0, ci_high: 247.4, n: 1200 },
                { code: 'B', label: 'Sim', mean: 263.6, ci_low: 260.5, ci_high: 266.7, n: 8500 },
            ],
            test: { type: 't-test', gap: 19.4, cohens_d: 0.382, p_value: 0.0001 },
        };
    }
    if (path === '/cross/student-tech' && params.variable === 'TX_RESP_Q12b') {
        return {
            variable: 'TX_RESP_Q12b',
            overall: {
                groups: [
                    { code: 'A', label: 'Nenhum', mean: 248.0, ci_lower: 245.5, ci_upper: 250.5, n: 4000 },
                    { code: 'B', label: '1', mean: 269.0, ci_lower: 266.0, ci_upper: 272.0, n: 3000 },
                    { code: 'C', label: '2', mean: 281.0, ci_lower: 276.0, ci_upper: 286.0, n: 900 },
                ],
                test: { type: 'anova', f_stat: 42.1, eta_squared: 0.0512, trend_r: 0.224, p_value: 0.00002 },
            },
        };
    }
    if (path === '/cross/student-tech' && params.variable === 'TX_RESP_Q12g') {
        return {
            variable: 'TX_RESP_Q12g',
            groups: [
                { code: 'A', label: 'Nenhum', mean: 230.0, ci_low: 225.0, ci_high: 235.0, n: 500 },
                { code: 'B', label: '1', mean: 255.0, ci_low: 252.0, ci_high: 258.0, n: 3200 },
            ],
            test: { type: 'anova', f_stat: 18.4, eta_squared: 0.031, p_value: 0.002 },
            correlation: { pearson_r: 0.176, p_value: 0.002 },
        };
    }
    if (path === '/cross/digital-index') {
        return {
            by_level: Array.from({ length: 9 }, (_, idx) => ({
                index: idx,
                mean: 230 + idx * 7.5,
                ci_low: 227 + idx * 7.5,
                ci_high: 233 + idx * 7.5,
                n: 500 + idx * 100,
            })),
            correlation: { pearson_r: 0.251, p_value: 0.00001, n: 8500 },
        };
    }
    return null;
};

(async () => {
    await ctx._loadCrossStudentTab();
    const byId = Object.fromEntries(chartRecords.map(r => [r._meta().id, r._meta().lastOption]));

    const wifiOpt = byId['chart-cross-wifi'];
    const compOpt = byId['chart-cross-computers'];
    const indexOpt = byId['chart-cross-index'];

    const wifiErrSeries = wifiOpt.series.find(s => s.type === 'custom');
    const renderedShape = wifiErrSeries.renderItem({}, {
        value: (i) => wifiErrSeries.data[0][i],
        coord: ([x, y]) => [100 + x * 80, 300 - y],
    });

    process.stdout.write(JSON.stringify({
        wifiAnnotation: wifiOpt.graphic[0].children[0].style.text,
        wifiSeriesTypes: wifiOpt.series.map(s => s.type),
        wifiErrData: wifiErrSeries.data,
        wifiTip: wifiOpt.tooltip.formatter([{ dataIndex: 1, name: 'Sim', value: 263.6 }]),
        renderedChildrenCount: renderedShape.children.length,
        compAnnotation: compOpt.graphic[0].children[0].style.text,
        compSeriesTypes: compOpt.series.map(s => s.type),
        compTip: compOpt.tooltip.formatter([{ dataIndex: 0, name: 'Nenhum', value: 248.0 }]),
        indexAnnotation: indexOpt.graphic[0].children[0].style.text,
        indexSeriesTypes: indexOpt.series.map(s => s.type),
        indexLevelsCount: indexOpt.xAxis.data.length,
        indexTip: indexOpt.tooltip.formatter([{ dataIndex: 4, name: '4', value: 260.0 }]),
    }));
})();
"""
    )
    res = _run_node_json(script)
    assert res["wifiSeriesTypes"] == ["bar", "custom"]
    assert res["wifiErrData"] == [[0, 241.0, 247.4], [1, 260.5, 266.7]]
    assert res["renderedChildrenCount"] == 3
    assert "Gap:" in res["wifiAnnotation"]
    assert "d =" in res["wifiAnnotation"]
    assert "p = <0.001" in res["wifiAnnotation"]
    assert "IC 95%:" in res["wifiTip"]

    assert res["compSeriesTypes"] == ["bar", "custom"]
    assert "η² =" in res["compAnnotation"]
    assert "r =" in res["compAnnotation"]
    assert "p = <0.001" in res["compAnnotation"]
    assert "IC 95%:" in res["compTip"]

    assert res["indexSeriesTypes"] == ["line", "custom"]
    assert res["indexLevelsCount"] == 9
    assert "r =" in res["indexAnnotation"]
    assert "p = <0.001" in res["indexAnnotation"]
    assert "IC 95%:" in res["indexTip"]


def test_js_proficiency_levels_34em_renders_all_levels() -> None:
    """R-04b: loadProficiency renderiza nivel_0_lp34em.. e nivel_0_mt34em.. (incluindo Nível 10)."""
    script = (
        _node_browser_harness_prefix()
        + """
for (const id of ['chart-prof-distribution', 'chart-prof-levels', 'chart-prof-compare']) {
    ensureEl(id, { offsetWidth: 800 });
}

const fakeLevelsRow = {
    rede: 1,
    nivel_0_lp34em: 12.4,
    nivel_1_lp34em: 15.1,
    nivel_2_lp34em: 18.0,
    nivel_8_lp34em: 2.3,
    nivel_0_mt34em: 19.5,
    nivel_2_mt34em: 21.0,
    nivel_10_mt34em: 0.6,
    nivel_0_lp9: 99.9,
};

ctx.fetchAPI = async (path) => {
    if (path === '/saeb/proficiency/levels') return { data: [fakeLevelsRow] };
    return null;
};

(async () => {
    vm.runInContext("state.serie = '34EM'; state.disciplina = 'LP';", ctx);
    await ctx.loadProficiency();
    const lpOpt = chartRecords[chartRecords.length - 1]._meta().lastOption;

    vm.runInContext("state.serie = '34EM'; state.disciplina = 'MT';", ctx);
    await ctx.loadProficiency();
    const mtOpt = chartRecords[chartRecords.length - 1]._meta().lastOption;

    process.stdout.write(JSON.stringify({
        lpCategories: lpOpt.xAxis.data,
        lpValues: lpOpt.series[0].data.map(d => d.value),
        mtCategories: mtOpt.xAxis.data,
        mtValues: mtOpt.series[0].data.map(d => d.value),
    }));
})();
"""
    )
    res = _run_node_json(script)
    assert res["lpCategories"] == ["Nível 0", "Nível 1", "Nível 2", "Nível 8"]
    assert res["lpValues"] == [12.4, 15.1, 18.0, 2.3]
    assert res["mtCategories"] == ["Nível 0", "Nível 2", "Nível 10"]
    assert res["mtValues"] == [19.5, 21.0, 0.6]


# ---------------------------------------------------------------------------
# 3. Infraestrutura: firebase.json, docker-compose.yml, .dockerignore, Dockerfile
# ---------------------------------------------------------------------------


def test_firebase_json_security_headers_csp_and_cache_control() -> None:
    """firebase.json é JSON válido com CSP estrita (sem unsafe-inline em script-src) e vendor immutable."""
    config = json.loads(FIREBASE_JSON.read_text(encoding="utf-8"))
    headers_blocks = config["hosting"]["headers"]

    global_blocks = [b for b in headers_blocks if b.get("source") == "**"]
    assert len(global_blocks) == 1
    sec_headers = {h["key"]: h["value"] for h in global_blocks[0]["headers"]}
    assert sec_headers["X-Content-Type-Options"] == "nosniff"
    assert sec_headers["X-Frame-Options"] == "DENY"
    assert sec_headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert sec_headers["Content-Security-Policy"] == EXPECTED_CSP

    csp_directives = {
        part.strip().split()[0]: part.strip().split()[1:]
        for part in sec_headers["Content-Security-Policy"].split(";")
        if part.strip()
    }
    assert csp_directives["script-src"] == ["'self'"]
    assert "'unsafe-inline'" not in csp_directives["script-src"]
    assert "'unsafe-eval'" not in csp_directives["script-src"]

    cache_by_source = {
        b["source"]: {h["key"]: h["value"] for h in b["headers"]}.get("Cache-Control")
        for b in headers_blocks
        if b.get("source") != "**"
    }
    assert cache_by_source == {
        "/api/**": "no-cache",
        "/": "no-cache",
        "**/*.html": "no-cache",
        "/dashboard": "no-cache",
        "**/*.@(js|css)": "public, max-age=86400",
        "/static/vendor/**": "public, max-age=31536000, immutable",
        "/reports/**": "no-cache",
    }

    # Regra de /static/vendor/** deve vir depois de **/*.@(js|css) para prevalecer no Firebase Hosting
    sources_order = [b["source"] for b in headers_blocks]
    assert sources_order.index("**/*.@(js|css)") < sources_order.index("/static/vendor/**")


def test_docker_compose_resource_limits_and_no_new_privileges() -> None:
    """R-05b: docker-compose.yml define mem_limit, cpus e no-new-privileges no serviço dashboard."""
    raw = DOCKER_COMPOSE_YML.read_text(encoding="utf-8")
    assert re.search(r"^\s*mem_limit:\s*2g\s*$", raw, flags=re.MULTILINE)
    assert re.search(r"^\s*cpus:\s*2\.0\s*$", raw, flags=re.MULTILINE)
    assert "no-new-privileges:true" in raw
    assert ":ro" in raw


def test_dockerignore_excludes_heavy_and_sensitive_paths() -> None:
    """Valida que .dockerignore existe e exclui artefatos pesados/sensíveis sem excluir data/processed."""
    assert DOCKERIGNORE.is_file()
    entries = {
        line.strip().rstrip("/")
        for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    required = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        ".firebase",
        ".claude",
        ".gemini",
        "pesquisa_ppe",
        "*.pdf",
        "*.docx",
        "*.pptx",
        "*.xlsx",
        "data/MICRODADOS_SAEB_2023",
        "data/tic_educacao_2023_escolas_tabelas_xlsx_v1.0",
        ".env*",
    }
    missing = required - entries
    assert not missing, f"Entradas ausentes em .dockerignore: {sorted(missing)}"
    assert "data/processed" not in entries
    assert "data" not in entries


def test_dockerfile_hardening_directives() -> None:
    """Dockerfile define usuário não-root, MPLCONFIGDIR, PYTHONDONTWRITEBYTECODE, HEALTHCHECK e COPY data/processed/."""
    content = DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^\s*USER\s+appuser\b", content, flags=re.MULTILINE)
    assert "MPLCONFIGDIR=/tmp/matplotlib" in content
    assert "PYTHONDONTWRITEBYTECODE=1" in content
    assert re.search(r"^\s*HEALTHCHECK\b.*(/api/health)", content, flags=re.MULTILINE | re.DOTALL)
    assert re.search(r"^\s*COPY\s+.*data/processed/\s+data/processed/", content, flags=re.MULTILINE)


# ---------------------------------------------------------------------------
# 4. dashboard.html: correções textuais e KaTeX sob demanda
# ---------------------------------------------------------------------------


def test_dashboard_html_text_fixes_and_no_duplicate_katex_script() -> None:
    """Valida textos corrigidos e ausência do bloco inline duplicado de KaTeX no template e em GET /dashboard."""
    template = DASHBOARD_HTML.read_text(encoding="utf-8")
    client = TestClient(app)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    rendered = resp.text

    for html in (template, rendered):
        # 1. Sem script inline duplicado de KaTeX no boot
        assert "katex.render(" not in html

        # 2. Bonferroni atualizado (11 testes)
        assert "0,05/11 ≈ 0,0045" in html
        assert "0,05/12" not in html

        # 3. Total aproximado de alunos no SAEB 2023 (~7,1 milhões)
        assert "~7,1 milhões de alunos" in html
        assert "~9 milhões de alunos" not in html

        # 4. Colunas da seção 2.8 de dados agregados por escola
        assert "MEDIA_EM_LP" in html
        assert "MEDIA_EM_MT" in html
        assert "PC_FORMACAO_DOCENTE_FINAL" in html
        assert "PC_FORMACAO_DOCENTE_MEDIO" in html

        # Fórmulas KaTeX continuam presentes para _initMethodologyKatex()
        assert 'class="katex-formula"' in html


def test_dashboard_html_zero_cdn_zero_inline_js_and_dedup_notes() -> None:
    """R-05a / R-01: zero CDNs externas, zero onclick= ou <script> inline, e notas de deduplicação."""
    template = DASHBOARD_HTML.read_text(encoding="utf-8")
    client = TestClient(app)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    rendered = resp.text

    forbidden_hosts = (
        "cdn.jsdelivr.net",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "unpkg.com",
        "cdnjs.cloudflare.com",
    )
    for html in (template, rendered):
        for host in forbidden_hosts:
            assert host not in html, f"Host externo proibido encontrado em dashboard.html: {host}"

        # Zero atributos inline on*= (onclick, onload, onerror, etc.) em tags HTML
        inline_handlers = re.findall(r"<[^>]+?\s(on[a-z]+\s*=)", html, flags=re.IGNORECASE | re.DOTALL)
        assert inline_handlers == [], f"Handlers inline encontrados no HTML: {inline_handlers}"

        # Zero javascript: URLs
        assert "javascript:" not in html.lower()

        # Todas as tags <script> devem carregar arquivo local (/static/...) e ter corpo vazio
        script_blocks = re.findall(r"<script\b([^>]*)>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL)
        assert len(script_blocks) == 8
        for attrs, body in script_blocks:
            assert body.strip() == "", f"Bloco <script> inline encontrado: {body!r}"
            src_match = re.search(r'src="([^"]+)"', attrs)
            assert src_match is not None, f"Tag <script> sem src: {attrs!r}"
            assert src_match.group(1).startswith("/static/"), f"Script externo não permitido: {src_match.group(1)}"

        # Todos os <link rel="stylesheet"> devem apontar para /static/...
        stylesheet_links = re.findall(
            r'<link\b[^>]*rel="stylesheet"[^>]*>', html, flags=re.IGNORECASE
        )
        assert len(stylesheet_links) == 5
        for tag in stylesheet_links:
            href_match = re.search(r'href="([^"]+)"', tag)
            assert href_match is not None
            assert href_match.group(1).startswith("/static/"), f"CSS externo não permitido: {href_match.group(1)}"

    # Nenhum JS próprio gera onclick= em strings HTML
    for js_file in sorted(JS_DIR.glob("*.js")):
        js_src = js_file.read_text(encoding="utf-8")
        assert not re.search(r"\bon[a-z]+\s*=", js_src, flags=re.IGNORECASE), (
            f"Atributo inline on*= encontrado em {js_file.name}"
        )

    # R-01: notas de deduplicação explícitas nas páginas 5 (Professores) e 6 (Questionários)
    teachers_sec = re.search(
        r'<div id="page-teachers".*?<!-- Página 6:', template, flags=re.DOTALL
    )
    assert teachers_sec is not None
    assert "ID_PROFESSOR" in teachers_sec.group(0)
    assert "ID_ESCOLA" in teachers_sec.group(0)

    quest_sec = re.search(
        r'<div id="page-questionnaires".*?<!-- Página 7:', template, flags=re.DOTALL
    )
    assert quest_sec is not None
    assert "ID_PROFESSOR" in quest_sec.group(0)
    assert "ID_ESCOLA" in quest_sec.group(0)


def test_vendor_assets_and_css_font_urls_all_exist_without_maps() -> None:
    """Todos os /static/vendor/... do HTML e todos os url(...) dos CSS vendorizados existem fisicamente."""
    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    vendor_refs = re.findall(r'(?:href|src)="(/static/vendor/[^"?#]+)', html)
    expected_refs = {
        "/static/vendor/inter/inter.css",
        "/static/vendor/bootstrap/bootstrap.min.css",
        "/static/vendor/bootstrap-icons/bootstrap-icons.min.css",
        "/static/vendor/katex/katex.min.css",
        "/static/vendor/bootstrap/bootstrap.bundle.min.js",
        "/static/vendor/katex/katex.min.js",
        "/static/vendor/echarts/echarts.min.js",
    }
    assert set(vendor_refs) == expected_refs

    for ref in vendor_refs:
        rel = ref.removeprefix("/static/")
        asset_path = STATIC_DIR / rel
        assert asset_path.is_file() and asset_path.stat().st_size > 0, f"Asset ausente ou vazio: {asset_path}"

    # Zero arquivos .map ou diretivas sourceMappingURL em vendor/
    map_files = list(VENDOR_DIR.rglob("*.map"))
    assert map_files == [], f"Arquivos .map desnecessários em vendor/: {map_files}"
    for text_asset in [*VENDOR_DIR.rglob("*.css"), *VENDOR_DIR.rglob("*.js")]:
        content = text_asset.read_text(encoding="utf-8")
        assert "sourceMappingURL" not in content, f"sourceMappingURL residual em {text_asset}"

    # Todos os url(...) de fontes/arquivos nos CSS vendorizados devem existir fisicamente em vendor/
    css_files = sorted(VENDOR_DIR.rglob("*.css"))
    assert len(css_files) == 4
    resolved_font_files: list[Path] = []
    for css_file in css_files:
        css_text = css_file.read_text(encoding="utf-8")
        for raw_url in re.findall(r"url\(([^)]+)\)", css_text):
            cleaned = raw_url.strip().strip("\"'")
            if cleaned.startswith(("data:", "#")):
                continue
            assert not cleaned.startswith(("http://", "https://", "//")), (
                f"URL externa dentro de {css_file}: {cleaned}"
            )
            rel_path = cleaned.split("?", 1)[0].split("#", 1)[0]
            target_file = (css_file.parent / rel_path).resolve()
            assert VENDOR_DIR.resolve() in target_file.parents, (
                f"URL escapa de vendor/ em {css_file}: {cleaned}"
            )
            assert target_file.is_file() and target_file.stat().st_size > 0, (
                f"Fonte/asset referenciado em {css_file.name} não existe: {cleaned} -> {target_file}"
            )
            resolved_font_files.append(target_file)

    # 8 woff2 Inter + 2 woff/woff2 Bootstrap Icons + 20 woff2 KaTeX = 30 referências de fontes
    assert len(resolved_font_files) == 30
