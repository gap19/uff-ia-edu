# Dashboard de Pesquisa: IA na Educação — UFF

Dashboard analítico do projeto PIBITI/PIBINOVA **"Ética na Tomada de Decisão por Inteligência Artificial no Ambiente Escolar"**, coordenado pelo Prof. Richard Fonseca (UFF/Faculdade de Educação).

Analisa microdados do **SAEB 2023** (7,6M+ registros) e da **TIC Educação 2023** (69 indicadores) para investigar impactos éticos da IA nos processos educacionais em escolas do Rio de Janeiro.

## Stack Tecnológico

| Camada | Tecnologia |
|--------|-----------|
| Backend/API | Python 3.12 + FastAPI |
| Banco de dados | DuckDB (in-process, Parquet colunar) |
| Frontend | Vanilla JS + Apache ECharts 5.5 + Bootstrap 5 |
| Tipografia/Ícones | Google Fonts (Inter) + Bootstrap Icons |
| Relatórios PDF | WeasyPrint + matplotlib/seaborn |
| Containerização | Docker + docker-compose |

## Pré-requisitos

- Python 3.10+
- Dependências de sistema para WeasyPrint (libpango, libcairo, libgdk-pixbuf)

> **Dados processados incluídos:** Este repositório já inclui os dados processados em `data/processed/` (~2 GB), prontos para uso. Não é necessário baixar nada para rodar o dashboard.

## Setup Rápido

```bash
# Setup completo: venv + dependências + ETL (~10-15 min)
./scripts/setup.sh

# Ativar ambiente e iniciar servidor
source .venv/bin/activate
python scripts/run.py
```

O dashboard estará acessível em **http://localhost:8000**.

### Setup Manual

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# ETL: CSV → Parquet → DuckDB (~10-15 min)
mkdir -p data/processed/saeb data/processed/tic
python scripts/init_db.py

# Servidor de desenvolvimento
python scripts/run.py
```

## Uso com Docker

```bash
docker-compose up --build
```

O dashboard estará acessível em **http://localhost:8000**.

## Estrutura do Projeto

```
uff-ia-edu/
├── backend/
│   ├── api/                  # FastAPI: app + rotas
│   │   ├── app.py            # Aplicação principal
│   │   ├── routes_saeb.py    # 9 endpoints SAEB
│   │   ├── routes_tic.py     # 7 endpoints TIC
│   │   ├── routes_cross.py   # 6 endpoints cruzamentos
│   │   └── routes_reports.py # Geração de PDF
│   ├── analysis/             # Módulos de análise estatística
│   │   ├── stats_utils.py    # Estatística ponderada
│   │   ├── proficiency.py    # Distribuições de proficiência
│   │   ├── equity.py         # Lacunas pública/privada, INSE
│   │   ├── teacher.py        # Formação e práticas docentes
│   │   └── cross_analysis.py # Cruzamentos tech x desempenho
│   ├── etl/                  # Pipeline de dados
│   │   ├── saeb_loader.py    # CSV → Parquet
│   │   ├── tic_loader.py     # Excel → Parquet
│   │   ├── codebook.py       # Labels dos questionários
│   │   └── precompute.py     # Tabelas de agregação
│   ├── reports/              # Geração de relatórios PDF
│   ├── config.py             # Configuração central
│   └── requirements.txt
├── frontend/
│   ├── templates/dashboard.html  # SPA do dashboard (Jinja2)
│   └── static/
│       ├── css/dashboard.css     # Design system (CSS variables, dark mode)
│       └── js/
│           ├── app.js            # Init, navegação, filtros, dark mode
│           ├── charts.js         # Wrapper ECharts, tema, helpers gráficos
│           ├── pages.js          # Page loaders (dados API → gráficos)
│           ├── glossary.js       # Glossário estatístico PT-BR (popovers)
│           └── explanations.js   # Interpretações acessíveis por gráfico
├── scripts/
│   ├── setup.sh              # Setup com um comando
│   ├── init_db.py            # ETL completo
│   ├── run.py                # Servidor de desenvolvimento
│   └── validate_stats.py     # Validação cruzada de estatísticas
├── tests/                    # Testes pytest (41 testes)
├── data/
│   └── processed/            # Dados processados (incluídos no repo)
│       ├── saeb.duckdb       # Tabelas pré-computadas (~1.1 GB)
│       ├── saeb/*.parquet    # Microdados filtrados (~849 MB)
│       └── tic/*.parquet     # Indicadores TIC (~356 KB)
├── Dockerfile
├── docker-compose.yml
├── METODOLOGIA.md            # Metodologia estatística
└── PLANO.md                  # Plano detalhado do projeto
```

## Páginas do Dashboard

1. **Visão Geral** — KPIs, médias por série/disciplina, ranking nacional de UFs
2. **Proficiência** — Distribuição, níveis de proficiência, comparação RJ/Sudeste/Brasil
3. **Equidade** — Gap pública/privada, correlação INSE x desempenho
4. **Tecnologia nas Escolas** — Indicadores TIC: infraestrutura, IA, formação, privacidade
5. **Professores** — Perfil, formação, práticas, correlação formação x desempenho
6. **Questionários** — Explorador interativo de respostas dos questionários contextuais
7. **Ética e IA** — Síntese: desigualdade digital, preparação docente, dimensões éticas
8. **Cruzamentos Tech x Desempenho** — Análise cruzada com controle por INSE

## API

A documentação interativa da API (Swagger) está disponível em `/docs`.

### Endpoints Principais

| Prefixo | Endpoints | Descrição |
|---------|----------|-----------|
| `/api/saeb/` | 9 | Proficiência, equidade, questionários, ranking |
| `/api/tic/` | 7 | Indicadores de tecnologia nas escolas |
| `/api/cross/` | 6 | Cruzamentos tecnologia x desempenho |
| `/api/reports/` | 2 | Geração de relatório PDF customizável |
| `/api/health` | 1 | Health check |

## Testes

```bash
# Todos os testes (41 testes: unitários + integração + PDF)
python -m pytest tests/ -v

# Apenas testes unitários de estatística
python -m pytest tests/test_stats_utils.py -v

# Apenas testes de API
python -m pytest tests/test_api_saeb.py tests/test_api_tic.py tests/test_api_cross.py -v

# Validação cruzada de estatísticas vs valores de referência
python scripts/validate_stats.py
```

## Geração de Relatórios PDF

O dashboard permite gerar relatórios PDF acadêmicos com seções customizáveis:

1. Clicar em **"Gerar Relatório PDF"** na sidebar
2. Selecionar seções, séries e disciplinas desejadas
3. O PDF é gerado com gráficos vetoriais (matplotlib/seaborn) e tabelas formatadas

Também disponível via API:
```bash
curl "http://localhost:8000/api/reports/generate?secoes=proficiencia&secoes=equidade&series=9EF&disciplinas=LP" -o relatorio.pdf
```

## Recursos do Frontend

### Gráficos Interativos (ECharts)
Todos os gráficos usam Apache ECharts 5.5 com tema customizado. Cada gráfico possui uma toolbox no canto superior direito para exportar como PNG (2x resolução), zoom e restaurar visualização. Gráficos incluem gradientes, animações de entrada e tooltips detalhados.

### Conteúdo Explicativo
- **Glossário estatístico**: termos como "Cohen's d", "p-valor", "INSE" possuem popovers com explicações em linguagem acessível — basta passar o mouse ou tocar
- **Cards "O que isso significa?"**: botão colapsável abaixo de cada gráfico com 2-3 frases interpretando os dados para audiências não-especializadas

### Dark Mode
Toggle na sidebar com persistência via localStorage. Afeta toda a interface incluindo gráficos, cards e tabelas.

### Exportar Gráficos
Clique no ícone de download na toolbox do gráfico para exportar como PNG em alta resolução.

## Rigor Estatístico

- Todas as estimativas utilizam **pesos amostrais** do SAEB
- Intervalos de confiança com **design effect**
- Testes de significância: t-test ponderado, ANOVA, qui-quadrado
- Tamanho de efeito: **d de Cohen** ponderado
- Correção para comparações múltiplas: **Bonferroni**
- Controle por nível socioeconômico (**INSE**) para separar efeito tecnologia de confundimento SES

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

1. Acesse: https://cetic.br/pt/pesquisa/educacao/indicadores/
2. Baixe as **tabelas de escolas** (formato Excel, edição 2023)
3. Coloque os 4 arquivos `.xlsx` em `data/tic_educacao_2023_escolas_tabelas_xlsx_v1.0/`

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
> Dashboard de Pesquisa: IA na Educação — UFF. Projeto PIBITI/PIBINOVA, Faculdade de Educação, Universidade Federal Fluminense. Disponível em: [URL do repositório].

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
