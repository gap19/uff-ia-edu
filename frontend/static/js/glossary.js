/**
 * Dashboard IA e Educação — UFF
 * Glossário de termos estatísticos em PT-BR para audiência leiga
 */

const STAT_GLOSSARY = {
    'Cohen\'s d': 'Medida padronizada do tamanho do efeito. Indica se a diferença entre dois grupos é pequena (d ≈ 0,2), média (d ≈ 0,5) ou grande (d ≈ 0,8). Quanto maior o valor absoluto, maior a diferença prática entre os grupos.',

    'p-valor': 'Probabilidade de observar uma diferença tão grande ou maior por acaso, caso não exista diferença real. Valores abaixo de 0,05 são considerados estatisticamente significativos — ou seja, é improvável que a diferença tenha ocorrido por mero acaso.',

    'INSE': 'Índice de Nível Socioeconômico — indicador calculado pelo INEP a partir de respostas dos alunos sobre escolaridade dos pais, posse de bens e acesso a serviços. Varia de 1 (mais baixo) a 8 (mais alto). É o principal fator associado ao desempenho escolar no Brasil.',

    'Intervalo de confiança': 'Faixa de valores dentro da qual a verdadeira média da população provavelmente se encontra, com 95% de confiança. Intervalos mais estreitos indicam estimativas mais precisas.',

    'Tamanho de efeito': 'Quantifica a magnitude prática de uma diferença ou relação, independentemente do tamanho da amostra. Diferente do p-valor, que pode ser significativo só porque a amostra é muito grande.',

    'Correlação': 'Medida de quanto duas variáveis se movem juntas. Varia de -1 (relação inversa perfeita) a +1 (relação direta perfeita). Zero indica ausência de relação linear. Correlação NÃO implica que uma variável causa a outra.',

    'Bonferroni': 'Correção estatística usada quando múltiplos testes são realizados simultaneamente. Torna o critério de significância mais rigoroso (divide α pelo número de testes) para evitar falsos positivos por testagem excessiva.',

    'ANOVA': 'Análise de Variância — teste que compara as médias de três ou mais grupos simultaneamente. Indica se existe pelo menos uma diferença significativa entre os grupos, mas não identifica qual par difere.',

    'Pesos amostrais': 'Fatores de correção que garantem que cada aluno no SAEB represente adequadamente a parcela da população que ele retrata. Sem pesos, escolas grandes seriam sobre-representadas e estimativas ficariam enviesadas.',

    'Design effect': 'Fator de correção que leva em conta que alunos da mesma escola tendem a ter resultados similares. Sem este ajuste, os intervalos de confiança seriam artificialmente estreitos.',

    'Escala SAEB': 'Escala padronizada de proficiência que permite comparar o desempenho dos alunos ao longo do tempo e entre séries. A média nacional histórica é próxima de 250 para o 9º ano do Ensino Fundamental.',

    'Qui-quadrado': 'Teste estatístico que verifica se a distribuição observada de respostas entre categorias difere significativamente do que seria esperado ao acaso. Muito usado para variáveis categóricas (sim/não, A/B/C/D).',

    'Proficiência': 'Nota estimada do aluno na escala SAEB, calculada a partir das respostas aos itens da prova usando Teoria de Resposta ao Item (TRI). Não é uma nota simples de acertos — a TRI leva em conta a dificuldade e qualidade de cada questão.',

    'Estratificação': 'Técnica que divide a amostra em subgrupos (estratos) antes da análise. Aqui, usamos estratificação por INSE para verificar se o efeito da tecnologia persiste mesmo quando comparamos alunos de mesmo nível socioeconômico.',
};

/**
 * Envolve um termo estatístico em um <span> com popover Bootstrap.
 * @param {string} term - O termo a ser anotado (deve existir no STAT_GLOSSARY)
 * @param {string} [display] - Texto a exibir (opcional, default = term)
 * @returns {string} HTML com o span configurado para popover
 */
function statTerm(term, display) {
    const explanation = STAT_GLOSSARY[term];
    if (!explanation) return display || term;
    const escaped = explanation.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    return `<span class="stat-term" tabindex="0" data-bs-toggle="popover" data-bs-trigger="hover focus" data-bs-placement="top" data-bs-content="${escaped}" title="${display || term}">${display || term}</span>`;
}

/**
 * Inicializa todos os popovers de termos estatísticos na página.
 * Deve ser chamada após o conteúdo dinâmico ser inserido no DOM.
 */
function initStatPopovers() {
    document.querySelectorAll('.stat-term[data-bs-toggle="popover"]').forEach(el => {
        // Dispose existing popover to avoid duplicates
        const existing = bootstrap.Popover.getInstance(el);
        if (existing) existing.dispose();
        new bootstrap.Popover(el, { html: false, sanitize: true });
    });
}
