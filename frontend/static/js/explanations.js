/**
 * Dashboard IA e Educação — UFF
 * Interpretações em linguagem acessível para cada gráfico/seção
 */

const CHART_EXPLANATIONS = {
    // ── Visão Geral ──
    'chart-overview-bars': {
        title: 'Médias por série',
        text: 'Este gráfico mostra a nota média dos alunos do Rio de Janeiro em Língua Portuguesa e Matemática, separada por série escolar (5º ano, 9º ano e Ensino Médio). A escala SAEB permite comparar desempenhos entre séries diferentes — valores mais altos indicam maior domínio das habilidades avaliadas.',
    },
    'chart-overview-ranking': {
        title: 'Ranking nacional',
        text: 'Compara a proficiência média do RJ com os demais estados brasileiros. A barra destacada em vermelho é o Rio de Janeiro. Este ranking usa <strong>médias ponderadas</strong> pelos pesos amostrais do SAEB, o que garante que cada escola contribua proporcionalmente à parcela da população que representa.',
    },

    // ── Proficiência ──
    'chart-prof-distribution': {
        title: 'Distribuição por UF',
        text: 'Mostra como a proficiência média se distribui entre os estados. Permite identificar onde o RJ se posiciona no cenário nacional — próximo à mediana, acima ou abaixo dos demais.',
    },
    'chart-prof-levels': {
        title: 'Níveis de proficiência',
        text: 'Os alunos são classificados em níveis conforme suas notas. <strong>Níveis baixos (1-2)</strong> indicam domínio insuficiente das habilidades básicas. <strong>Níveis médios (3-5)</strong> representam domínio parcial. <strong>Níveis altos (6+)</strong> indicam domínio adequado ou avançado. A proporção em cada nível revela o quanto o sistema educacional está cumprindo seus objetivos.',
    },
    'chart-prof-compare': {
        title: 'RJ vs região e país',
        text: 'Compara diretamente a proficiência média do Rio de Janeiro com a média da região Sudeste e do Brasil. Diferenças maiores que 5-10 pontos na escala SAEB são consideradas pedagogicamente relevantes.',
    },

    // ── Equidade ──
    'chart-eq-gap': {
        title: 'Lacuna público-privada',
        text: 'Mostra a diferença de desempenho entre escolas públicas e privadas. Esta lacuna é um dos principais indicadores de <strong>desigualdade educacional</strong>. No Brasil, ela historicamente supera 40 pontos na escala SAEB — equivalente a quase 2 anos de aprendizado.',
    },
    'chart-eq-inse': {
        title: 'Efeito socioeconômico',
        text: 'O <strong>INSE</strong> (Índice Socioeconômico) é o fator que mais influencia o desempenho escolar no Brasil. Este gráfico mostra como a proficiência aumenta conforme o nível socioeconômico sobe. Entender este padrão é essencial para interpretar corretamente qualquer outra análise — incluindo o impacto da tecnologia.',
    },

    // ── Tecnologia ──
    'chart-tech-infra': {
        title: 'Infraestrutura digital',
        text: 'Dados da pesquisa TIC Educação 2023 (CETIC.br) sobre infraestrutura tecnológica nas escolas da região Sudeste. Cada barra representa a proporção de escolas que possuem determinado recurso. Estes dados são de nível regional — não estão disponíveis por estado individualmente.',
    },
    'chart-tech-ai': {
        title: 'IA nas escolas',
        text: 'Mostra a adoção de tecnologias baseadas em inteligência artificial e dados nas escolas. Inclui biometria, reconhecimento facial, sistemas analíticos e chatbots. A baixa adoção de IA contrasta com o rápido crescimento destas tecnologias no setor privado.',
    },
    'chart-tech-training': {
        title: 'Formação digital docente',
        text: 'Proporção de escolas que oferecem formação aos professores em tecnologias educacionais. A <strong>preparação docente</strong> é um fator crítico para o uso efetivo de tecnologia em sala de aula — sem formação adequada, equipamentos e softwares tendem a ser subutilizados.',
    },
    'chart-tech-privacy': {
        title: 'Políticas de privacidade',
        text: 'Indicadores de governança de dados e privacidade nas escolas. Com a LGPD (Lei Geral de Proteção de Dados) e o crescimento da IA educacional, estas políticas são fundamentais para proteger dados sensíveis de crianças e adolescentes.',
    },

    // ── Professores ──
    'chart-teach-profile': {
        title: 'Perfil docente',
        text: 'Distribuição das respostas dos professores do RJ a esta questão do questionário contextual do SAEB. Ajuda a traçar o perfil da força docente do estado.',
    },
    'chart-teach-corr': {
        title: 'Formação e desempenho',
        text: 'Cada ponto representa uma escola. O eixo horizontal mostra o percentual de professores com formação inicial adequada, e o eixo vertical mostra a proficiência média dos alunos. Se os pontos sobem da esquerda para a direita, há uma <strong>correlação positiva</strong> — escolas com mais professores qualificados tendem a ter alunos com melhor desempenho.',
    },

    // ── Cruzamentos ──
    'chart-cross-computers': {
        title: 'Computadores e desempenho',
        text: 'Compara a proficiência média dos alunos conforme o número de computadores em casa. A diferença entre as barras (o "gap") é testada estatisticamente. O <strong>Cohen\'s d</strong> indica se esta diferença é pequena, média ou grande na prática.',
    },
    'chart-cross-wifi': {
        title: 'Wi-Fi e desempenho',
        text: 'Compara alunos com e sem Wi-Fi em casa. Um gap grande pode parecer indicar que Wi-Fi melhora o aprendizado, mas pode ser apenas um <strong>proxy do nível socioeconômico</strong> — famílias mais ricas têm mais Wi-Fi E mais recursos educacionais. A aba "Controle INSE" testa esta hipótese.',
    },
    'chart-cross-phones': {
        title: 'Celulares com internet e desempenho',
        text: 'Compara a proficiência média dos alunos conforme o número de celulares com acesso à internet no domicílio. O gradiente crescente (de "Nenhum" a "3 ou mais") sugere uma associação positiva entre conectividade móvel e desempenho. Contudo, assim como o Wi-Fi, o acesso a celulares com internet é fortemente correlacionado com o <strong>nível socioeconômico</strong> da família.',
    },
    'chart-cross-index': {
        title: 'Índice digital composto',
        text: 'Combina múltiplos indicadores de acesso digital (computadores, internet, celulares) em um único índice de 0 a 8. A correlação (r) indica a força da relação linear entre acesso digital e proficiência. Valores entre 0,1 e 0,3 são típicos em ciências sociais.',
    },
    'chart-cross-q194': {
        title: 'Projetos de ciência e tecnologia',
        text: 'Compara a proficiência média de alunos em escolas cujos diretores reportam ter projetos de ciência e tecnologia (Q194) versus aquelas que não possuem. A ausência de diferença significativa pode indicar que a mera existência de projetos não é suficiente — a <strong>qualidade e integração curricular</strong> importam mais.',
    },
    'chart-cross-q219': {
        title: 'Novas tecnologias educacionais',
        text: 'Avalia se escolas que adotam novas tecnologias educacionais (Q219, conforme relato do diretor) apresentam desempenho diferente. Resultados devem ser interpretados com cautela: escolas que adotam novas tecnologias podem diferir sistematicamente em outros aspectos (recursos, gestão, perfil socioeconômico).',
    },
    'chart-cross-q035': {
        title: 'Softwares educacionais',
        text: 'Analisa a relação entre a disponibilidade de softwares educacionais na escola (Q035, escala de adequação reportada pelo diretor) e a proficiência dos alunos. A escala vai de "Inexistente" a "Bom", permitindo observar se há um gradiente de desempenho associado.',
    },
    'chart-cross-q036': {
        title: 'Internet banda larga',
        text: 'Examina se a qualidade da internet banda larga na escola (Q036, conforme avaliação do diretor) está associada ao desempenho dos alunos. Conectividade é condição necessária para o uso efetivo de tecnologias digitais na educação, mas não suficiente por si só.',
    },
    'chart-cross-q029': {
        title: 'Formação docente em tecnologia',
        text: 'Avalia se a percepção do professor sobre a contribuição da sua formação em tecnologia (Q029) está associada à proficiência dos alunos. Professores que se sentem mais preparados para usar tecnologia podem integrar recursos digitais de forma mais efetiva em suas práticas pedagógicas.',
    },
    'chart-cross-q037': {
        title: 'Uso de TICs na prática pedagógica',
        text: 'Examina a relação entre a frequência de uso de TICs pelo professor em sala de aula (Q037) e a proficiência. Um padrão <strong>curvilíneo</strong> (uso moderado associado ao melhor desempenho) pode indicar que o uso excessivo de tecnologia sem propósito pedagógico claro não beneficia a aprendizagem.',
    },
    'chart-cross-forest': {
        title: 'Comparação de efeitos',
        text: 'O <strong>Forest Plot</strong> mostra o tamanho de efeito (Cohen\'s d) de cada variável tecnológica. Barras verdes indicam efeito positivo (tecnologia associada a melhor desempenho) e vermelhas indicam efeito negativo. A linha tracejada no zero indica "sem efeito". Efeitos são classificados como: <strong>pequeno</strong> (d ≈ 0,2), <strong>médio</strong> (d ≈ 0,5) ou <strong>grande</strong> (d ≈ 0,8).',
    },
    'chart-cross-wifi-inse': {
        title: 'Controle por renda',
        text: 'Se a diferença de proficiência entre alunos com e sem Wi-Fi <strong>desaparece</strong> ao comparar dentro do mesmo nível socioeconômico (INSE), isso indica que o efeito observado é <strong>proxy da renda</strong>, não da tecnologia em si. Se a diferença <strong>persiste</strong>, há evidência de efeito independente da tecnologia.',
    },
    'chart-cross-index-inse': {
        title: 'Índice digital por INSE',
        text: 'Mostra a relação entre acesso digital e desempenho dentro de cada faixa de INSE. Permite verificar se alunos com mais acesso digital se saem melhor mesmo comparados com colegas de mesma condição socioeconômica.',
    },

    // ── Ética e IA ──
    'chart-ethics-tech': {
        title: 'Adoção de IA',
        text: 'Proporção de escolas que utilizam tecnologias baseadas em IA. Estes números são relevantes porque decisões automatizadas na educação (como sistemas de correção ou recomendação) podem perpetuar vieses existentes se não forem auditadas adequadamente.',
    },
    'chart-ethics-digital': {
        title: 'Desigualdade digital',
        text: 'A lacuna entre escolas públicas e privadas evidencia o <strong>risco ético</strong> de implementar IA na educação sem considerar a desigualdade de acesso. Alunos de escolas públicas já partem de uma posição desvantajosa — ferramentas de IA podem ampliar essa desigualdade se não forem implementadas com equidade.',
    },
    'chart-ethics-teachers': {
        title: 'Preparação para IA',
        text: 'A formação docente em tecnologia é pré-requisito para o uso ético de IA na educação. Professores precisam entender como funcionam os sistemas automatizados para poder questionar suas recomendações e proteger os alunos de decisões algorítmicas enviesadas.',
    },
    'chart-ethics-dimensions': {
        title: 'Privacidade escolar',
        text: 'Políticas de privacidade e proteção de dados são a base da governança ética de IA em escolas. Dados de crianças e adolescentes requerem proteção especial (ECA e LGPD). A ausência destas políticas é um indicador de <strong>risco ético elevado</strong>.',
    },
};

/**
 * Renderiza um card de explicação colapsável abaixo de um gráfico.
 * @param {string} chartId - ID do container do gráfico
 * @param {HTMLElement} [parentEl] - Elemento pai onde inserir (default: após o chartId)
 */
function renderExplanation(chartId, parentEl) {
    const explanation = CHART_EXPLANATIONS[chartId];
    if (!explanation) return;

    const collapseId = `explain-${chartId}`;

    // Verificar se já existe
    if (document.getElementById(collapseId)) return;

    const target = parentEl || document.getElementById(chartId);
    if (!target) return;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
        <button class="explanation-toggle" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
            <i class="bi bi-lightbulb"></i> O que isso significa?
        </button>
        <div class="collapse" id="${collapseId}">
            <div class="explanation-card">
                ${explanation.text}
            </div>
        </div>
    `;

    target.parentNode.appendChild(wrapper);
}

/**
 * Renderiza explicações para todos os gráficos visíveis na página atual.
 */
function renderAllExplanations() {
    for (const chartId of Object.keys(CHART_EXPLANATIONS)) {
        const el = document.getElementById(chartId);
        if (el && !el.closest('.d-none')) {
            renderExplanation(chartId);
        }
    }
}
