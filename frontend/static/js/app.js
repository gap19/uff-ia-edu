/**
 * Dashboard IA e Educação — UFF
 * Controlador principal: init, navegação, filtros, helpers, relatório
 *
 * Dependências (carregados antes deste arquivo):
 *   - charts.js (COLORS, renderChart, gradientBar, etc.)
 *   - glossary.js (STAT_GLOSSARY, statTerm, initStatPopovers)
 *   - explanations.js (CHART_EXPLANATIONS, renderExplanation)
 *   - pages.js (loadPage, loadOverview, etc.)
 */

const API_BASE = '/api';

// Estado global dos filtros
const state = {
    page: 'overview',
    serie: '9EF',
    disciplina: 'LP',
    rede: '',
};

// =========================================================
// Navegação
// =========================================================

function initNavigation() {
    document.querySelectorAll('[data-page]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            navigateTo(link.dataset.page);
        });
    });
}

function navigateTo(page) {
    state.page = page;

    document.querySelectorAll('[data-page]').forEach(link => {
        link.classList.toggle('active', link.dataset.page === page);
        link.classList.toggle('text-white', link.dataset.page === page);
        link.classList.toggle('text-white-50', link.dataset.page !== page);
    });

    document.querySelectorAll('.page-section').forEach(section => {
        section.classList.add('d-none');
    });
    const target = document.getElementById(`page-${page}`);
    if (target) {
        target.classList.remove('d-none');
        // Reset animation
        target.style.animation = 'none';
        target.offsetHeight; // reflow
        target.style.animation = '';
    }

    // Hide global filters on pages that don't use them
    const filtersEl = document.getElementById('global-filters');
    if (filtersEl) {
        const withFilters = ['proficiency', 'equity', 'overview', 'ethics', 'cross-analysis'];
        filtersEl.style.display = withFilters.includes(page) ? 'flex' : 'none';
    }

    loadPage(page);
}

// =========================================================
// Filtros
// =========================================================

function initFilters() {
    document.getElementById('filter-serie').addEventListener('change', (e) => {
        state.serie = e.target.value;
        loadPage(state.page);
    });
    document.getElementById('filter-disciplina').addEventListener('change', (e) => {
        state.disciplina = e.target.value;
        loadPage(state.page);
    });
}

// =========================================================
// API Helper
// =========================================================

async function fetchAPI(path, params = {}) {
    const url = new URL(API_BASE + path, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== '' && v !== null && v !== undefined) {
            url.searchParams.set(k, v);
        }
    });
    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`API error: ${path}`, err);
        return null;
    }
}

// =========================================================
// Formatadores
// =========================================================

function fmtNum(n, decimals = 1) {
    if (n == null || isNaN(n)) return '—';
    return Number(n).toLocaleString('pt-BR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
}

function fmtInt(n) {
    if (n == null || isNaN(n)) return '—';
    return Number(n).toLocaleString('pt-BR');
}

function showLoading(elementId) {
    const el = document.getElementById(elementId);
    if (el) el.innerHTML = `
        <div class="loading-skeleton">
            <div class="spinner-border"></div>
            <span>Carregando dados...</span>
        </div>`;
}

function showEmpty(elementId, msg = 'Dados não disponíveis') {
    const el = document.getElementById(elementId);
    if (el) el.innerHTML = `<div class="text-center p-5" style="color: var(--clr-text-light)"><i class="bi bi-inbox" style="font-size:1.5rem"></i><br>${msg}</div>`;
}

// =========================================================
// Dark Mode
// =========================================================

function initThemeToggle() {
    const btn = document.getElementById('btn-theme');
    if (!btn) return;

    const stored = localStorage.getItem('uff-theme');
    if (stored === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        btn.innerHTML = '<i class="bi bi-sun"></i> <span class="nav-label">Modo Claro</span>';
    }

    btn.addEventListener('click', (e) => {
        e.preventDefault();
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        if (isDark) {
            document.documentElement.removeAttribute('data-theme');
            localStorage.setItem('uff-theme', 'light');
            btn.innerHTML = '<i class="bi bi-moon"></i> <span class="nav-label">Modo Escuro</span>';
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            localStorage.setItem('uff-theme', 'dark');
            btn.innerHTML = '<i class="bi bi-sun"></i> <span class="nav-label">Modo Claro</span>';
        }
        // Re-render all charts with the new theme colors
        rerenderAllCharts();
    });
}

// =========================================================
// Questionários init
// =========================================================

function initQuestionnaires() {
    document.getElementById('quest-dataset').addEventListener('change', loadQuestionnaires);
    document.getElementById('quest-question').addEventListener('change', async () => {
        const dataset = document.getElementById('quest-dataset').value;
        const questao = document.getElementById('quest-question').value;
        if (!questao) return;
        const handler = renderQuestionnaireChart(dataset, questao);
        await handler();
    });
}

// =========================================================
// Relatório PDF
// =========================================================

function initReport() {
    const btn = document.getElementById('btn-generate-report');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        const statusEl = document.getElementById('report-status');
        const errorEl = document.getElementById('report-error');
        statusEl.classList.remove('d-none');
        errorEl.classList.add('d-none');
        btn.disabled = true;

        const secoes = [];
        document.querySelectorAll('[id^="rep-sec-"]').forEach(cb => {
            if (cb.checked) secoes.push(cb.value);
        });
        const series = [];
        document.querySelectorAll('[id^="rep-serie-"]').forEach(cb => {
            if (cb.checked) series.push(cb.value);
        });
        const disciplinas = [];
        document.querySelectorAll('[id^="rep-disc-"]').forEach(cb => {
            if (cb.checked) disciplinas.push(cb.value);
        });
        const apendice = document.getElementById('rep-apendice').checked;

        const url = new URL('/api/reports/generate', window.location.origin);
        secoes.forEach(s => url.searchParams.append('secoes', s));
        series.forEach(s => url.searchParams.append('series', s));
        disciplinas.forEach(d => url.searchParams.append('disciplinas', d));
        url.searchParams.set('incluir_apendice', apendice);

        try {
            const resp = await fetch(url, { method: 'GET' });
            if (!resp.ok) {
                const text = await resp.text();
                throw new Error(text || `HTTP ${resp.status}`);
            }
            const blob = await resp.blob();
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'relatorio_ia_educacao_uff.pdf';
            link.click();
            URL.revokeObjectURL(link.href);

            const modal = bootstrap.Modal.getInstance(document.getElementById('reportModal'));
            if (modal) modal.hide();
        } catch (err) {
            errorEl.textContent = 'Erro ao gerar relatório: ' + err.message;
            errorEl.classList.remove('d-none');
        } finally {
            statusEl.classList.add('d-none');
            btn.disabled = false;
        }
    });
}

// =========================================================
// Tab resize: fix charts rendered in hidden tabs
// =========================================================

function initTabResize() {
    document.addEventListener('shown.bs.tab', (e) => {
        const targetPane = document.querySelector(e.target.getAttribute('data-bs-target') || e.target.getAttribute('href'));
        if (!targetPane) return;
        // Resize all ECharts instances inside the newly visible tab pane
        targetPane.querySelectorAll('.echarts-container').forEach(el => {
            const chart = _chartInstances[el.id];
            if (chart && !chart.isDisposed()) {
                chart.resize();
            }
        });
    });
}

// =========================================================
// Init
// =========================================================

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initFilters();
    initQuestionnaires();
    initReport();
    initThemeToggle();
    initTabResize();
    navigateTo('home');
});
