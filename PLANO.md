# Plano: Dashboard de Pesquisa - IA e Educação (UFF)

## Contexto

O projeto PIBITI/PIBINOVA "Ética na Tomada de Decisão por Inteligência Artificial no Ambiente Escolar", coordenado por Richard Fonseca (UFF/Faculdade de Educação), investiga os impactos éticos da IA nos processos educacionais em escolas do Rio de Janeiro. Este dashboard visa fornecer estatísticas cientificamente rigorosas a partir dos microdados do SAEB 2023 e da pesquisa TIC Educação 2023, servindo como ferramenta analítica para subsidiar os eixos da pesquisa: equidade, formação docente, infraestrutura tecnológica e dimensões éticas da IA na educação.

---

## 1. Arquitetura Geral

### Stack Tecnológico

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| Backend/API | Python + FastAPI | Tipagem, async, OpenAPI auto, serve arquivos estáticos |
| Banco de dados | DuckDB | Leitura direta de CSV/Parquet, in-process (sem servidor), processamento colunar para datasets de 2.5M+ linhas |
| Frontend | Vanilla JS + Plotly.js + Bootstrap 5 | Sem build step, charts interativos com export PNG/SVG, responsivo |
| Relatórios PDF | WeasyPrint + matplotlib/seaborn | HTML/CSS para PDF, gráficos estáticos vetoriais para publicação |
| Deploy | Docker + docker-compose | Local e nuvem com a mesma imagem |

### Decisão Arquitetural Central: DuckDB + Parquet

Os CSVs do SAEB totalizam ~3GB. Carregar em pandas a cada request é inviável. DuckDB resolve isso:
1. Converte CSVs para Parquet (compressão colunar: ~3GB -> ~500MB)
2. Consultas SQL diretamente sobre Parquet com streaming colunar
3. Pré-computa tabelas de agregação para respostas sub-100ms
4. Roda in-process (sem PostgreSQL/MySQL), ideal para execução local

### Estrutura de Diretórios

```
uff-ia-edu/
  backend/
    etl/                # Pipeline de dados
      saeb_loader.py    # CSV -> Parquet
      tic_loader.py     # Excel parser (138 planilhas)
      codebook.py       # Labels dos questionários (via scripts R)
      precompute.py     # Tabelas de agregação pré-calculadas
    analysis/           # Módulos de análise estatística
      proficiency.py    # Distribuições de proficiência
      equity.py         # Lacunas pública vs privada, INSE
      questionnaire.py  # Respostas dos questionários
      teacher.py        # Formação e práticas docentes
      tic_indicators.py # Indicadores de tecnologia
      cross_analysis.py # Cruzamentos tech x desempenho (aluno, escola, professor)
      stats_utils.py    # Médias ponderadas, IC, testes, ANOVA
    api/
      app.py            # Aplicação FastAPI
      routes_saeb.py    # Endpoints SAEB
      routes_tic.py     # Endpoints TIC
      routes_cross.py   # Endpoints de cruzamentos tech x desempenho
      routes_reports.py # Geração de PDF
    reports/
      pdf_generator.py  # Motor de geração PDF
      templates/        # Templates Jinja2 para PDF
    config.py
    requirements.txt
  frontend/
    templates/
      base.html         # Layout base
      dashboard.html    # Página principal
    static/
      css/dashboard.css
      js/
        app.js          # Controlador principal
        charts.js       # Construtores Plotly.js
        filters.js      # Painel de filtros
        pages/          # Módulos por página (7 páginas)
      vendor/           # Plotly.js e Bootstrap offline
  scripts/
    setup.sh            # Setup com um comando
    init_db.py          # ETL completo
    run.py              # Servidor de desenvolvimento
  data/                 # Dados brutos (já existente, READ-ONLY)
    processed/          # Parquet e DuckDB gerados pelo ETL
  tests/
  Dockerfile
  docker-compose.yml
```

---

## 2. Pipeline de Dados (ETL)

### 2.1 SAEB: CSV -> Parquet (`saeb_loader.py`)

Para cada arquivo em `data/MICRODADOS_SAEB_2023/DADOS/`:
1. Leitura via DuckDB (`read_csv_auto` com `delim=';'`)
2. Correção de tipos (proficiências como DOUBLE, respostas como VARCHAR)
3. Gravação em `data/processed/saeb/{arquivo}.parquet`

**Arquivos e volumes**:
- `TS_ALUNO_5EF.csv` -> 2,4M linhas, 153 colunas
- `TS_ALUNO_9EF.csv` -> 2,5M linhas, 153 colunas
- `TS_ALUNO_34EM.csv` -> 2,1M linhas
- `TS_ESCOLA.csv` -> 70K linhas, 137 colunas
- `TS_PROFESSOR.csv` -> 411K linhas, 148 colunas
- `TS_DIRETOR.csv` -> 107K linhas
- `TS_SECRETARIO_MUNICIPAL.csv` -> 5,5K linhas

### 2.2 TIC: Excel -> Parquet (`tic_loader.py`)

Os 4 arquivos Excel contêm 138 planilhas cada. Estratégia:
1. Ler cada planilha com openpyxl
2. Parsear headers multinível (linhas 1-4: descrição, categorias, subcategorias)
3. Normalizar para formato longo: `indicador`, `variavel_corte`, `valor_corte`, `proporcao`, `total`, `margem_erro`
4. Gravar como `data/processed/tic/tic_educacao_2023.parquet`

### 2.3 Codebook (`codebook.py`)

Parsear os scripts R em `INPUTS/INPUT_R_*.R` para extrair labels de variáveis e opções de resposta dos questionários. Os scripts R contêm as definições completas como factor levels.

Funções:
- `get_variable_label(tabela, coluna)` -> descrição em português
- `get_response_labels(tabela, coluna)` -> {código: label}
- `get_proficiency_scale(serie, disciplina)` -> faixas e interpretação

### 2.4 Pré-computação (`precompute.py`)

Tabelas de agregação materializadas em DuckDB/Parquet (~15-20 tabelas):

| Tabela | Dimensões | Uso |
|--------|----------|-----|
| `prof_by_uf_serie_disc` | UF x série x disciplina x rede | Comparação de proficiência |
| `prof_by_inse` | INSE x série x disciplina | Análise socioeconômica |
| `prof_niveis_rj` | nível x série x disc x rede | Distribuição por nível |
| `prof_niveis_nacional` | nível x série x disc | Comparação nacional |
| `quest_aluno_rj` | questão x resposta x série | Questionários dos alunos |
| `quest_professor_rj` | questão x resposta | Questionários dos professores |
| `quest_diretor_rj` | questão x resposta | Questionários dos diretores |
| `escola_formacao_rj` | faixa formação x proficiência | Impacto da formação docente |
| `escola_inse_rj` | INSE x proficiências médias | Nível escola |
| `tic_indicadores` | indicador x corte x valor | Dados TIC normalizados |
| `cross_aluno_tech_rj` | tech_var x resposta x serie x disc x INSE | Proficiência por acesso digital do aluno |
| `cross_diretor_tech_rj` | tech_var x resposta x rede | Proficiência escolar por infra tech do diretor |
| `cross_professor_tech_rj` | tech_var x resposta x serie x disc | Proficiência por formação tech do professor |
| `cross_digital_index_rj` | faixa_digital x serie x disc x INSE | Índice digital composto vs proficiência |
| `cross_summary_rj` | analysis_type x serie x disc | Gaps, Cohen's d, p-valores pré-calculados |

**Filtro Rio de Janeiro**: `ID_UF = 33` (código IBGE real, não mascarado)
**Filtro Sudeste**: `ID_REGIAO = 3`
**Rede**: `IN_PUBLICA = 0` (privada) ou `IN_PUBLICA = 1` (pública)

---

## 3. Rigor Estatístico (`stats_utils.py`)

### Pesos Amostrais

Todas as estimativas do SAEB **devem** usar os pesos amostrais:
- `PESO_ALUNO_LP` / `PESO_ALUNO_MT` para Língua Portuguesa / Matemática
- `PESO_ALUNO_CH` / `PESO_ALUNO_CN` para Ciências Humanas / Natureza
- `PESO_ALUNO_INSE` para indicador socioeconômico
- Variável `ESTRATO` para estimação de variância com desenho amostral

### Funções Estatísticas

- `weighted_mean(values, weights)` - Média ponderada
- `weighted_variance(values, weights)` - Variância com correção de Bessel
- `weighted_percentile(values, weights, q)` - Percentis ponderados
- `confidence_interval_mean(values, weights, strata, alpha=0.05)` - IC com design effect
- `weighted_ttest(group1_vals, group1_weights, group2_vals, group2_weights)` - Teste t ponderado
- `cohens_d_weighted(...)` - Tamanho de efeito para lacunas de desempenho
- `chi_squared_test(contingency_table)` - Teste de independência para questionários
- `pearson_weighted(x, y, weights)` - Correlação ponderada (INSE vs proficiência)

### Validação Cruzada

Resultados devem ser verificados contra os dados oficiais publicados pelo INEP:
- Médias estaduais por UF (disponível em `PLANILHAS DE RESULTADOS/TS_UF.ods`)
- Médias nacionais (disponível em `TS_BRASIL.ods`)
- Distribuições por nível de proficiência

---

## 4. Frontend: 7 Páginas do Dashboard

### Navegação

```
[Logo UFF] Painel de Pesquisa: IA na Educação

Sidebar:
  1. Visão Geral
  2. Proficiência
  3. Equidade
  4. Tecnologia nas Escolas
  5. Professores
  6. Questionários
  7. Ética e IA
  8. Cruzamentos Tech x Desempenho
  ---
  Gerar Relatório PDF
  Sobre o Projeto
```

### Painel de Filtros Global (persistente)
- Série: 2o EF, 5o EF, 9o EF, 3o/4o EM
- Disciplina: LP, MT, CH, CN
- Rede: Pública, Privada, Todas
- Localização: Urbana, Rural, Todas
- Área: Capital, Interior, Todas

### Página 1 - Visão Geral
- Cards KPI: total de alunos avaliados no RJ, total de escolas, média de proficiência RJ vs Brasil
- Mapa coroplético do Brasil por UF (proficiência média), com RJ destacado
- Gráfico de barras: médias por série e disciplina no RJ
- Resumo dos achados principais (autogerado)

### Página 2 - Proficiência
- **Aba Distribuição**: Histograma de proficiência (RJ) com overlay nacional
- **Aba Níveis**: Barras empilhadas com % de alunos em cada nível (0-9/10), pública vs privada
- **Aba Comparação**: RJ vs estados do Sudeste; RJ vs ranking nacional (27 UFs)

### Página 3 - Equidade
- **Aba Pública vs Privada**: Histogramas lado a lado, lacuna com IC 95% e tamanho de efeito (d de Cohen)
- **Aba INSE**: Scatter INSE x proficiência média, box plots por nível INSE, composição socioeconômica
- **Aba Localização**: Urbana vs Rural, Capital vs Interior, heatmap cruzado

### Página 4 - Tecnologia nas Escolas (TIC Educação)

> Banner: "Dados referentes à região Sudeste. Dados por UF não disponíveis na pesquisa TIC Educação pública."

- **Aba Infraestrutura**: Internet (A1-A8), velocidade (A3), WiFi (A4), equipamentos (B1-B12)
- **Aba IA e Dados**: Sistemas de IA (E6), analytics (E5), biometria/reconhecimento facial (E4A-B), chatbots (F6)
- **Aba Formação Digital**: Capacitação docente (J1-J4), letramento digital (I1-I3), políticas de acesso (C1-C6)
- **Aba Privacidade**: Políticas de proteção (H1), debates (H3), preocupações (H7), não adoção por privacidade (H6)

### Página 5 - Professores
- **Aba Perfil**: Demographics, formação, condições de emprego
- **Aba Formação e Práticas**: Treinamento em tecnologia (TX_Q029), necessidade de capacitação (TX_Q037)
- **Aba Infraestrutura Escolar**: Adequação de recursos tecnológicos (TX_Q069-Q075)
- **Aba Correlações**: Formação docente (PC_FORMACAO_DOCENTE) vs desempenho dos alunos

### Página 6 - Questionários (Explorador Interativo)
- Seleção: dataset (Aluno 5EF, 9EF, Professor, Diretor, Secretário) + questão
- Visualização automática: gráfico de barras com distribuição de respostas
- Tabulação cruzada: comparar respostas entre duas variáveis
- Aplicação de filtros geográficos e demográficos

### Página 7 - Ética e IA (Síntese)
- **Contexto Tecnológico**: Resumo TIC sobre adoção de IA, vigilância, privacidade
- **Desigualdade Digital**: Acesso a tecnologia em casa (Q12-Q13) vs proficiência, brecha pública/privada — integra achados da página 8
- **Preparação Docente**: Necessidade de formação em tecnologia vs participação real
- **Dimensões Éticas**: Adoção de IA sem políticas de privacidade adequadas; vigilância biométrica; autonomia docente vs mandatos tecnológicos externos

### Página 8 - Cruzamentos Tech x Desempenho (NOVO)

> Página central de análise cruzada entre variáveis de tecnologia e proficiência.

- **Aba Acesso Digital do Aluno**: Barras agrupadas (computadores em casa vs proficiência), barras lado-a-lado (WiFi sim/não com gap e p-valor), linha do índice digital composto. Toggle "Controlar por INSE".
- **Aba Infraestrutura Escolar**: Barras para projetos de tecnologia (Q194) vs proficiência, inovação digital (Q219) vs proficiência, software educacional (Q035) vs proficiência, internet banda larga (Q036).
- **Aba Formação Docente em Tecnologia**: Barras de proficiência por nível de contribuição da formação tech (Q029) e uso de TICs (Q037).
- **Aba Panorama Geral**: Tabela HTML com todas variáveis ranqueadas por Cohen's d (color-coded). Forest plot horizontal com todos os efeitos e IC.
- **Aba Controle INSE**: Small multiples mostrando o gap em cada nível INSE. Card interpretativo: "O efeito persiste após controlar pelo nível socioeconômico?"

---

## 5. Análises Cientificamente Relevantes

### 5.1 Análises SAEB (filtro RJ: ID_UF = 33)

1. **Distribuições de proficiência** em LP, MT, CH, CN por série (5EF, 9EF, EM)
2. **Lacuna pública vs privada**: diferença de médias ponderadas, IC 95%, d de Cohen
3. **Correlação INSE x desempenho**: Pearson ponderado, regressão por faixas INSE
4. **Impacto da formação docente**: cruzamento PC_FORMACAO_DOCENTE_INICIAL/FINAL/MEDIO com médias de proficiência
5. **Distribuição por nível de proficiência**: % de alunos em cada nível (crítico, insuficiente, básico, adequado, avançado)
6. **Comparação RJ vs Brasil e Sudeste**: diferença com IC, ranking entre UFs
7. **Questionários de alunos**: perfil socioeconômico, acesso a tecnologia em casa, hábitos de estudo

### 5.2 Análises TIC (Sudeste)

1. **Adoção de sistemas de IA** (indicador E6) - por tipo de rede e porte
2. **Políticas de privacidade** (H1-H7) - lacunas entre adoção de tecnologia e proteção de dados
3. **Infraestrutura de conectividade** (A1-A8) - velocidade, cobertura WiFi, barreiras
4. **Capacitação docente** (J1-J4) - programação, robótica, conteúdos digitais
5. **Tecnologias de vigilância** (E4A-B) - biometria, reconhecimento facial
6. **Plataformas de ensino virtual** (G1-G4) - Teams, Zoom, Classroom, Moodle
7. **Letramento digital** (I1-I3) - uso seguro, responsável e crítico da internet

### 5.3 Cruzamentos Tecnologia x Desempenho (`cross_analysis.py`)

> **Fundamentação**: OECD/PISA 2022 mostra que uso moderado de dispositivos = +14 pts em matemática, mas uso excessivo = efeito negativo. UNESCO 2023 indica que impacto de tecnologia é context-dependent, mediado por formação docente e equidade. Acesso a tecnologia em casa se confunde fortemente com nível socioeconômico (INSE), exigindo controle estatístico.

#### 5.3.1 Cruzamentos Nível Aluno (TS_ALUNO_5EF, 9EF, 34EM)

Variáveis tecnológicas cruzadas com `PROFICIENCIA_LP_SAEB` / `PROFICIENCIA_MT_SAEB` (pesos amostrais):

| Variável | Pergunta | Respostas | Teste |
|----------|----------|-----------|-------|
| `TX_RESP_Q12b` | Computadores em casa | A=Nenhum, B=1, C=2, D=3+ | ANOVA ponderado + tendência linear |
| `TX_RESP_Q12g` | Celulares com internet | A=Nenhum, B=1, C=2, D=3+ | ANOVA ponderado + tendência linear |
| `TX_RESP_Q13a` | TV por internet/streaming | A=Não, B=Sim | t-test ponderado + Cohen's d |
| `TX_RESP_Q13b` | Rede Wi-Fi em casa | A=Não, B=Sim | t-test ponderado + Cohen's d |

**Índice Digital Composto**: soma de Q12b(0-3) + Q12g(0-3) + Q13a(0-1) + Q13b(0-1) = 0 a 8. Faixas: Baixo(0-2), Médio(3-5), Alto(6-8). Correlação Pearson ponderada com proficiência.

**Controle INSE**: todas as análises executadas duas vezes — bruta (raw) e estratificada por `NU_TIPO_NIVEL_INSE` (1-8). Se o gap some ao estratificar, tecnologia é proxy de renda (achado válido).

**Dado preliminar confirmado (RJ 9EF LP)**: WiFi sim (B): 102K alunos, média=263.6 vs WiFi não (A): 9.5K alunos, média=244.2. Gap bruto ≈ 19.3 pts. ~50% dos alunos RJ 9EF não têm computador em casa.

#### 5.3.2 Cruzamentos Nível Escola (TS_DIRETOR → TS_ESCOLA via ID_ESCOLA)

Variáveis de infraestrutura tecnológica do diretor cruzadas com `MEDIA_*` de TS_ESCOLA:

| Variável | Pergunta | Respostas | Teste |
|----------|----------|-----------|-------|
| `TX_Q034` | Computadores na escola | A-E (escala de adequação) | ANOVA |
| `TX_Q035` | Softwares educacionais | A-E | ANOVA |
| `TX_Q036` | Internet banda larga | A-E | ANOVA |
| `TX_Q194` | Projetos de ciência e tecnologia | A=Sim, B=Não | t-test + Cohen's d |
| `TX_Q219` | Novas tecnologias educacionais | A=Sim, B=Não | t-test + Cohen's d |

#### 5.3.3 Cruzamentos Nível Professor (TS_PROFESSOR → TS_ALUNO via ID_TURMA)

| Variável | Pergunta | Teste |
|----------|----------|-------|
| `TX_Q029` | Contribuição da formação em tecnologia | ANOVA ponderado |
| `TX_Q037` | Uso de TICs | ANOVA ponderado |

#### 5.3.4 Dimensão Ética

1. **Divide digital**: acesso a tecnologia em casa vs desempenho, controlado por INSE
2. **Lacuna de formação**: necessidade declarada de formação tecnológica (professor) vs oferta real
3. **Paradoxo privacidade-adoção**: escolas que adotam IA (TIC E6) sem políticas de privacidade (TIC H1-H7)
4. **Equidade tecnológica**: pública vs privada em acesso a equipamentos e conectividade

#### 5.3.5 Limitações Metodológicas (a documentar no dashboard)

1. **Correlação ≠ causalidade**: cruzamentos mostram associações, não efeitos causais
2. **Confundimento SES**: acesso a tecnologia correlaciona fortemente com renda; estratificação INSE mitiga mas não elimina
3. **TIC regional vs SAEB escolar**: dados TIC são nível Sudeste, não cruzáveis diretamente com escolas individuais
4. **Comparações múltiplas**: com ~12 variáveis testadas, aplicar correção Bonferroni (α = 0.05/12 ≈ 0.004)
5. **Missing data**: respostas em branco ('.' e '*') são filtradas — verificar se introduz viés

### 5.4 Sugestões de Dados Complementares

Para enriquecer as análises futuras, sugere-se considerar a incorporação de:

1. **Censo Escolar 2023 (INEP)**: dados de infraestrutura física das escolas por município, incluindo laboratório de informática, acesso a internet, número de computadores - permitiria cruzamento direto com SAEB no nível escola
2. **IDEB 2023**: índice histórico de desenvolvimento educacional por escola/município, permitindo análise temporal
3. **PNAD Contínua - TIC (IBGE)**: acesso domiciliar a internet e tecnologia no RJ, complementando a visão escolar do TIC Educação
4. **Microdados TIC Educação (CETIC.br)**: solicitar acesso aos microdados via canais oficiais, permitindo análise no nível UF e não apenas regional
5. **Dados do QEdu / IDEB por escola**: métricas de fluxo escolar (aprovação, reprovação, abandono) para cruzar com indicadores de tecnologia
6. **Pesquisa PISA (OCDE)**: comparação internacional do Brasil em letramento digital e uso de tecnologia por estudantes

---

## 6. Geração de Relatórios PDF

### Motor: WeasyPrint (HTML/CSS -> PDF)

1. Templates Jinja2 definem layout acadêmico (A4, margens adequadas, cabeçalho/rodapé)
2. Gráficos gerados via matplotlib/seaborn (vetoriais, 300 DPI)
3. Tabelas formatadas com estilos de publicação

### Estrutura do Relatório

```
Capa: Logo UFF, título do projeto, autores, data
Sumário
1. Resumo Executivo
2. Metodologia (fontes de dados, pesos amostrais, testes aplicados)
3. Resultados SAEB (gráficos e tabelas selecionados)
4. Resultados TIC Educação
5. Cruzamentos e Dimensões Éticas
6. Apêndice Estatístico (tabelas detalhadas, ICs, resultados de testes)
Referências
```

### Customização via API

```json
POST /api/reports/generate
{
  "secoes": ["proficiencia", "equidade", "tecnologia", "cruzamentos", "etica"],
  "series": ["5EF", "9EF"],
  "disciplinas": ["LP", "MT"],
  "incluir_apendice": true
}
```

### Endpoints de Cruzamento (`/api/cross/`)

| Endpoint | Params | Fonte |
|----------|--------|-------|
| `GET /student-tech` | serie, disciplina, variable, stratify_inse | `cross_aluno_tech_rj` |
| `GET /director-tech` | variable, serie, disciplina | `cross_diretor_tech_rj` |
| `GET /teacher-tech` | variable, serie, disciplina | `cross_professor_tech_rj` |
| `GET /digital-index` | serie, disciplina, stratify_inse | `cross_digital_index_rj` |
| `GET /summary` | serie, disciplina | `cross_summary_rj` |
| `GET /school-scatter` | serie, disciplina, tech_var | TS_ESCOLA + TS_DIRETOR direto |

---

## 7. Estratégia de Deploy

### Local (padrão)

```bash
# Um comando para setup completo
./scripts/setup.sh

# Internamente:
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py   # ETL: CSV -> Parquet -> agregações (~10-15min)
python scripts/run.py       # FastAPI em http://localhost:8000
```

### Docker (deploy online)

```dockerfile
FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
RUN python scripts/init_db.py
EXPOSE 8000
CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Opções de deploy cloud: Fly.io, Railway, Render (free tier), VPS (DigitalOcean ~$6/mês)

### Atualização do DevContainer

O `.devcontainer/devcontainer.json` existente será atualizado com:
- Python 3.12 (estabilidade de bibliotecas)
- `postCreateCommand` com instalação de dependências
- Port forwarding para 8000

---

## 8. Fases de Desenvolvimento

### Fase 1 - Fundação ✅
- [x] Scaffolding do projeto (diretórios, requirements.txt, config)
- [x] `saeb_loader.py`: conversão CSV -> Parquet para todas as 9 tabelas SAEB (7,6M+ linhas)
- [x] `tic_loader.py`: parsing dos Excel TIC (276 planilhas, 83.244 registros) - corrigido bug openpyxl drawings
- [x] `codebook.py`: extrair labels dos scripts R (9 tabelas, 140+ variáveis)
- [x] `precompute.py`: gerar 11 tabelas de agregação no DuckDB
- [x] `stats_utils.py`: 10 funções de estatística ponderada (média, variância, IC, t-test, Cohen's d, etc.)
- [x] `init_db.py`: script de setup completo com etapas e progresso
- [x] Testes: médias do RJ verificadas na escala SAEB (LP 5EF ~206 pública, ~240 privada)

### Fase 2 - API Backend ✅
- [x] FastAPI app com CORS e serviço de arquivos estáticos (`backend/api/app.py`)
- [x] Endpoints SAEB: 9 endpoints (overview, proficiency, equity, questionnaires, ranking)
- [x] Endpoints TIC: 7 endpoints (indicators, infrastructure, AI, privacy, training)
- [x] Módulos de análise: `proficiency.py`, `equity.py`, `teacher.py`
- [x] Testes de API (41 testes: pytest + httpx — unitários, integração SAEB/TIC/Cross, PDF)

### Fase 3 - Frontend Dashboard ✅
- [x] Template base HTML + Bootstrap + navegação sidebar (`dashboard.html`)
- [x] CSS do dashboard e JavaScript controlador principal (`app.js`)
- [x] Painel de filtros global (série, disciplina, rede)
- [x] Páginas 1-2: Visão Geral e Proficiência - conectados à API
- [x] Páginas 3-4: Equidade e Tecnologia nas Escolas
- [x] Páginas 5-7: Professores, Questionários, Ética e IA
- [x] Export de gráficos (PNG/SVG) — modebar Plotly.js habilitada com botão de download PNG 2x

### Fase 4 - Relatórios PDF e Polimento ✅
- [x] `pdf_generator.py` com WeasyPrint + matplotlib (6 geradores de gráficos vetoriais)
- [x] Templates de relatório Jinja2 (capa, sumário, 6 seções, apêndice estatístico, referências)
- [x] Gráficos matplotlib/seaborn para PDF (proficiência, equidade, INSE, ranking, TIC)
- [x] API endpoint `POST/GET /api/reports/generate` com opções customizáveis
- [x] UI no frontend: botão "Gerar Relatório PDF" + modal de configuração
- [x] Validação cruzada de todas as estatísticas (58 validações em `scripts/validate_stats.py`)
- [x] Revisão de textos em português, responsividade (CSS mobile/tablet/print, modal "Sobre", notas metodológicas)

### Fase 5 - Deploy e Documentação ✅
- [x] Dockerfile (Python 3.12-slim + deps WeasyPrint)
- [x] docker-compose.yml (porta 8000, volume para dados processados)
- [x] devcontainer.json atualizado (Python 3.12, port forwarding, deps sistema)
- [ ] Deploy em cloud (se necessário)
- [x] README.md com instruções completas (setup, Docker, testes, API, export)
- [x] Documentação técnica e de metodologia estatística (`METODOLOGIA.md`)

### Fase 6 - Cruzamentos Tech x Desempenho ✅
- [x] `stats_utils.py`: adicionar `weighted_anova_oneway()` (F-test ponderado)
- [x] `cross_analysis.py` (novo): 5 funções de análise cruzada (aluno, diretor, professor, índice digital, resumo)
- [x] `precompute.py`: 4 novas tabelas de agregação para cruzamentos (630 + 114 + 48 + 418 linhas)
- [x] `routes_cross.py` (novo): 6 endpoints de API + registro em `app.py`
- [x] `dashboard.html`: página 8 com 5 abas de visualizações + entrada na sidebar
- [x] `app.js`: `loadCrossAnalysis()` + renderização de gráficos Plotly (~250 linhas)
- [x] `pdf_generator.py`: seção "cruzamentos" com 4 gráficos matplotlib + template atualizado
- [x] Página 7 (Ética e IA): integrar achados-chave dos cruzamentos
- [x] Validação: gap WiFi = 19.3 pts confirmado (LP 9EF RJ), INSE-stratified reduz para ~4-14 pts
- [x] Re-rodar `init_db.py`: 16 tabelas pré-computadas geradas com sucesso

**Resultados validados (9EF LP RJ):**
- WiFi sim vs não: gap = 19.3 pts (244.2 → 263.6), n=111K
- Computadores: gradiente A(247) → B(265) → C(275) → D(287), ~40 pts spread
- Índice digital composto: Baixo(237) → Médio(252) → Alto(274), 37 pts spread
- Projetos de ciência/tech (diretor Q194): sem efeito (252.7 vs 252.8)
- Uso de TICs (professor Q037): curvilíneo — uso moderado é ótimo (261→265→267→264)
- Controle INSE: gap WiFi reduz de 19 pts bruto para ~4-14 pts dentro de cada nível, confirmando confundimento SES parcial

---

## 9. Verificação

### Como testar de ponta a ponta
1. Executar `./scripts/setup.sh` - deve criar venv, instalar deps, rodar ETL sem erros
2. Executar `python scripts/run.py` - dashboard acessível em `http://localhost:8000`
3. Verificar Página 1 (Visão Geral): cards KPI mostram números coerentes
4. Verificar Página 2 (Proficiência): médias do RJ devem bater com `TS_UF.ods` (planilha oficial)
5. Verificar Página 4 (Tecnologia): indicadores TIC devem bater com tabelas publicadas
6. Verificar Página 8 (Cruzamentos): 5 abas com gráficos interativos, gap WiFi ≈ 19 pts
7. Verificar controle INSE: gap reduz ao estratificar por nível socioeconômico
8. Gerar relatório PDF com seção "cruzamentos": gráficos legíveis, tabela de efeitos
9. Docker: `docker-compose up` deve subir o dashboard funcional

### Arquivos críticos (Fases 1-5)
- `backend/etl/saeb_loader.py`, `tic_loader.py`, `codebook.py`, `precompute.py` ✅
- `backend/analysis/stats_utils.py`, `proficiency.py`, `equity.py`, `teacher.py` ✅
- `backend/api/app.py`, `routes_saeb.py`, `routes_tic.py`, `routes_reports.py` ✅
- `frontend/templates/dashboard.html`, `frontend/static/js/app.js` ✅
- `scripts/init_db.py`, `.devcontainer/devcontainer.json` ✅

### Arquivos críticos (Fase 6 - Cruzamentos)
- `backend/analysis/cross_analysis.py` (novo) - módulo de análise cruzada
- `backend/analysis/stats_utils.py` (editar) - adicionar ANOVA ponderado
- `backend/etl/precompute.py` (editar) - 5 novas tabelas de agregação
- `backend/api/routes_cross.py` (novo) - 6 endpoints
- `backend/api/app.py` (editar) - registrar router de cruzamentos
- `frontend/templates/dashboard.html` (editar) - página 8 + sidebar
- `frontend/static/js/app.js` (editar) - loadCrossAnalysis + gráficos
- `backend/reports/pdf_generator.py` (editar) - seção cruzamentos
- `backend/reports/templates/report.html` (editar) - template seção 5

### Funções/utilidades existentes a reutilizar
- Scripts R em `data/MICRODADOS_SAEB_2023/INPUTS/` - fonte autoritativa para labels e tipos de dados
- Dicionário em `data/MICRODADOS_SAEB_2023/DICIONARIO/Dicionario_Saeb_2023.xlsx` - referência cruzada
- Escalas de proficiência em `ESCALAS DE PROFICIÊNCIA/` - faixas e interpretação pedagógica
