/**
 * Dashboard IA e Educação — UFF
 * ECharts wrapper, tema e funções auxiliares de gráficos
 */

// Paleta de cores global
const COLORS = {
    primary: '#4e79a7',
    primaryLight: '#6a9fd8',
    secondary: '#f28e2b',
    accent: '#e15759',
    green: '#59a14f',
    teal: '#76b7b2',
    purple: '#b07aa1',
    brown: '#9c755f',
    yellow: '#edc948',
    palette: ['#4e79a7', '#f28e2b', '#e15759', '#59a14f', '#76b7b2', '#b07aa1', '#9c755f', '#edc948'],
    gradient: ['#e15759', '#f28e2b', '#edc948', '#76b7b2', '#4e79a7', '#59a14f', '#9c755f', '#b07aa1'],
};

// Instâncias ECharts ativas (para resize e dispose)
const _chartInstances = {};
// Stored options for re-rendering on theme change
const _chartOptions = {};

// ─── Dark mode detection ────────────────────────────────────

function isDarkMode() {
    return document.documentElement.getAttribute('data-theme') === 'dark';
}

function themeColors() {
    const dark = isDarkMode();
    return {
        text:       dark ? '#e2e8f0' : '#4a5568',
        textStrong: dark ? '#f7fafc' : '#2d3748',
        textMuted:  dark ? '#a0aec0' : '#718096',
        textLight:  dark ? '#718096' : '#a0aec0',
        border:     dark ? '#2d3348' : '#e2e6ef',
        splitLine:  dark ? '#2d3348' : '#eef0f5',
        tooltipBg:  dark ? 'rgba(26,29,46,0.97)' : 'rgba(255,255,255,0.97)',
        tooltipBorder: dark ? '#2d3348' : '#e2e6ef',
        shadowStyle: dark ? 'rgba(78,121,167,0.12)' : 'rgba(78,121,167,0.06)',
    };
}

// ─── Registro dos temas ─────────────────────────────────────

function _buildThemeObj(tc) {
    return {
        color: COLORS.palette,
        backgroundColor: 'transparent',
        textStyle: {
            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            color: tc.text,
        },
        title: {
            textStyle: {
                fontSize: 14,
                fontWeight: 600,
                color: tc.textStrong,
            },
        },
        tooltip: {
            backgroundColor: tc.tooltipBg,
            borderColor: tc.tooltipBorder,
            borderWidth: 1,
            textStyle: { color: tc.textStrong, fontSize: 12.5, fontFamily: "'Inter', sans-serif" },
            extraCssText: 'box-shadow: 0 4px 14px rgba(0,0,0,0.15); border-radius: 8px; padding: 10px 14px;',
            trigger: 'axis',
            axisPointer: { type: 'shadow', shadowStyle: { color: tc.shadowStyle } },
        },
        legend: {
            textStyle: { fontSize: 12, color: tc.textMuted },
            itemGap: 16,
            itemWidth: 14,
            itemHeight: 10,
        },
        categoryAxis: {
            axisLine: { lineStyle: { color: tc.border } },
            axisTick: { show: false },
            axisLabel: { color: tc.textMuted, fontSize: 11.5 },
            splitLine: { show: false },
        },
        valueAxis: {
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: { color: tc.textLight, fontSize: 11 },
            splitLine: { lineStyle: { color: tc.splitLine, type: 'dashed' } },
        },
        toolbox: {
            feature: {
                saveAsImage: {
                    title: 'Salvar PNG',
                    pixelRatio: 2,
                    name: 'grafico_dashboard_uff',
                },
            },
            iconStyle: { borderColor: tc.textLight },
            emphasis: { iconStyle: { borderColor: '#4e79a7' } },
        },
        animationDuration: 700,
        animationDurationUpdate: 400,
        animationEasing: 'cubicOut',
    };
}

// Register both themes upfront
echarts.registerTheme('uff-light', _buildThemeObj(themeColors()));
echarts.registerTheme('uff-dark', _buildThemeObj((function() {
    // Force dark palette for registration
    return {
        text: '#e2e8f0', textStrong: '#f7fafc', textMuted: '#a0aec0', textLight: '#718096',
        border: '#2d3348', splitLine: '#2d3348',
        tooltipBg: 'rgba(26,29,46,0.97)', tooltipBorder: '#2d3348',
        shadowStyle: 'rgba(78,121,167,0.12)',
    };
})()));

function currentThemeName() {
    return isDarkMode() ? 'uff-dark' : 'uff-light';
}

// ─── Wrapper principal ────────────────────────────────────

/**
 * Renderiza um gráfico ECharts no elemento especificado.
 * Gerencia resize automático e dispose de instâncias anteriores.
 */
function renderChart(elementId, option, opts = {}) {
    const el = document.getElementById(elementId);
    if (!el) {
        console.warn(`Chart container #${elementId} not found`);
        return null;
    }

    // Dispose da instância anterior se existir
    if (_chartInstances[elementId]) {
        _chartInstances[elementId].dispose();
    }

    // Limpar conteúdo de loading
    el.innerHTML = '';

    const chart = echarts.init(el, currentThemeName(), {
        renderer: opts.renderer || 'canvas',
    });

    const tc = themeColors();

    // Merge com defaults
    const defaults = {
        grid: { top: 50, right: 30, bottom: 50, left: 60, containLabel: true },
        toolbox: {
            show: true,
            right: 10,
            top: 0,
            feature: {
                saveAsImage: { pixelRatio: 2, name: 'grafico_dashboard_uff' },
            },
        },
    };

    const merged = deepMerge(defaults, option);

    // Apply theme-aware label colors to all series that have labels
    if (merged.series) {
        const arr = Array.isArray(merged.series) ? merged.series : [merged.series];
        for (const s of arr) {
            if (s.label && s.label.show && !s.label.color) {
                s.label.color = tc.text;
            }
        }
    }

    // Store option for theme-switch re-render
    _chartOptions[elementId] = option;

    chart.setOption(merged);

    _chartInstances[elementId] = chart;
    return chart;
}

// Resize global
window.addEventListener('resize', () => {
    Object.values(_chartInstances).forEach(chart => {
        if (chart && !chart.isDisposed()) {
            chart.resize();
        }
    });
});

/**
 * Re-render all active charts with the current theme.
 * Called when dark/light mode is toggled.
 */
function rerenderAllCharts() {
    for (const [id, option] of Object.entries(_chartOptions)) {
        const el = document.getElementById(id);
        if (el && el.offsetWidth > 0) {
            renderChart(id, option);
        }
    }
}

// ─── Funções auxiliares de gráficos ───────────────────────

/**
 * Cria uma barra com gradiente vertical
 */
function gradientBar(color, opacity = 0.85) {
    const hex = color.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    return {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
            { offset: 0, color: `rgba(${r},${g},${b},${opacity})` },
            { offset: 1, color: `rgba(${r},${g},${b},${opacity * 0.55})` },
        ],
    };
}

/**
 * Annotation de estatística no topo do gráfico
 */
function statAnnotation(text, opts = {}) {
    return {
        type: 'group',
        left: opts.left || 'center',
        top: opts.top || 5,
        children: [{
            type: 'text',
            style: {
                text,
                fill: opts.color || COLORS.accent,
                fontSize: opts.fontSize || 12,
                fontFamily: "'Inter', sans-serif",
                fontWeight: 500,
            },
        }],
    };
}

/**
 * Formata número para tooltip
 */
function tooltipVal(v, decimals = 1) {
    if (v == null || isNaN(v)) return '—';
    return Number(v).toLocaleString('pt-BR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
}

/**
 * Deep merge de objetos (simples)
 */
function deepMerge(target, source) {
    const result = { ...target };
    for (const key of Object.keys(source)) {
        if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])
            && target[key] && typeof target[key] === 'object' && !Array.isArray(target[key])) {
            result[key] = deepMerge(target[key], source[key]);
        } else {
            result[key] = source[key];
        }
    }
    return result;
}
