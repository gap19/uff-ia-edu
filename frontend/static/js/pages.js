/**
 * Dashboard IA e Educação — UFF
 * Page loaders — carregam dados da API e renderizam com ECharts
 */

// =========================================================
// Page router
// =========================================================

async function loadPage(page) {
    switch (page) {
        case 'home': return; // Static content, no API calls needed
        case 'overview': return loadOverview();
        case 'proficiency': return loadProficiency();
        case 'equity': return loadEquity();
        case 'technology': return loadTechnology();
        case 'teachers': return loadTeachers();
        case 'questionnaires': return loadQuestionnaires();
        case 'ethics': return loadEthics();
        case 'cross-analysis': return loadCrossAnalysis();
        case 'methodology': return; // Static content
    }
}

// =========================================================
// 1. Visão Geral
// =========================================================

async function loadOverview() {
    showLoading('chart-overview-bars');
    showLoading('chart-overview-ranking');

    const data = await fetchAPI('/saeb/overview');
    if (!data) return;

    // KPIs
    const alunos = data.alunos_por_serie || [];
    const totalAlunos = alunos.reduce((s, r) => s + (r.total_alunos || 0), 0);
    document.getElementById('kpi-total-alunos').textContent = fmtInt(totalAlunos);

    const escolas = data.escolas || {};
    document.getElementById('kpi-total-escolas').textContent = fmtInt(escolas.total_escolas);

    const serieAtual = alunos.find(r => r.serie === state.serie);
    document.getElementById('kpi-media-lp').textContent = fmtNum(serieAtual?.media_lp);
    document.getElementById('kpi-media-mt').textContent = fmtNum(serieAtual?.media_mt);

    // Gráfico de barras: médias por série
    if (alunos.length > 0) {
        renderChart('chart-overview-bars', {
            tooltip: {
                trigger: 'axis',
                formatter: params => params.map(p =>
                    `<strong>${p.seriesName}</strong>: ${tooltipVal(p.value)} pts`
                ).join('<br>'),
            },
            legend: { data: ['Língua Portuguesa', 'Matemática'], top: 0 },
            grid: { top: 35 },
            xAxis: { type: 'category', data: alunos.map(s => s.serie) },
            yAxis: { type: 'value', name: 'Proficiência (escala SAEB)' },
            series: [
                {
                    name: 'Língua Portuguesa',
                    type: 'bar',
                    data: alunos.map(s => s.media_lp),
                    itemStyle: { color: gradientBar(COLORS.primary), borderRadius: [4, 4, 0, 0] },
                    label: { show: true, position: 'top', formatter: p => tooltipVal(p.value), fontSize: 11 },
                    barMaxWidth: 50,
                },
                {
                    name: 'Matemática',
                    type: 'bar',
                    data: alunos.map(s => s.media_mt),
                    itemStyle: { color: gradientBar(COLORS.secondary), borderRadius: [4, 4, 0, 0] },
                    label: { show: true, position: 'top', formatter: p => tooltipVal(p.value), fontSize: 11 },
                    barMaxWidth: 50,
                },
            ],
        });
        renderExplanation('chart-overview-bars');
    }

    // Ranking de UFs
    const ranking = await fetchAPI('/saeb/proficiency/ranking', {
        serie: state.serie, disciplina: state.disciplina,
    });
    if (ranking && ranking.data && ranking.data.length > 0) {
        const sorted = ranking.data;
        renderChart('chart-overview-ranking', {
            tooltip: {
                trigger: 'axis',
                formatter: params => `<strong>${params[0].name}</strong>: ${tooltipVal(params[0].value)} pts`,
            },
            grid: { top: 35, bottom: 30 },
            xAxis: { type: 'category', data: sorted.map(r => r.uf_sigla), axisLabel: { rotate: 0, fontSize: 10 } },
            yAxis: { type: 'value', name: 'Proficiência média' },
            series: [{
                type: 'bar',
                data: sorted.map(r => ({
                    value: r.media_proficiencia,
                    itemStyle: {
                        color: r.uf_sigla === 'RJ' ? gradientBar(COLORS.accent) : gradientBar(COLORS.teal, 0.65),
                        borderRadius: [3, 3, 0, 0],
                    },
                })),
                barMaxWidth: 28,
            }],
        });
        renderExplanation('chart-overview-ranking');
    } else {
        showEmpty('chart-overview-ranking');
    }
}

// =========================================================
// 2. Proficiência
// =========================================================

async function loadProficiency() {
    showLoading('chart-prof-distribution');
    showLoading('chart-prof-levels');
    showLoading('chart-prof-compare');

    const params = { serie: state.serie, disciplina: state.disciplina };

    // Aba Comparação: RJ vs Sudeste vs Brasil
    const comparison = await fetchAPI('/saeb/proficiency/comparison');
    if (comparison) {
        const findMedia = (arr) => {
            const filtered = arr.filter(r =>
                r.serie === state.serie && r.disciplina === state.disciplina
            );
            const total = filtered.find(r => r.rede === '' || r.rede === 'total');
            if (total) return total.media_proficiencia;
            if (filtered.length === 0) return null;
            const totalPesos = filtered.reduce((s, r) => s + (r.n_alunos || 1), 0);
            return filtered.reduce((s, r) =>
                s + (r.media_proficiencia || 0) * (r.n_alunos || 1), 0
            ) / totalPesos;
        };

        const rjMedia = findMedia(comparison.rj || []);
        const sudMedia = findMedia(comparison.sudeste || []);
        const brMedia = findMedia(comparison.brasil || []);

        if (rjMedia != null) {
            const labels = ['RJ', 'Sudeste', 'Brasil'];
            const values = [rjMedia, sudMedia, brMedia];
            const colors = [COLORS.accent, COLORS.teal, COLORS.primary];
            renderChart('chart-prof-compare', {
                tooltip: { trigger: 'axis', formatter: params => `<strong>${params[0].name}</strong>: ${tooltipVal(params[0].value)} pts` },
                xAxis: { type: 'category', data: labels },
                yAxis: { type: 'value', name: 'Proficiência média' },
                series: [{
                    type: 'bar',
                    data: values.map((v, i) => ({
                        value: v,
                        itemStyle: { color: gradientBar(colors[i]), borderRadius: [4, 4, 0, 0] },
                    })),
                    label: { show: true, position: 'top', formatter: p => tooltipVal(p.value), fontSize: 12 },
                    barMaxWidth: 70,
                }],
            });
            renderExplanation('chart-prof-compare');
        }
    }

    // Aba Distribuição
    const profData = await fetchAPI('/saeb/proficiency', params);
    if (profData && profData.data && profData.data.length > 0) {
        const sorted = [...profData.data].sort((a, b) => a.media_proficiencia - b.media_proficiencia);
        renderChart('chart-prof-distribution', {
            tooltip: { trigger: 'axis', formatter: params => `<strong>${params[0].name}</strong>: ${tooltipVal(params[0].value)} pts` },
            xAxis: { type: 'category', data: sorted.map(r => r.uf_sigla), axisLabel: { fontSize: 10 } },
            yAxis: { type: 'value', name: 'Proficiência média' },
            series: [{
                type: 'bar',
                data: sorted.map(r => ({
                    value: r.media_proficiencia,
                    itemStyle: {
                        color: r.uf_sigla === 'RJ' ? gradientBar(COLORS.accent) : gradientBar(COLORS.primary, 0.5),
                        borderRadius: [3, 3, 0, 0],
                    },
                })),
                barMaxWidth: 28,
            }],
        });
        renderExplanation('chart-prof-distribution');
    } else {
        showEmpty('chart-prof-distribution');
    }

    // Aba Níveis
    const levels = await fetchAPI('/saeb/proficiency/levels', { scope: 'rj' });
    if (levels && levels.data && levels.data.length > 0) {
        const row = levels.data[0];
        const disc = state.disciplina.toLowerCase();
        const serieKey = state.serie === '34EM' ? '34em' : state.serie.toLowerCase().replace('ef', '');
        const prefix = 'nivel_';
        const suffix = `_${disc}${serieKey}`;
        const niveis = [];
        for (const [key, val] of Object.entries(row)) {
            if (key.startsWith(prefix) && key.endsWith(suffix)) {
                const nivel = parseInt(key.replace(prefix, '').replace(suffix, ''));
                if (!isNaN(nivel) && val != null) niveis.push({ nivel, percentual: val });
            }
        }

        if (niveis.length > 0) {
            niveis.sort((a, b) => a.nivel - b.nivel);
            const nivelColors = niveis.map(n => {
                if (n.nivel <= 2) return COLORS.accent;
                if (n.nivel <= 4) return COLORS.secondary;
                if (n.nivel <= 6) return COLORS.teal;
                return COLORS.primary;
            });
            renderChart('chart-prof-levels', {
                tooltip: { trigger: 'axis', formatter: params => `Nível ${params[0].name}: <strong>${tooltipVal(params[0].value)}%</strong> dos alunos` },
                xAxis: { type: 'category', data: niveis.map(n => `Nível ${n.nivel}`) },
                yAxis: { type: 'value', name: '% de alunos' },
                series: [{
                    type: 'bar',
                    data: niveis.map((n, i) => ({
                        value: n.percentual,
                        itemStyle: { color: gradientBar(nivelColors[i]), borderRadius: [4, 4, 0, 0] },
                    })),
                    label: { show: true, position: 'top', formatter: p => tooltipVal(p.value) + '%', fontSize: 11 },
                    barMaxWidth: 55,
                }],
            });
            renderExplanation('chart-prof-levels');
        } else {
            showEmpty('chart-prof-levels', 'Níveis não disponíveis para esta série/disciplina');
        }
    } else {
        showEmpty('chart-prof-levels');
    }
}

// =========================================================
// 3. Equidade
// =========================================================

async function loadEquity() {
    showLoading('chart-eq-gap');
    showLoading('chart-eq-inse');
    showLoading('chart-eq-location');

    const params = { serie: state.serie, disciplina: state.disciplina };

    // Gap pública vs privada
    const gap = await fetchAPI('/saeb/equity/gap', params);
    if (gap && gap.data && gap.data.length > 0) {
        const item = gap.data.find(g =>
            g.serie === state.serie && g.disciplina === state.disciplina
        ) || gap.data[0];

        if (item.media_publica != null && item.media_privada != null) {
            renderChart('chart-eq-gap', {
                tooltip: { trigger: 'axis', formatter: params => `<strong>${params[0].name}</strong>: ${tooltipVal(params[0].value)} pts` },
                graphic: [statAnnotation(`Lacuna: ${fmtNum(item.gap)} pontos`)],
                xAxis: { type: 'category', data: ['Pública', 'Privada'] },
                yAxis: { type: 'value', name: 'Proficiência média' },
                series: [{
                    type: 'bar',
                    data: [
                        { value: item.media_publica, itemStyle: { color: gradientBar(COLORS.primary), borderRadius: [4, 4, 0, 0] } },
                        { value: item.media_privada, itemStyle: { color: gradientBar(COLORS.secondary), borderRadius: [4, 4, 0, 0] } },
                    ],
                    label: { show: true, position: 'top', formatter: p => tooltipVal(p.value), fontSize: 12 },
                    barMaxWidth: 80,
                }],
            });
            renderExplanation('chart-eq-gap');
        } else {
            showEmpty('chart-eq-gap', 'Dados insuficientes para comparação pública/privada');
        }
    } else {
        showEmpty('chart-eq-gap');
    }

    // INSE
    const inse = await fetchAPI('/saeb/equity/inse');
    if (inse && inse.data && inse.data.length > 0) {
        const filtered = inse.data.filter(i =>
            i.serie === state.serie && i.disciplina === state.disciplina
        );
        if (filtered.length > 0) {
            filtered.sort((a, b) => a.nivel_inse - b.nivel_inse);
            renderChart('chart-eq-inse', {
                tooltip: { trigger: 'axis', formatter: params => `INSE ${params[0].name}: <strong>${tooltipVal(params[0].value)}</strong> pts` },
                xAxis: { type: 'category', data: filtered.map(i => `Nível ${i.nivel_inse}`) },
                yAxis: { type: 'value', name: 'Proficiência média' },
                series: [{
                    type: 'bar',
                    data: filtered.map((i, idx) => ({
                        value: i.media_proficiencia,
                        itemStyle: {
                            color: gradientBar(COLORS.gradient[idx % COLORS.gradient.length]),
                            borderRadius: [4, 4, 0, 0],
                        },
                    })),
                    label: { show: true, position: 'top', formatter: p => tooltipVal(p.value), fontSize: 11 },
                    barMaxWidth: 50,
                }],
            });
            renderExplanation('chart-eq-inse');
        } else {
            showEmpty('chart-eq-inse', 'Sem dados INSE para esta série/disciplina');
        }
    } else {
        showEmpty('chart-eq-inse');
    }

    showEmpty('chart-eq-location', 'Análise por localização (urbana/rural) em construção');
}

// =========================================================
// 4. Tecnologia (TIC)
// =========================================================

async function loadTechnology() {
    showLoading('chart-tech-infra');
    showLoading('chart-tech-ai');
    showLoading('chart-tech-training');
    showLoading('chart-tech-privacy');

    const [infra, ai, training, privacy] = await Promise.all([
        fetchAPI('/tic/infrastructure'),
        fetchAPI('/tic/ai'),
        fetchAPI('/tic/teacher-training'),
        fetchAPI('/tic/privacy'),
    ]);

    _plotTicGroup('chart-tech-infra', infra, COLORS.primary);
    _plotTicGroup('chart-tech-ai', ai, COLORS.accent);
    _plotTicGroup('chart-tech-training', training, COLORS.green);
    _plotTicGroup('chart-tech-privacy', privacy, COLORS.purple);
}

function _plotTicGroup(elementId, response, color) {
    if (!response || !response.data || response.data.length === 0) {
        showEmpty(elementId, response?.message || 'Dados TIC não disponíveis');
        return;
    }

    const filtered = response.data.filter(d =>
        d.tipo === 'proporcao' && d.valor_corte === 'TOTAL'
    );
    if (filtered.length === 0) {
        showEmpty(elementId, 'Sem dados de proporção para este grupo');
        return;
    }

    const byIndicator = {};
    for (const d of filtered) {
        if (!(d.indicador in byIndicator)) byIndicator[d.indicador] = d.valor;
    }

    const indicators = Object.keys(byIndicator).sort();
    const values = indicators.map(i => byIndicator[i]);

    renderChart(elementId, {
        tooltip: { trigger: 'axis', formatter: params => `<strong>${params[0].name}</strong>: ${tooltipVal(params[0].value)}%` },
        xAxis: { type: 'category', data: indicators },
        yAxis: { type: 'value', name: 'Proporção (%)', max: 105 },
        series: [{
            type: 'bar',
            data: values.map(v => ({
                value: v,
                itemStyle: { color: gradientBar(color), borderRadius: [4, 4, 0, 0] },
            })),
            label: { show: true, position: 'top', formatter: p => tooltipVal(p.value) + '%', fontSize: 10 },
            barMaxWidth: 45,
        }],
    });
    renderExplanation(elementId);
}

// =========================================================
// 5. Professores
// =========================================================

async function loadTeachers() {
    showLoading('chart-teach-profile');
    showLoading('chart-teach-practices');
    showLoading('chart-teach-infra');
    showLoading('chart-teach-corr');

    const [genero, tech, recursos, formacao] = await Promise.all([
        fetchAPI('/saeb/questionnaire/professor', { questao: 'TX_Q001' }),
        fetchAPI('/saeb/questionnaire/professor', { questao: 'TX_Q029' }),
        fetchAPI('/saeb/questionnaire/professor', { questao: 'TX_Q069' }),
        fetchAPI('/saeb/teachers/formation'),
    ]);

    _plotQuestionnaire('chart-teach-profile', genero, 'Gênero dos Professores (RJ)', COLORS.primary);
    _plotQuestionnaire('chart-teach-practices', tech, 'Uso de Tecnologia em Aula', COLORS.secondary);
    _plotQuestionnaire('chart-teach-infra', recursos, 'Recursos Tecnológicos na Escola', COLORS.teal);

    // Correlações: formação docente vs desempenho
    if (formacao && formacao.data && formacao.data.length > 0) {
        const rows = formacao.data.filter(r =>
            r.pc_formacao_docente_inicial != null && r.media_5ef_lp != null
        );
        if (rows.length > 0) {
            renderChart('chart-teach-corr', {
                tooltip: {
                    trigger: 'item',
                    formatter: p => `Formação: ${tooltipVal(p.value[0], 0)}%<br>LP 5EF: ${tooltipVal(p.value[1])} pts`,
                },
                xAxis: { type: 'value', name: '% Formação Adequada', nameLocation: 'center', nameGap: 30 },
                yAxis: { type: 'value', name: 'Proficiência LP 5EF' },
                series: [{
                    type: 'scatter',
                    data: rows.map(r => [r.pc_formacao_docente_inicial, r.media_5ef_lp]),
                    symbolSize: 8,
                    itemStyle: { color: COLORS.primary, opacity: 0.55 },
                    emphasis: { itemStyle: { opacity: 0.9, shadowBlur: 4, shadowColor: 'rgba(0,0,0,0.2)' } },
                }],
            });
            renderExplanation('chart-teach-corr');
        } else {
            showEmpty('chart-teach-corr', 'Dados insuficientes para correlação');
        }
    } else {
        showEmpty('chart-teach-corr');
    }
}

function _plotQuestionnaire(elementId, response, title, color) {
    if (!response || !response.data || response.data.length === 0) {
        showEmpty(elementId, 'Sem dados para esta questão');
        return;
    }

    const rows = response.data;
    const total = rows.reduce((s, r) => s + r.contagem, 0);

    renderChart(elementId, {
        title: { text: title, left: 'center', top: 0, textStyle: { fontSize: 13, fontWeight: 600 } },
        tooltip: {
            trigger: 'axis',
            formatter: params => `${params[0].name}<br>Contagem: <strong>${fmtInt(params[0].value)}</strong> (${tooltipVal((params[0].value / total) * 100)}%)`,
        },
        grid: { top: 40 },
        xAxis: { type: 'category', data: rows.map(r => r.resposta), axisLabel: { fontSize: 10.5 } },
        yAxis: { type: 'value', name: 'Contagem' },
        series: [{
            type: 'bar',
            data: rows.map(r => ({
                value: r.contagem,
                itemStyle: { color: gradientBar(color || COLORS.primary), borderRadius: [4, 4, 0, 0] },
            })),
            barMaxWidth: 50,
        }],
    });
}

// =========================================================
// 6. Questionários
// =========================================================

async function loadQuestionnaires() {
    const dataset = document.getElementById('quest-dataset').value;
    const data = await fetchAPI(`/saeb/questionnaire/${dataset}`);
    if (data && data.data) {
        const questoes = [...new Set(data.data.map(r => r.questao))].sort();
        const select = document.getElementById('quest-question');
        select.innerHTML = '<option value="">Selecione uma questão...</option>';
        questoes.forEach(q => {
            const opt = document.createElement('option');
            opt.value = q;
            opt.textContent = q;
            select.appendChild(opt);
        });
    }
}

function renderQuestionnaireChart(dataset, questao) {
    return async function () {
        if (!questao) return;
        showLoading('chart-questionnaire');
        const data = await fetchAPI(`/saeb/questionnaire/${dataset}`, { questao });
        if (data && data.data && data.data.length > 0) {
            const rows = data.data;
            const total = rows.reduce((s, r) => s + r.contagem, 0);
            renderChart('chart-questionnaire', {
                tooltip: {
                    trigger: 'axis',
                    formatter: params => {
                        const r = rows[params[0].dataIndex];
                        const pct = ((r.contagem / total) * 100).toFixed(1);
                        return `${params[0].name}<br>Contagem: <strong>${fmtInt(params[0].value)}</strong> (${pct}%)`;
                    },
                },
                xAxis: { type: 'category', data: rows.map(r => r.resposta), name: 'Resposta' },
                yAxis: { type: 'value', name: 'Contagem' },
                series: [{
                    type: 'bar',
                    data: rows.map((r, i) => ({
                        value: r.contagem,
                        itemStyle: { color: gradientBar(COLORS.palette[i % COLORS.palette.length]), borderRadius: [4, 4, 0, 0] },
                    })),
                    barMaxWidth: 50,
                }],
            });
        } else {
            showEmpty('chart-questionnaire', 'Sem dados para esta questão');
        }
    };
}

// =========================================================
// 7. Ética e IA
// =========================================================

async function loadEthics() {
    showLoading('chart-ethics-tech');
    showLoading('chart-ethics-digital');
    showLoading('chart-ethics-teachers');
    showLoading('chart-ethics-dimensions');

    _loadEthicsCrossFindings();

    const [ai, gap, training, privacy] = await Promise.all([
        fetchAPI('/tic/ai'),
        fetchAPI('/saeb/equity/gap', { serie: state.serie, disciplina: state.disciplina }),
        fetchAPI('/tic/teacher-training'),
        fetchAPI('/tic/privacy'),
    ]);

    // IA nas escolas
    if (ai && ai.data && ai.data.length > 0) {
        const filtered = ai.data.filter(d => d.tipo === 'proporcao' && d.valor_corte === 'TOTAL');
        const byInd = {};
        for (const d of filtered) { if (!(d.indicador in byInd)) byInd[d.indicador] = d.valor; }
        const labels = { 'E4A': 'Biometria', 'E4B': 'Reconhec. Facial', 'E5': 'Analytics', 'E6': 'Sist. IA', 'F6': 'Chatbot' };
        const inds = Object.keys(byInd).sort();
        renderChart('chart-ethics-tech', {
            tooltip: { trigger: 'axis', formatter: p => `<strong>${p[0].name}</strong>: ${tooltipVal(p[0].value)}%` },
            xAxis: { type: 'category', data: inds.map(i => labels[i] || i) },
            yAxis: { type: 'value', name: 'Proporção (%)', max: 105 },
            series: [{
                type: 'bar',
                data: inds.map(i => ({ value: byInd[i], itemStyle: { color: gradientBar(COLORS.accent), borderRadius: [4, 4, 0, 0] } })),
                label: { show: true, position: 'top', formatter: p => tooltipVal(p.value) + '%', fontSize: 11 },
                barMaxWidth: 55,
            }],
        });
        renderExplanation('chart-ethics-tech');
    } else {
        showEmpty('chart-ethics-tech', 'Dados TIC de IA não disponíveis');
    }

    // Desigualdade Digital
    if (gap && gap.data) {
        const items = gap.data.filter(g => g.media_publica != null && g.media_privada != null);
        if (items.length > 0) {
            renderChart('chart-ethics-digital', {
                tooltip: { trigger: 'axis', formatter: p => `<strong>${p[0].name}</strong>: lacuna de ${tooltipVal(p[0].value)} pts` },
                graphic: [statAnnotation('Diferença: Privada − Pública', { color: '#666', fontSize: 11 })],
                xAxis: { type: 'category', data: items.map(i => `${i.serie} ${i.disciplina}`) },
                yAxis: { type: 'value', name: 'Lacuna (pontos)' },
                series: [{
                    type: 'bar',
                    data: items.map(i => ({ value: i.gap, itemStyle: { color: gradientBar(COLORS.accent), borderRadius: [4, 4, 0, 0] } })),
                    label: { show: true, position: 'top', formatter: p => tooltipVal(p.value), fontSize: 11 },
                    barMaxWidth: 50,
                }],
            });
            renderExplanation('chart-ethics-digital');
        } else {
            showEmpty('chart-ethics-digital', 'Sem dados de gap');
        }
    } else {
        showEmpty('chart-ethics-digital');
    }

    // Preparação Docente
    if (training && training.data && training.data.length > 0) {
        const filtered = training.data.filter(d => d.tipo === 'proporcao' && d.valor_corte === 'TOTAL');
        const byInd = {};
        for (const d of filtered) { if (!(d.indicador in byInd)) byInd[d.indicador] = d.valor; }
        const labels = { 'J1': 'Programação', 'J2': 'Robótica', 'J3': 'Uso pedagóg. TIC', 'J4': 'Segurança online' };
        const inds = Object.keys(byInd).sort();
        renderChart('chart-ethics-teachers', {
            tooltip: { trigger: 'axis', formatter: p => `<strong>${p[0].name}</strong>: ${tooltipVal(p[0].value)}%` },
            xAxis: { type: 'category', data: inds.map(i => labels[i] || i) },
            yAxis: { type: 'value', name: 'Proporção de escolas (%)', max: 105 },
            series: [{
                type: 'bar',
                data: inds.map(i => ({ value: byInd[i], itemStyle: { color: gradientBar(COLORS.green), borderRadius: [4, 4, 0, 0] } })),
                label: { show: true, position: 'top', formatter: p => tooltipVal(p.value) + '%', fontSize: 11 },
                barMaxWidth: 55,
            }],
        });
        renderExplanation('chart-ethics-teachers');
    } else {
        showEmpty('chart-ethics-teachers', 'Dados de formação docente TIC não disponíveis');
    }

    // Dimensões Éticas: privacidade
    if (privacy && privacy.data && privacy.data.length > 0) {
        const filtered = privacy.data.filter(d => d.tipo === 'proporcao' && d.valor_corte === 'TOTAL');
        const byInd = {};
        for (const d of filtered) { if (!(d.indicador in byInd)) byInd[d.indicador] = d.valor; }
        const labels = { 'H1': 'Polít. privacidade', 'H3': 'Debate privacidade', 'H4': 'Consent. dados', 'H5': 'Proteção dados', 'H6': 'Não adoção', 'H7': 'Preocup. privac.' };
        const inds = Object.keys(byInd).sort();
        renderChart('chart-ethics-dimensions', {
            tooltip: { trigger: 'axis', formatter: p => `<strong>${p[0].name}</strong>: ${tooltipVal(p[0].value)}%` },
            xAxis: { type: 'category', data: inds.map(i => labels[i] || i) },
            yAxis: { type: 'value', name: 'Proporção (%)', max: 105 },
            series: [{
                type: 'bar',
                data: inds.map(i => ({ value: byInd[i], itemStyle: { color: gradientBar(COLORS.purple), borderRadius: [4, 4, 0, 0] } })),
                label: { show: true, position: 'top', formatter: p => tooltipVal(p.value) + '%', fontSize: 11 },
                barMaxWidth: 55,
            }],
        });
        renderExplanation('chart-ethics-dimensions');
    } else {
        showEmpty('chart-ethics-dimensions', 'Dados de privacidade TIC não disponíveis');
    }
}

async function _loadEthicsCrossFindings() {
    const el = document.getElementById('ethics-cross-findings');
    if (!el) return;

    const data = await fetchAPI('/cross/summary', {
        serie: state.serie, disciplina: state.disciplina,
    });

    if (!data || !data.analyses || data.analyses.length === 0) {
        el.innerHTML = '<p class="text-muted">Dados de cruzamento não disponíveis. Execute a pré-computação primeiro.</p>';
        return;
    }

    const significant = data.analyses.filter(a => a.p_value != null && a.p_value < 0.05);
    const topBinary = data.analyses.find(a => a.cohens_d != null);

    let html = '<div class="row g-2">';
    html += `<div class="col-md-3"><div class="border rounded p-2 text-center">
        <div class="fw-bold" style="font-size:1.5em; color: var(--clr-primary)">${data.analyses.length}</div>
        <div class="text-muted small">Variáveis testadas</div>
    </div></div>`;
    html += `<div class="col-md-3"><div class="border rounded p-2 text-center">
        <div class="fw-bold" style="font-size:1.5em; color: var(--clr-green)">${significant.length}</div>
        <div class="text-muted small">Significativas (${statTerm('p-valor', 'p<0.05')})</div>
    </div></div>`;
    if (topBinary) {
        html += `<div class="col-md-3"><div class="border rounded p-2 text-center">
            <div class="fw-bold" style="font-size:1.5em; color: var(--clr-accent)">d = ${fmtNum(topBinary.cohens_d, 3)}</div>
            <div class="text-muted small">Maior ${statTerm('Tamanho de efeito', 'efeito')}: ${topBinary.label}</div>
        </div></div>`;
    }
    html += `<div class="col-md-3"><div class="border rounded p-2 text-center">
        <div class="fw-bold" style="font-size:1.5em; color: var(--clr-secondary)">${fmtNum(data.bonferroni_alpha, 4)}</div>
        <div class="text-muted small">Alfa ${statTerm('Bonferroni')}</div>
    </div></div>`;
    html += '</div>';
    html += '<p class="mt-2 mb-0 text-muted small">Veja a página <strong>8. Cruzamentos Tech</strong> para análises detalhadas e controle por INSE.</p>';
    el.innerHTML = html;
    initStatPopovers();
}

// =========================================================
// 8. Cruzamentos Tech x Desempenho
// =========================================================

async function loadCrossAnalysis() {
    _loadCrossStudentTab();
    _loadCrossSchoolTab();
    _loadCrossTeacherTab();
    _loadCrossOverviewTab();
    _loadCrossInseTab();
}

async function _loadCrossStudentTab() {
    showLoading('chart-cross-computers');
    showLoading('chart-cross-wifi');
    showLoading('chart-cross-phones');
    showLoading('chart-cross-index');

    const params = { serie: state.serie, disciplina: state.disciplina, use_precomputed: true };

    const [computers, wifi, phones, index] = await Promise.all([
        fetchAPI('/cross/student-tech', { ...params, variable: 'TX_RESP_Q12b' }),
        fetchAPI('/cross/student-tech', { ...params, variable: 'TX_RESP_Q13b' }),
        fetchAPI('/cross/student-tech', { ...params, variable: 'TX_RESP_Q12g' }),
        fetchAPI('/cross/digital-index', params),
    ]);

    _plotCrossGap('chart-cross-computers', computers);
    _plotCrossGap('chart-cross-wifi', wifi);
    _plotCrossGap('chart-cross-phones', phones);

    // Digital index
    if (index && index.by_level && index.by_level.length > 0) {
        renderChart('chart-cross-index', {
            tooltip: {
                trigger: 'axis',
                formatter: p => `Índice ${p[0].name}: <strong>${tooltipVal(p[0].value)}</strong> pts<br>n = ${fmtInt(index.by_level[p[0].dataIndex]?.n)}`,
            },
            graphic: index.correlation ? [statAnnotation(
                `${statTerm('Correlação', 'r')} = ${fmtNum(index.correlation.pearson_r, 3)}`,
                { left: 15, top: 8, color: COLORS.accent }
            )] : [],
            xAxis: { type: 'category', data: index.by_level.map(l => l.index), name: 'Índice Digital (0-8)' },
            yAxis: { type: 'value', name: 'Proficiência média' },
            series: [{
                type: 'line',
                data: index.by_level.map(l => l.mean),
                smooth: true,
                symbol: 'circle',
                symbolSize: 9,
                lineStyle: { width: 3, color: COLORS.primary },
                itemStyle: { color: COLORS.primary },
                areaStyle: {
                    color: {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(78,121,167,0.25)' },
                            { offset: 1, color: 'rgba(78,121,167,0.02)' },
                        ],
                    },
                },
            }],
        });
        renderExplanation('chart-cross-index');
    } else if (index && index.faixas && index.faixas.length > 0) {
        _plotCrossGap('chart-cross-index', { groups: index.faixas.map(f => ({ ...f, code: f.label })) });
    } else {
        showEmpty('chart-cross-index');
    }
}

async function _loadCrossSchoolTab() {
    showLoading('chart-cross-q194');
    showLoading('chart-cross-q219');
    showLoading('chart-cross-q035');
    showLoading('chart-cross-q036');

    const params = { serie: state.serie, disciplina: state.disciplina };

    const [q194, q219, q035, q036] = await Promise.all([
        fetchAPI('/cross/director-tech', { ...params, variable: 'TX_Q194' }),
        fetchAPI('/cross/director-tech', { ...params, variable: 'TX_Q219' }),
        fetchAPI('/cross/director-tech', { ...params, variable: 'TX_Q035' }),
        fetchAPI('/cross/director-tech', { ...params, variable: 'TX_Q036' }),
    ]);

    _plotCrossGap('chart-cross-q194', q194);
    _plotCrossGap('chart-cross-q219', q219);
    _plotCrossGap('chart-cross-q035', q035);
    _plotCrossGap('chart-cross-q036', q036);
}

async function _loadCrossTeacherTab() {
    showLoading('chart-cross-q029');
    showLoading('chart-cross-q037');

    const params = { serie: state.serie, disciplina: state.disciplina };

    const [q029, q037] = await Promise.all([
        fetchAPI('/cross/teacher-tech', { ...params, variable: 'TX_Q029' }),
        fetchAPI('/cross/teacher-tech', { ...params, variable: 'TX_Q037' }),
    ]);

    _plotCrossGap('chart-cross-q029', q029);
    _plotCrossGap('chart-cross-q037', q037);
}

async function _loadCrossOverviewTab() {
    showLoading('table-cross-summary');
    showLoading('chart-cross-forest');

    const data = await fetchAPI('/cross/summary', {
        serie: state.serie, disciplina: state.disciplina,
    });

    if (!data || !data.analyses || data.analyses.length === 0) {
        showEmpty('table-cross-summary', 'Dados de resumo não disponíveis');
        showEmpty('chart-cross-forest');
        return;
    }

    const analyses = data.analyses;

    // Summary table with stat term popovers
    let html = '<div class="table-responsive"><table class="table table-sm table-striped">';
    html += `<thead><tr><th>Nível</th><th>Variável</th><th>Tipo</th><th>${statTerm('p-valor')}</th><th>${statTerm("Cohen's d", "Cohen's d / F")}</th><th>Sig.</th></tr></thead><tbody>`;
    for (const a of analyses) {
        const pVal = a.p_value != null ? (a.p_value < 0.001 ? '<0.001' : fmtNum(a.p_value, 4)) : '—';
        const effect = a.cohens_d != null ? `d = ${fmtNum(a.cohens_d, 3)}` :
            (a.f_stat != null ? `F = ${fmtNum(a.f_stat, 2)}` : '—');
        const sig = a.p_value != null && a.p_value < (data.bonferroni_alpha || 0.05);
        const sigBadge = sig ? '<span class="badge bg-success">Sim</span>' :
            (a.p_value != null && a.p_value < 0.05 ? '<span class="badge bg-warning text-dark">*</span>' :
            '<span class="badge bg-secondary">Não</span>');
        const levelLabel = { aluno: 'Aluno', diretor: 'Escola', professor: 'Professor' }[a.level] || a.level;
        html += `<tr><td>${levelLabel}</td><td>${a.label}</td><td>${a.test_type || '—'}</td>`;
        html += `<td>${pVal}</td><td>${effect}</td><td>${sigBadge}</td></tr>`;
    }
    html += '</tbody></table></div>';
    html += `<p class="small text-muted mt-2">${data.note || ''}</p>`;
    document.getElementById('table-cross-summary').innerHTML = html;
    initStatPopovers();

    // Forest plot
    const withEffect = analyses.filter(a => a.cohens_d != null);
    if (withEffect.length > 0) {
        // Classify effect sizes for annotation
        const effectLabel = d => {
            const abs = Math.abs(d);
            if (abs < 0.2) return 'Insignificante';
            if (abs < 0.5) return 'Pequeno';
            if (abs < 0.8) return 'Médio';
            return 'Grande';
        };

        renderChart('chart-cross-forest', {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: params => {
                    const p = params[0];
                    return `<strong>${p.name}</strong><br>${statTerm("Cohen's d", 'd')} = ${tooltipVal(p.value, 3)}<br>Efeito: ${effectLabel(p.value)}`;
                },
            },
            grid: { top: 20, left: 200, right: 60, bottom: 40 },
            xAxis: {
                type: 'value',
                name: "Cohen's d (tamanho de efeito)",
                nameLocation: 'center',
                nameGap: 28,
            },
            yAxis: {
                type: 'category',
                data: withEffect.map(a => a.label),
                axisLabel: { fontSize: 11 },
            },
            series: [{
                type: 'bar',
                data: withEffect.map(a => ({
                    value: a.cohens_d,
                    itemStyle: {
                        color: a.cohens_d >= 0 ? gradientBar(COLORS.green) : gradientBar(COLORS.accent),
                        borderRadius: a.cohens_d >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
                    },
                })),
                label: {
                    show: true,
                    position: 'right',
                    formatter: p => `d = ${tooltipVal(p.value, 3)} (${effectLabel(p.value)})`,
                    fontSize: 10,
                    color: '#718096',
                },
                barMaxWidth: 18,
            }],
            markLine: {
                silent: true,
                data: [{ xAxis: 0 }],
                lineStyle: { color: '#999', type: 'dashed' },
                label: { show: false },
            },
        });
        renderExplanation('chart-cross-forest');
    } else {
        showEmpty('chart-cross-forest', 'Sem efeitos binários (Cohen\'s d) para plotar');
    }
}

async function _loadCrossInseTab() {
    showLoading('chart-cross-wifi-inse');
    showLoading('chart-cross-index-inse');

    const params = { serie: state.serie, disciplina: state.disciplina, stratify_inse: true };

    const [wifi, index] = await Promise.all([
        fetchAPI('/cross/student-tech', { ...params, variable: 'TX_RESP_Q13b', use_precomputed: false }),
        fetchAPI('/cross/digital-index', params),
    ]);

    // WiFi by INSE
    if (wifi && wifi.by_inse && wifi.by_inse.length > 0) {
        const inseData = wifi.by_inse.map(inse => {
            const groups = inse.groups || [];
            const noWifi = groups.find(g => g.code === 'A');
            const yesWifi = groups.find(g => g.code === 'B');
            return {
                inse: inse.inse_level,
                no: noWifi?.mean, yes: yesWifi?.mean,
                gap: (yesWifi?.mean && noWifi?.mean) ? yesWifi.mean - noWifi.mean : null,
            };
        }).filter(d => d.gap != null);

        if (inseData.length > 0) {
            renderChart('chart-cross-wifi-inse', {
                tooltip: { trigger: 'axis' },
                legend: { data: ['Com Wi-Fi', 'Sem Wi-Fi'], top: 0 },
                grid: { top: 35, right: 15, left: 50 },
                xAxis: { type: 'category', data: inseData.map(d => `INSE ${d.inse}`) },
                yAxis: { type: 'value', name: 'Proficiência média' },
                series: [
                    {
                        name: 'Com Wi-Fi', type: 'bar',
                        data: inseData.map(d => d.yes),
                        itemStyle: { color: gradientBar(COLORS.primary), borderRadius: [4, 4, 0, 0] },
                        barMaxWidth: 22,
                    },
                    {
                        name: 'Sem Wi-Fi', type: 'bar',
                        data: inseData.map(d => d.no),
                        itemStyle: { color: gradientBar(COLORS.accent), borderRadius: [4, 4, 0, 0] },
                        barMaxWidth: 22,
                    },
                ],
            });
            renderExplanation('chart-cross-wifi-inse');
        } else {
            showEmpty('chart-cross-wifi-inse', 'Dados INSE insuficientes');
        }
    } else {
        showEmpty('chart-cross-wifi-inse');
    }

    // Digital index by INSE
    if (index && index.by_inse && index.by_inse.length > 0) {
        // Group flat rows by nivel_inse, then by faixa_digital
        const byInseMap = {};
        for (const row of index.by_inse) {
            const key = row.nivel_inse;
            if (!byInseMap[key]) byInseMap[key] = {};
            if (!byInseMap[key][row.faixa_digital]) {
                byInseMap[key][row.faixa_digital] = { total: 0, weighted: 0 };
            }
            byInseMap[key][row.faixa_digital].total += row.n_alunos;
            byInseMap[key][row.faixa_digital].weighted += row.media_proficiencia * row.n_alunos;
        }
        const inseKeys = Object.keys(byInseMap).map(Number).sort((a, b) => a - b);
        const bandColors = { 'Baixo': COLORS.accent, 'Medio': COLORS.secondary, 'Alto': COLORS.green };
        const traces = [];
        for (const band of ['Baixo', 'Medio', 'Alto']) {
            const yVals = [];
            for (const inse of inseKeys) {
                const entry = byInseMap[inse][band];
                yVals.push(entry && entry.total > 0 ? +(entry.weighted / entry.total).toFixed(1) : null);
            }
            if (yVals.some(v => v !== null)) {
                traces.push({
                    name: band, type: 'bar',
                    data: yVals,
                    itemStyle: { color: gradientBar(bandColors[band]), borderRadius: [4, 4, 0, 0] },
                    barMaxWidth: 18,
                });
            }
        }
        if (traces.length > 0) {
            renderChart('chart-cross-index-inse', {
                tooltip: { trigger: 'axis' },
                legend: { data: traces.map(t => t.name), top: 0 },
                grid: { top: 35, right: 15, left: 50 },
                xAxis: { type: 'category', data: inseKeys.map(k => `INSE ${k}`) },
                yAxis: { type: 'value', name: 'Proficiência média' },
                series: traces,
            });
            renderExplanation('chart-cross-index-inse');
        } else {
            showEmpty('chart-cross-index-inse', 'Dados INSE insuficientes');
        }
    } else {
        showEmpty('chart-cross-index-inse');
    }
}

function _plotCrossGap(elementId, response) {
    const groups = response?.groups || response?.overall?.groups || [];
    if (groups.length === 0) {
        showEmpty(elementId, 'Sem dados disponíveis');
        return;
    }

    const labels = groups.map(g => g.label || g.code);
    const values = groups.map(g => g.mean);
    const ns = groups.map(g => g.n);

    const barColors = groups.length === 2
        ? [COLORS.accent, COLORS.primary]
        : groups.map((_, i) => COLORS.gradient[i % COLORS.gradient.length]);

    // Build stat annotation
    const test = response?.test || response?.overall?.test;
    let annotationText = '';
    if (test) {
        const parts = [];
        if (test.gap != null) parts.push(`Gap: ${fmtNum(test.gap)} pts`);
        if (test.cohens_d != null) parts.push(`d = ${fmtNum(test.cohens_d, 3)}`);
        if (test.p_value != null) {
            const pStr = test.p_value < 0.001 ? '<0.001' : fmtNum(test.p_value, 4);
            parts.push(`p = ${pStr}`);
        }
        annotationText = parts.join('  |  ');
    }

    renderChart(elementId, {
        tooltip: {
            trigger: 'axis',
            formatter: params => {
                const idx = params[0].dataIndex;
                return `<strong>${params[0].name}</strong><br>Proficiência: ${tooltipVal(params[0].value)} pts<br>n = ${fmtInt(ns[idx])}`;
            },
        },
        graphic: annotationText ? [statAnnotation(annotationText, { fontSize: 11 })] : [],
        xAxis: { type: 'category', data: labels },
        yAxis: { type: 'value', name: 'Proficiência média' },
        series: [{
            type: 'bar',
            data: values.map((v, i) => ({
                value: v,
                itemStyle: { color: gradientBar(barColors[i]), borderRadius: [4, 4, 0, 0] },
            })),
            label: {
                show: true,
                position: 'top',
                formatter: p => `${tooltipVal(p.value)} (n=${fmtInt(ns[p.dataIndex])})`,
                fontSize: 10,
            },
            barMaxWidth: 55,
        }],
    });
    renderExplanation(elementId);
}
