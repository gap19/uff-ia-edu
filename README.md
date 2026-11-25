# Dashboard de Pesquisa: IA na Educação — UFF

Dashboard analítico do projeto PIBITI/PIBINOVA **"Ética na Tomada de Decisão por Inteligência Artificial no Ambiente Escolar"**, coordenado pelo Prof. Richard Fonseca (UFF/Faculdade de Educação).

Analisa microdados do **SAEB 2023** (7,6M+ registros) e da **TIC Educação 2023** (69 indicadores) para investigar impactos éticos da IA nos processos educacionais em escolas do Rio de Janeiro.

**Site publicado:** <https://uff-ia-edu-94f5b.web.app>

## Stack Tecnológico

| Camada | Tecnologia |
|--------|-----------|
| Backend/API | Python 3.11+ (container Docker `Python 3.12-slim`) + FastAPI |
| Banco de dados | DuckDB (in-process, Parquet colunar) |
| Frontend | Vanilla JS + Apache ECharts 5.5.1 + Bootstrap 5.3.3 (`frontend/static/vendor/`, sem CDNs, CSP `script-src 'self'`) |
| Tipografia/Ícones/Fórmulas | `@fontsource/inter` + Bootstrap Icons 1.11.3 + KaTeX 0.16.11 (100% auto-hospedados em `frontend/static/vendor/`) |
| Relatórios PDF | WeasyPrint + matplotlib/seaborn |
| Containerização | Docker + Docker Compose |
| Hospedagem | Firebase Hosting (site estático pré-computado) |

## Pré-requisitos

- **Python 3.11+** (imagem Docker oficial baseada em `python:3.12-slim`)
- Dependências de sistema para WeasyPrint (`libpango`, `libcairo`, `libgdk-pixbuf`)
- **Node.js 18+** *(opcional — usado apenas para rodar os testes de sintaxe e comportamento JS na suíte `pytest`)*

> **Dados processados incluídos:** Este repositório já inclui os dados processados em `data/processed/` (~853 MB, via Git LFS — instale o [git-lfs](https://git-lfs.com) e rode `git lfs pull` caso necessário), prontos para uso. Não é necessário baixar os microdados brutos nem rodar o ETL para iniciar o dashboard.

## Setup Rápido

Como `data/processed/` já está versionado via Git LFS, basta criar o ambiente virtual, instalar as dependências e iniciar o servidor:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt   # ou: pip install -r backend/requirements.lock (versões fixadas reproduzíveis)

# Iniciar servidor local (recarregamento automático)
python scripts/run.py
```

O dashboard estará acessível em **http://localhost:8000**.

> **Nota:** `./scripts/setup.sh` e `python scripts/init_db.py` executam o pipeline ETL completo (~10–15 min) e **só são necessários** caso você queira reprocessar os microdados brutos (`CSV`/`XLSX` → `Parquet` → `DuckDB`); veja [Reprodução a Partir dos Dados Brutos](#reprodução-a-partir-dos-dados-brutos-opcional).

### Variáveis de Ambiente (Opcional)

- `CORS_ORIGINS`: lista de origens permitidas pela API separadas por vírgula (padrão: `http://localhost:8000,http://127.0.0.1:8000`).

## Uso com Docker

```bash
docker compose up --build
```

O dashboard estará acessível em **http://localhost:8000** (para customizar CORS no container, defina `CORS_ORIGINS` no ambiente ou no `docker-compose.yml`).

## Deploy (Firebase Hosting)

O site público é uma exportação estática do dashboard: todas as respostas da
API são pré-computadas como JSON e publicadas no Firebase Hosting (plano
gratuito). Para atualizar o site após mudanças em código ou dados:

```bash
python scripts/export_static.py
firebase deploy --only hosting
```

Detalhes e setup inicial em [DEPLOY.md](DEPLOY.md).

## Estrutura do Projeto

```
uff-ia-edu/
├── backend/
│   ├── api/                  # FastAPI: app, CSP/headers e rotas
│   │   ├── app.py            # Aplicação principal, CORS e CSP estrita
│   │   ├── routes_saeb.py    # 10 endpoints SAEB
│   │   ├── routes_tic.py     # 9 endpoints TIC
│   │   ├── routes_cross.py   # 6 endpoints cruzamentos
│   │   └── routes_reports.py # 2 endpoints de geração de PDF
│   ├── analysis/             # Módulos de análise estatística
│   │   ├── stats_utils.py    # Estatística ponderada e de desenho amostral
│   │   ├── proficiency.py    # Distribuições de proficiência
│   │   ├── equity.py         # Lacunas pública/privada, INSE, localização
│   │   ├── teacher.py        # Formação e práticas docentes (deduplicadas)
│   │   ├── cross_analysis.py # Cruzamentos tech x desempenho
│   │   └── tic.py            # Catálogo de indicadores TIC (Sudeste e Brasil)
│   ├── etl/                  # Pipeline de dados
│   │   ├── saeb_loader.py    # CSV → Parquet
│   │   ├── tic_loader.py     # Excel → Parquet
│   │   ├── codebook.py       # Labels dos questionários
│   │   └── precompute.py     # Tabelas de agregação DuckDB
│   ├── reports/              # Geração de relatórios PDF (WeasyPrint)
│   ├── config.py             # Configuração central
│   ├── db.py                 # Conexão DuckDB compartilhada (somente leitura)
│   ├── requirements.txt      # Dependências diretas (runtime + testes)
│   └── requirements.lock     # Lockfile com versões fixadas reproduzíveis
├── frontend/
│   ├── templates/dashboard.html  # SPA do dashboard (Jinja2, zero JS inline)
│   └── static/
│       ├── css/dashboard.css     # Design system (CSS variables, dark mode)
│       ├── js/
│       │   ├── app.js            # Init, navegação, filtros, dark mode, modo estático
│       │   ├── charts.js         # Wrapper ECharts, tema, helpers gráficos
│       │   ├── pages.js          # Page loaders (dados API → gráficos + KaTeX)
│       │   ├── glossary.js       # Glossário estatístico PT-BR (popovers)
│       │   └── explanations.js   # Interpretações acessíveis por gráfico
│       └── vendor/               # Assets 100% auto-hospedados (sem CDNs)
│           ├── bootstrap/        # Bootstrap 5.3.3 (CSS + bundle JS)
│           ├── bootstrap-icons/  # Bootstrap Icons 1.11.3 (CSS + fontes)
│           ├── echarts/          # Apache ECharts 5.5.1
│           ├── inter/            # Tipografia @fontsource/inter (woff2)
│           └── katex/            # KaTeX 0.16.11 (CSS + JS + fontes matemáticas)
├── scripts/
│   ├── setup.sh              # Setup completo + reprocessamento ETL
│   ├── init_db.py            # Orquestrador do pipeline ETL
│   ├── run.py                # Servidor de desenvolvimento
│   ├── export_static.py      # Exportação estática para o Firebase Hosting
│   └── validate_stats.py     # Validação cruzada de estatísticas (109 checks)
├── tests/                    # Suíte automatizada pytest (213 testes)
│   ├── conftest.py               # Fixtures compartilhadas
│   ├── test_stats_utils.py       # Estatística ponderada e desenho amostral
│   ├── test_etl_and_analysis.py  # ETL, módulos analíticos e concorrência DB
│   ├── test_api_saeb.py          # Endpoints SAEB
│   ├── test_api_tic.py           # Endpoints TIC Educação
│   ├── test_api_cross.py         # Endpoints de cruzamentos
│   ├── test_api_reports.py       # Geração e validação de relatórios PDF
│   ├── test_export_static.py     # Paridade 1:1 da exportação estática
│   └── test_frontend_and_infra.py # JS em VM Node.js, CSP, HTML e Docker/Firebase
├── data/
│   └── processed/            # Dados processados (incluídos via Git LFS)
│       ├── saeb.duckdb                   # 14 tabelas agregadas (~3,9 MB)
│       ├── saeb_questionnaire_dict.json  # Dicionário oficial SAEB (~164 KB)
│       ├── saeb/*.parquet                # Microdados SAEB 2023 (~849 MB)
│       └── tic/*.parquet                 # Tabelas TIC Educação 2023 (~340 KB)
├── pyproject.toml            # Metadados do pacote e config pytest/ruff/mypy
├── Dockerfile
├── .dockerignore
├── docker-compose.yml
├── firebase.json             # Configuração e headers CSP do Firebase Hosting
├── DEPLOY.md                 # Guia de deploy (site estático)
└── METODOLOGIA.md            # Metodologia estatística detalhada
```

## Páginas do Dashboard

A navegação lateral reúne **10 seções**:

- **Início** — Apresentação institucional do projeto PIBITI/PIBINOVA, objetivos específicos, fontes de dados e síntese metodológica
- **1. Visão Geral** — KPIs do RJ, médias ponderadas por série/disciplina e ranking nacional de UFs
- **2. Proficiência** — Distribuição, níveis de proficiência (5º EF, 9º EF e Ensino Médio) e comparação RJ/Sudeste/Brasil
- **3. Equidade** — Lacuna pública/privada, gradiente socioeconômico (INSE × desempenho) e recorte urbano/rural
- **4. Tecnologia nas Escolas** *(Tecnologia)* — Indicadores TIC Educação (Sudeste como proxy do RJ, Brasil como referência): infraestrutura, dados/IA, formação docente e privacidade
- **5. Professores** — Perfil docente deduplicado (`ID_PROFESSOR`), práticas e dispersão formação docente × proficiência escolar
- **6. Questionários** — Explorador interativo das questões fechadas dos questionários contextuais (alunos, professores e diretores)
- **7. Ética e IA** — Síntese crítica: desigualdade digital, preparação docente, vigilância escolar, privacidade e dimensões éticas
- **8. Cruzamentos Tech x Desempenho** *(Cruzamentos Tech)* — Análise cruzada (11 variáveis tecnológicas + Índice Digital Composto) com estratificação por INSE, tamanhos de efeito e correção de Bonferroni
- **Metodologia** — Documentação completa de fontes, ETL, desenho amostral e testes estatísticos com fórmulas renderizadas via **KaTeX**

## API

A documentação interativa da API (Swagger) está disponível em `/docs` ao rodar o servidor localmente.

> **Nota:** o site publicado (Firebase Hosting) não roda a API dinâmica — ele serve versões pré-computadas de todas as respostas como arquivos JSON estáticos, gerados por `scripts/export_static.py`.

### Endpoints Principais

| Prefixo | Endpoints | Descrição |
|---------|----------|-----------|
| `/api/saeb/` | 10 | Proficiência, equidade, formação docente, questionários e ranking |
| `/api/tic/` | 9 | Indicadores TIC Educação (Sudeste e Brasil, com margens de erro) |
| `/api/cross/` | 6 | Cruzamentos tecnologia x desempenho |
| `/api/reports/` | 2 | Geração de relatório PDF customizável |
| `/api/health` | 1 | Health check |

## Testes e Qualidade

A suíte automatizada conta com **213 testes** cobrindo estatística de desenho amostral, pipeline ETL e concorrência DuckDB, endpoints da API, geração de PDF, paridade da exportação estática, execução comportamental do frontend JS em VM Node.js e hardening de infraestrutura/CSP:

```bash
# Suíte completa (213 testes: estatística, ETL, API, PDF, export estático, JS/Node e infra/CSP)
python -m pytest tests/ -v

# Validação cruzada de estatísticas contra valores de referência (109 verificações)
python scripts/validate_stats.py

# Linting e verificação estática de tipos
ruff check .
python -m mypy backend scripts tests
```

## Geração de Relatórios PDF

O dashboard permite gerar relatórios PDF acadêmicos com seções customizáveis:

1. Clicar em **"Gerar Relatório PDF"** na sidebar
2. Selecionar seções, séries e disciplinas desejadas
3. O PDF é gerado com gráficos vetoriais (matplotlib/seaborn) e tabelas formatadas

> **Nota:** a customização de seções requer o servidor local. No site publicado, o botão baixa o relatório completo pré-gerado (todas as seções, incluindo cruzamentos, com apêndice para todas as séries e disciplinas; gráficos de série única — ranking, INSE e cruzamentos — referem-se ao 9º EF / LP).

Também disponível via API:
```bash
curl "http://localhost:8000/api/reports/generate?secoes=proficiencia&secoes=equidade&series=9EF&disciplinas=LP" -o relatorio.pdf
```

## Recursos do Frontend

### Gráficos Interativos (ECharts)
Todos os gráficos usam Apache ECharts 5.5.1 auto-hospedado com tema customizado. Cada gráfico possui uma toolbox no canto superior direito para exportar como PNG (2x resolução), zoom e restaurar visualização. Gráficos incluem gradientes, animações de entrada e tooltips detalhados.

### Conteúdo Explicativo
- **Glossário estatístico**: termos como "Cohen's d", "p-valor", "INSE" possuem popovers com explicações em linguagem acessível — basta passar o mouse ou tocar
- **Cards "O que isso significa?"**: botão colapsável abaixo de cada gráfico com 2-3 frases interpretando os dados para audiências não-especializadas

### Dark Mode
Toggle na sidebar com persistência via localStorage. Afeta toda a interface incluindo gráficos, cards e tabelas.

### Exportar Gráficos
Clique no ícone de download na toolbox do gráfico para exportar como PNG em alta resolução.

## Rigor Estatístico

- Todas as estimativas populacionais utilizam os **pesos amostrais** oficiais do SAEB (`PESO_ALUNO_LP`, `PESO_ALUNO_MT`)
- Erros-padrão, intervalos de confiança e testes incorporam o **desenho amostral complexo** do SAEB (linearização de Taylor com estratos e conglomerados por escola, equivalente a `svy`/`survey`), com **aninhamento explícito de PSUs `(ESTRATO, ID_ESCOLA)`** — indispensável no Ensino Médio (`34EM`), onde uma mesma escola pode figurar em múltiplos estratos (`nest=TRUE`)
- Testes de significância: teste *t* (de desenho para alunos/pares aluno–professor; Welch para escolas), ANOVA (Wald com correção *F* de Korn–Graubard) e correlação de Pearson ponderada
- Tamanho de efeito: **d de Cohen** ponderado (com correção de Bessel para *reliability weights* e **invariância estrita à escala dos pesos**) e **η²**
- Correção para comparações múltiplas: **Bonferroni** aplicada aos 11 testes simultâneos de cruzamentos tecnológicos (**`0,05/11 ≈ 0,0045`**)
- **Deduplicação descritiva**: respondentes de `TS_PROFESSOR` deduplicados por **`ID_PROFESSOR`** (priorizando a turma principal) e de `TS_DIRETOR` deduplicados por **`ID_ESCOLA`** antes das contagens descritivas e cruzamentos em nível escolar
- Controle por nível socioeconômico (**INSE**, restrito a `IN_INSE = 1`) para separar o efeito associado à tecnologia do confundimento socioeconômico

Veja [METODOLOGIA.md](METODOLOGIA.md) para detalhes completos.

## Reprodução a Partir dos Dados Brutos (Opcional)

Os dados processados já estão incluídos no repositório. Esta seção é para quem deseja **validar o pipeline** ou **adicionar novas fontes de dados**.

### 1. SAEB 2023 — Microdados (INEP/MEC)

1. Acesse: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/saeb
2. Baixe **"Microdados SAEB 2023"** (~1.2 GB compactado)
3. Extraia em `data/MICRODADOS_SAEB_2023/`
   ```
   data/MICRODADOS_SAEB_2023/
   ├── DADOS/                          # CSVs (~3.1 GB)
   │   ├── TS_ALUNO_2EF.csv
   │   ├── TS_ALUNO_5EF.csv
   │   ├── TS_ALUNO_9EF.csv
   │   ├── TS_ALUNO_34EM.csv
   │   ├── TS_ESCOLA.csv
   │   ├── TS_PROFESSOR.csv
   │   ├── TS_DIRETOR.csv
   │   ├── TS_SECRETARIO_MUNICIPAL.csv
   │   └── TS_ITEM.csv
   ├── DICIONÁRIO/
   ├── INPUTS/                         # Scripts R com labels das variáveis
   └── LEIA-ME E DOCUMENTOS TÉCNICOS/
   ```

### 2. TIC Educação 2023 — Tabelas (CETIC.br/NIC.br)

1. Baixe as **tabelas de escolas** (Excel, v1.0) em <https://cetic.br/media/microdados/786/tic_educacao_2023_escolas_tabelas_xlsx_v1.0.zip> (página: <https://cetic.br/pt/arquivos/educacao/2023/escolas/>)
2. Extraia os 4 arquivos `.xlsx` em `data/tic_educacao_2023_escolas_tabelas_xlsx_v1.0/`
3. Os indicadores exibidos no dashboard estão catalogados em `backend/analysis/tic.py` (rota `/api/tic/groups`)

### 3. Executar o Pipeline ETL

```bash
source .venv/bin/activate
python scripts/init_db.py           # ETL completo (~10-15 min)
python scripts/validate_stats.py    # Validação cruzada dos resultados
```

## Licença

Este projeto é licenciado sob [**Creative Commons Atribuição 4.0 Internacional (CC BY 4.0)**](https://creativecommons.org/licenses/by/4.0/deed.pt-br).

Você pode **compartilhar** (copiar, redistribuir) e **adaptar** (remixar, transformar, criar a partir de) este material para qualquer finalidade, inclusive comercial, desde que atribua crédito adequado ao projeto original e indique se alterações foram feitas.

**Atribuição sugerida:**
> Dashboard de Pesquisa: IA na Educação — UFF. Projeto PIBITI/PIBINOVA, Faculdade de Educação, Universidade Federal Fluminense. Disponível em: https://uff-ia-edu-94f5b.web.app (código-fonte: https://github.com/gap19/uff-ia-edu).

## Usando como Base para Outros Projetos

Esta aplicação foi pensada para ser reutilizável. Se você deseja criar um fork com **outros dados** (outras edições do SAEB, outros estados, outras pesquisas), o pipeline ETL é modular:

| Arquivo | O que faz | Como adaptar |
|---------|-----------|--------------|
| `backend/config.py` | Define caminhos, filtros geográficos e mapeamentos | Altere `ID_UF_RJ`, `SAEB_CSV_FILES`, `TIC_XLSX_FILES` para seus dados |
| `backend/etl/saeb_loader.py` | Converte CSVs do SAEB em Parquet | Ajuste filtros de colunas ou adicione novos datasets |
| `backend/etl/tic_loader.py` | Converte Excel do TIC em Parquet | Adapte para outras pesquisas do CETIC.br ou fontes similares |
| `backend/etl/precompute.py` | Gera tabelas de agregação no DuckDB | Adicione novas tabelas conforme seus indicadores |
| `scripts/init_db.py` | Orquestra o pipeline completo | Adicione novas etapas se necessário |

**Fluxo para adicionar uma nova fonte de dados:**

1. Crie um novo loader em `backend/etl/` (ex: `pnad_loader.py`)
2. Registre os caminhos em `backend/config.py`
3. Adicione as queries de agregação em `backend/etl/precompute.py`
4. Crie os endpoints em `backend/api/` (ex: `routes_pnad.py`)
5. Adicione a página correspondente no frontend (`frontend/templates/dashboard.html` + `frontend/static/js/pages.js`)
6. Execute `python scripts/init_db.py` para processar
