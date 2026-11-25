# Dados e Métodos — Dashboard IA e Educação (UFF)

Este documento descreve, de forma detalhada e didática, **todas as fontes de dados** utilizadas na aplicação, **como são processados**, **quais análises estatísticas são realizadas** e **o que cada resultado significa** no contexto da pesquisa sobre Inteligência Artificial e Educação no estado do Rio de Janeiro.

O objetivo é que qualquer pessoa — mesmo sem formação avançada em estatística — consiga compreender de onde vêm os números apresentados no dashboard, como foram calculados e por que foram escolhidos.

---

## Sumário

1. [Visão geral das fontes de dados](#1-visão-geral-das-fontes-de-dados)
2. [SAEB 2023 — Microdados do desempenho escolar](#2-saeb-2023--microdados-do-desempenho-escolar)
3. [TIC Educação 2023 — Tecnologia nas escolas](#3-tic-educação-2023--tecnologia-nas-escolas)
4. [Como os dados são processados (ETL)](#4-como-os-dados-são-processados-etl)
5. [Dados apresentados diretamente (descritivos)](#5-dados-apresentados-diretamente-descritivos)
6. [Dados cruzados (análises comparativas)](#6-dados-cruzados-análises-comparativas)
7. [Dados "criados" por manipulação estatística](#7-dados-criados-por-manipulação-estatística)
8. [Métodos estatísticos explicados](#8-métodos-estatísticos-explicados)
9. [Índice Digital Composto](#9-índice-digital-composto)
10. [Correção para comparações múltiplas (Bonferroni)](#10-correção-para-comparações-múltiplas-bonferroni)
11. [Fluxo completo dos dados](#11-fluxo-completo-dos-dados)
12. [Limitações e cuidados na interpretação](#12-limitações-e-cuidados-na-interpretação)
13. [Glossário de termos técnicos](#13-glossário-de-termos-técnicos)

---

## 1. Visão geral das fontes de dados

A aplicação utiliza **duas grandes fontes públicas** de dados educacionais brasileiros:

| Fonte | Órgão responsável | Ano | O que mede | Abrangência |
|-------|-------------------|-----|------------|-------------|
| **SAEB** (Sistema de Avaliação da Educação Básica) | INEP/MEC | 2023 | Desempenho dos alunos em provas padronizadas, perfil de professores, diretores e escolas | Nacional (todos os estados) |
| **TIC Educação** | CETIC.br / NIC.br | 2023 | Uso de tecnologia, IA e infraestrutura digital nas escolas | Brasil e regiões (não por estado) — usamos o Sudeste como proxy do RJ |

### Por que essas fontes?

- O **SAEB** é a principal avaliação em larga escala da educação básica no Brasil. Permite medir a proficiência dos alunos e, por meio dos questionários contextuais, entender as condições de ensino.
- A **TIC Educação** é a pesquisa de referência sobre tecnologia nas escolas brasileiras, incluindo indicadores sobre inteligência artificial, privacidade de dados e formação digital docente — temas centrais desta pesquisa.

A combinação dessas duas fontes permite responder à pergunta central: **qual é a relação entre o acesso à tecnologia e o desempenho educacional no Rio de Janeiro?**

---

## 2. SAEB 2023 — Microdados do desempenho escolar

### 2.1 O que são os microdados?

Os microdados do SAEB são registros individuais (um por aluno, professor, diretor ou escola) contendo centenas de variáveis. A aplicação utiliza os seguintes arquivos:

| Arquivo | Conteúdo | Volume aproximado |
|---------|----------|-------------------|
| `TS_ALUNO_5EF` | Alunos do 5º ano do Ensino Fundamental | ~2,4 milhões de registros |
| `TS_ALUNO_9EF` | Alunos do 9º ano do Ensino Fundamental | ~2,5 milhões de registros |
| `TS_ALUNO_34EM` | Alunos do Ensino Médio (3ª/4ª séries) | ~2,1 milhões de registros |
| `TS_ESCOLA` | Resultados agregados por escola (apenas escolas **públicas**) | ~70 mil escolas |
| `TS_PROFESSOR` | Respostas dos professores | ~411 mil registros |
| `TS_DIRETOR` | Respostas dos diretores | ~107 mil registros |

### 2.2 Variáveis de proficiência

Cada aluno possui uma **nota na escala SAEB** para cada disciplina avaliada:

- **`PROFICIENCIA_LP_SAEB`** — Língua Portuguesa
- **`PROFICIENCIA_MT_SAEB`** — Matemática

Essas notas **não são como notas de prova** (0 a 10). São valores em uma escala contínua (tipicamente entre 100 e 400 pontos) que permite comparar desempenho entre séries, anos e regiões. Quanto maior o valor, maior a proficiência do aluno.

### 2.3 Pesos amostrais e desenho amostral

O SAEB 2023 é **censitário** para as escolas públicas (todas as turmas das séries avaliadas) e **amostral** para as escolas privadas (amostra estratificada de escolas). Em ambos os casos, cada aluno recebe um **peso** que indica quantos alunos da população ele "representa" — corrigindo a seleção amostral e a não resposta:

- **`PESO_ALUNO_LP`** — Peso para análises de Língua Portuguesa
- **`PESO_ALUNO_MT`** — Peso para análises de Matemática

> **Exemplo:** Se um aluno tem peso 3,5, isso significa que ele "vale por" 3,5 alunos na estimativa populacional. Como os alunos de escolas privadas foram sorteados, seus pesos são muito maiores que os das públicas; sem os pesos, a rede privada ficaria sub-representada e as médias, enviesadas para baixo (no 9º ano do RJ, em LP, a média ignorando os pesos seria ~252 em vez de 261,3).

**Toda média calculada nesta aplicação é uma média ponderada** que utiliza esses pesos.

Além dos pesos, os microdados trazem as variáveis do **desenho amostral**, usadas para calcular erros-padrão, intervalos e testes (ver [seção 8.1](#81-intervalo-de-confiança)):

- **`ID_ESCOLA`** — a escola é o **conglomerado** (unidade primária de amostragem): alunos de uma mesma escola tendem a ter resultados parecidos;
- **`ESTRATO`** — o **estrato** de seleção (no RJ, 162 estratos no 5º ano, 216 no 9º ano e 178 no Ensino Médio; no 5º e 9º anos cada escola pertence a um único estrato, enquanto no Ensino Médio algumas escolas com turmas de 3ª e 4ª séries aparecem em dois estratos — por isso os conglomerados são aninhados no estrato como pares `(ESTRATO, ID_ESCOLA)`, equivalente a `nest=TRUE` no pacote `survey` do R e ao `svy` do Stata).

### 2.4 Variáveis socioeconômicas

- **`INSE_ALUNO`** — Índice de Nível Socioeconômico (escala contínua de 0 a ~200)
- **`NU_TIPO_NIVEL_INSE`** — Nível INSE categorizado em faixas de 1 (mais baixo) a 8 (mais alto)
- **`IN_INSE`** — 1 quando o INSE do aluno foi calculado. **Atenção:** alunos sem INSE (`IN_INSE = 0`, em geral por não responderem ao questionário) vêm com `NU_TIPO_NIVEL_INSE = 1`; a aplicação só usa o nível INSE quando `IN_INSE = 1` (no 9º ano do RJ, isso evita colocar ~5,4 mil alunos sem INSE no nível 1, que tem ~0,9 mil alunos de fato)
- **`IN_PUBLICA`** — Se a escola é pública (1) ou privada (0)
- **`ID_LOCALIZACAO`** — 1 = Urbana, 2 = Rural
- **`ID_UF`** — Código do estado (33 = Rio de Janeiro)

### 2.5 Variáveis de acesso à tecnologia (questionário do aluno)

O questionário contextual do SAEB pergunta aos alunos sobre tecnologia em casa:

| Código | Pergunta | Respostas |
|--------|----------|-----------|
| `TX_RESP_Q12b` | Quantos computadores há na sua casa? | A = Nenhum, B = 1, C = 2, D = 3 ou mais |
| `TX_RESP_Q12g` | Quantos celulares com internet? | A = Nenhum, B = 1, C = 2, D = 3 ou mais |
| `TX_RESP_Q13a` | Tem TV por streaming em casa? | A = Não, B = Sim |
| `TX_RESP_Q13b` | Tem Wi-Fi em casa? | A = Não, B = Sim |

### 2.6 Variáveis do questionário do professor

| Código | Pergunta | Respostas |
|--------|----------|-----------|
| `TX_Q001` | Sexo | A = Masculino, B = Feminino, C = Não declarado |
| `TX_Q029` | Contribuição da formação em tecnologia | A = Não contribuiu, B = Pouco, C = Razoavelmente, D = Muito |
| `TX_Q037` | Necessidade de formação sobre o uso de novas TICs | A = Nenhuma necessidade, B = Pouca, C = Moderada, D = Muita necessidade |
| `TX_Q020` | Maior nível de escolaridade concluído | A = Ensino Médio - Magistério, B = Graduação, C = Especialização, D = Mestrado, E = Doutorado |

> Os rótulos seguem o dicionário oficial do SAEB 2023 (`data/processed/saeb_questionnaire_dict.json`). Atenção: `TX_Q004`–`TX_Q007` tratam de deficiência/TEA/altas habilidades, não de formação; o questionário de 2023 não tem item de tempo de experiência. O SAEB também não identifica a disciplina do professor: em turmas com mais de um professor respondente, cada aluno é associado a todos eles, com o peso amostral dividido pelo número de professores da turma (unidade de análise: par aluno–professor).

### 2.7 Variáveis do questionário do diretor

| Código | Pergunta | Respostas |
|--------|----------|-----------|
| `TX_Q034` | Condição dos computadores da escola | A = Não tem, B = Muito inadequado, C = Inadequado, D = Adequado, E = Muito adequado |
| `TX_Q035` | Softwares educacionais | A = Não tem ... E = Muito adequado |
| `TX_Q036` | Internet banda larga | A = Não tem ... E = Muito adequado |
| `TX_Q194` | Há projetos de ciência e tecnologia na escola? | A = Não, B = Sim |
| `TX_Q219` | A equipe escolar recebeu formação em novas tecnologias educacionais neste ano? | A = Não, B = Sim |

> `TS_DIRETOR` tem uma linha por escola **e por série avaliada** (com as mesmas respostas). Nos cruzamentos, o questionário é reduzido a uma linha por escola antes do cruzamento com `TS_ESCOLA`, para que cada escola conte uma única vez. Diferenças e d de Cohen das variáveis binárias são sempre calculados como "Sim − Não".

### 2.8 Variáveis da escola

`TS_ESCOLA` contém apenas escolas **públicas** com resultados no SAEB (4.215 no RJ). As médias e percentuais são calculados pelo INEP.

| Coluna | Descrição |
|--------|-----------|
| `MEDIA_5EF_LP`, `MEDIA_5EF_MT` | Proficiência média dos alunos do 5º ano |
| `MEDIA_9EF_LP`, `MEDIA_9EF_MT` | Proficiência média dos alunos do 9º ano |
| `MEDIA_EM_LP`, `MEDIA_EM_MT` | Proficiência média dos alunos do Ensino Médio |
| `PC_FORMACAO_DOCENTE_INICIAL` | % de docentes com formação adequada — anos iniciais do EF |
| `PC_FORMACAO_DOCENTE_FINAL` | % de docentes com formação adequada — anos finais do EF |
| `PC_FORMACAO_DOCENTE_MEDIO` | % de docentes com formação adequada — Ensino Médio |
| `NIVEL_0_LP5` a `NIVEL_9_LP5` (e análogos) | % de alunos da escola em cada nível de proficiência |

---

## 3. TIC Educação 2023 — Tecnologia nas escolas

### 3.1 O que é a pesquisa TIC Educação?

A pesquisa TIC Educação, conduzida pelo Cetic.br (Centro Regional de Estudos para o Desenvolvimento da Sociedade da Informação, do NIC.br/CGI.br), investiga o uso de tecnologias da informação e comunicação nas escolas brasileiras de Ensino Fundamental e Médio (universo de 130.918 escolas em 2023), por amostra probabilística.

> **Importante:** A TIC Educação **não divulga dados por estado**. As tabelas trazem o total do Brasil e recortes por região, área, localização, dependência administrativa, nível de ensino e porte. Na aplicação, os indicadores são apresentados para a **região Sudeste** (proxy para o Rio de Janeiro) e para o **Brasil** (referência), sempre com as margens de erro publicadas pelo Cetic.br. Isso é informado ao usuário no dashboard.

### 3.2 Arquivos utilizados

Tabelas oficiais de escolas, versão 1.0, baixadas de <https://cetic.br/media/microdados/786/tic_educacao_2023_escolas_tabelas_xlsx_v1.0.zip> e colocadas em `data/tic_educacao_2023_escolas_tabelas_xlsx_v1.0/`:

| Arquivo | Conteúdo |
|---------|----------|
| `tic_educacao_2023_escolas_tabela_proporcao_v1.0.xlsx` | Proporções (%) de escolas |
| `tic_educacao_2023_escolas_tabela_total_v1.0.xlsx` | Estimativas do número de escolas |
| `tic_educacao_2023_escolas_tabela_margem_de_erro_v1.0.xlsx` | Margens de erro das proporções (p.p.) |
| `tic_educacao_2023_escolas_tabela_margem_de_erro_total_v1.0.xlsx` | Margens de erro dos totais |

Cada arquivo tem 69 abas (uma por indicador). O ETL (`backend/etl/tic_loader.py`) lê, em cada aba, o título (linha 1), o universo (linha 2), os cabeçalhos de subitem e de resposta (linhas 3–4) e as linhas de dados, preservando a variável de corte (ex.: `REGIÃO`) e a categoria (ex.: `Sudeste`). Resultado: `data/processed/tic/tic_educacao_2023.parquet` (colunas `indicador, titulo, universo, tipo, variavel_corte, valor_corte, item, resposta, coluna, valor`).

### 3.3 Indicadores utilizados

Os gráficos usam conjuntos curados de indicadores, definidos em `backend/analysis/tic.py` (e disponíveis em `/api/tic/groups`). Em todos, o valor é o **percentual de escolas com resposta "Sim"** (exceto quando indicado).

#### Infraestrutura e conectividade

| Indicador | Pergunta oficial | Rótulo no dashboard |
|-----------|------------------|---------------------|
| B1 | Escolas que possuem computador | Possui computador |
| A1 | Escolas com acesso à internet | Acesso à internet |
| A6 | Escolas que possuem computador e acesso à internet | Computador e internet |
| B1B | Escolas que possuem computador disponível para uso dos alunos em atividades educacionais | Computador para uso dos alunos |
| A7 | Escolas com acesso à internet para uso dos alunos | Internet para uso dos alunos |
| A8 | Escolas que possuem computador e acesso à internet para uso dos alunos | Computador e internet para os alunos |
| A4 | Escolas com acesso à internet, por presença de rede sem fio¹ | Rede sem fio¹ |
| A2 | … por tipo da principal conexão — resposta "Conexão via fibra ótica"¹ | Conexão por fibra ótica¹ |

#### Dados, vigilância e inteligência artificial

| Indicador | Pergunta oficial | Rótulo no dashboard |
|-----------|------------------|---------------------|
| E3 | Uso de sistema interno de câmeras de vídeo | Câmeras de vídeo internas |
| E4A | Uso de sistema de identificação dos alunos pela digital ou palma da mão | Biometria (digital/palma) |
| E4B | Uso de sistema de identificação dos alunos por reconhecimento facial | Reconhecimento facial |
| E6 | Uso de bases de dados e analítica de aprendizagem na gestão — subitem "Relatórios… de *Business Intelligence* (BI)" | Business Intelligence na gestão |
| E6 | Idem — subitem "Sistemas de Inteligência Artificial, como ferramentas de predição e análise de dados baseadas em aprendizagem de máquina" | Sistemas de IA na gestão |
| F6 | Recursos do aplicativo da escola — subitem "Monitoramento das atividades dos alunos por meio de acesso às câmeras de vídeo" | Câmeras acessíveis pelo app |
| F6 | Idem — subitem "Atendimento automatizado, por meio de assistente virtual ou chatbots" | Chatbot no app da escola |

#### Formação docente em tecnologias

| Indicador | Pergunta oficial | Rótulo no dashboard |
|-----------|------------------|---------------------|
| J1 | Oferta de formação para os professores sobre o uso de tecnologias digitais no ensino (últimos 12 meses) | Ofertou formação em tecnologias |
| J3 | Participação em programas de formação de professores sobre tecnologias digitais | Participa de programa de formação |
| J2 | Temas das formações: "Linguagem de programação e robótica", "Criação de conteúdos educacionais digitais", "Fake news…", "Uso de tecnologias na avaliação dos alunos" | Tema: … |

#### Privacidade e proteção de dados

| Indicador | Pergunta oficial | Rótulo no dashboard |
|-----------|------------------|---------------------|
| H1 | Possui documento que define a política de proteção de dados e de segurança da informação | Política de proteção de dados |
| H3 | Realizou debates ou palestras sobre privacidade e proteção de dados (12 meses) | Debates sobre privacidade |
| H5 | Recebeu dúvidas de pais ou responsáveis sobre privacidade dos dados dos alunos (12 meses) | Dúvidas de pais sobre privacidade |
| H6 | Deixou de adotar dispositivos, plataformas ou recursos digitais por preocupação com a privacidade dos alunos | Deixou de adotar recurso por privacidade |

#### Uso seguro da internet (rota `/api/tic/digital-literacy`)

I1 (promoveu formação sobre uso seguro, responsável e crítico da internet) e I3 (público-alvo: alunos, professores, pais).

¹ Universo: escolas com acesso à internet. Nos demais, o universo é o total de escolas de Ensino Fundamental e Médio.

### 3.4 Filtros aplicados

Para cada indicador do catálogo: `tipo = 'proporcao'` (valor) e `tipo = 'margem_erro'` (margem de erro), na resposta indicada (em geral "Sim") e, quando houver, no subitem indicado; recortes `variavel_corte = 'REGIÃO' AND valor_corte = 'Sudeste'` e `valor_corte = 'TOTAL'` (Brasil).

---

## 4. Como os dados são processados (ETL)

ETL significa **Extract, Transform, Load** (Extrair, Transformar, Carregar). É o processo que transforma os dados brutos em tabelas prontas para consulta.

### 4.1 Etapa 1: Conversão para formato eficiente

Os dados brutos (CSV do SAEB e XLSX da TIC) são convertidos para o formato **Parquet**, um formato colunar otimizado para consultas analíticas. Os microdados ficam apenas nos Parquet (`data/processed/saeb/*.parquet`), lidos diretamente pelas análises estatísticas.

### 4.2 Etapa 2: Pré-computação de tabelas agregadas

O script `backend/etl/precompute.py` lê os Parquet e gera, do zero, o banco DuckDB `data/processed/saeb.duckdb` (~5 MB) com **14 tabelas agregadas**, para que as consultas descritivas do dashboard respondam em milissegundos:

| Tabela | O que contém | Tipo de dado |
|--------|--------------|--------------|
| `kpi_rj` | Alunos (registros e presentes) e médias gerais do RJ por série | Descritivo direto |
| `kpi_escolas_rj` | Contagem de escolas (públicas) com resultados no RJ | Descritivo direto |
| `prof_by_uf_serie_disc` | Proficiência média e soma dos pesos por UF, série, disciplina e rede | Descritivo (agregado com pesos) |
| `prof_niveis_rj` | Média, entre escolas públicas do RJ, do % de alunos por nível | Descritivo direto |
| `prof_niveis_nacional` | Idem, nacional | Descritivo direto |
| `prof_by_inse` | Proficiência por nível socioeconômico (RJ, `IN_INSE = 1`) | Cruzamento |
| `prof_by_location_rj` | Proficiência urbana vs. rural (RJ) | Cruzamento |
| `escola_inse_rj` | Proficiências médias por INSE da escola | Cruzamento |
| `quest_aluno_rj` | Distribuição de respostas fechadas dos alunos | Descritivo direto |
| `quest_professor_rj` | Distribuição de respostas fechadas dos professores (deduplicada por `ID_PROFESSOR`) | Descritivo direto |
| `quest_diretor_rj` | Distribuição de respostas fechadas dos diretores (deduplicada por `ID_ESCOLA`) | Descritivo direto |
| `cross_aluno_tech_rj` | Médias de proficiência por resposta tecnológica do aluno (e por INSE) | Cruzamento |
| `cross_digital_index_rj` | Médias por valor do índice digital composto (e por INSE) | Criado por manipulação estatística |
| `tic_indicadores` | Tabelas da TIC Educação em formato longo | Descritivo direto |

Os testes estatísticos (t, ANOVA, correlação, intervalos de confiança) **não** são pré-computados: são calculados sob demanda a partir dos Parquet (em geral em menos de 0,1 s), assim como os cruzamentos em nível de escola/diretor/professor e a dispersão formação docente × proficiência.

### 4.3 Como a média ponderada é calculada

A operação mais fundamental em toda a aplicação é a **média ponderada**. Em vez de simplesmente somar e dividir (média simples), cada valor é multiplicado pelo seu peso antes da soma:

```
                 Σ (valor_i × peso_i)
Média ponderada = ────────────────────
                     Σ (peso_i)
```

**Exemplo concreto:**

Suponha 3 alunos com as seguintes notas e pesos:

| Aluno | Proficiência | Peso |
|-------|-------------|------|
| Ana   | 200         | 2,0  |
| Bruno | 250         | 1,5  |
| Clara | 180         | 3,0  |

- **Média simples:** (200 + 250 + 180) / 3 = **210,0**
- **Média ponderada:** (200×2,0 + 250×1,5 + 180×3,0) / (2,0 + 1,5 + 3,0) = (400 + 375 + 540) / 6,5 = **202,3**

A média ponderada é menor porque Clara, que tem a nota mais baixa, tem o maior peso (ela "representa" mais alunos na população). Ignorar os pesos distorceria os resultados.

---

## 5. Dados apresentados diretamente (descritivos)

Esses são dados que vêm das fontes originais e são exibidos **sem transformação estatística complexa** — apenas contagens, médias e proporções.

### 5.1 Visão Geral (KPIs)

- **Alunos avaliados** no RJ: presentes na prova de Língua Portuguesa (`IN_PRESENCA_LP = 1`), por série
- **Escolas públicas com resultados** (`TS_ESCOLA` não inclui as privadas)
- **Médias de proficiência** em LP e MT por série

> Esses números são médias ponderadas calculadas diretamente dos microdados, sem cruzamento.

### 5.2 Proficiência por UF (ranking)

Para cada estado, calcula-se a média ponderada de proficiência. Os estados são então ordenados, permitindo visualizar a posição do RJ no cenário nacional.

**Quando o filtro de rede (pública/privada) não está ativo**, a média do estado é recalculada combinando as duas redes:

```
                 média_pública × peso_total_pública + média_privada × peso_total_privada
Média do estado = ──────────────────────────────────────────────────────────────────────────
                                peso_total_pública + peso_total_privada
```

### 5.3 Distribuição por nível de proficiência

O SAEB classifica os alunos em **níveis de proficiência** (0 a 9 para LP no 5º EF, 0 a 8 para LP no 9º EF e Ensino Médio, 0 a 10 para MT no 5º EF e Ensino Médio, e 0 a 9 para MT no 9º EF), onde cada nível corresponde a um conjunto de habilidades que o aluno demonstra dominar.

Os percentuais vêm da tabela `TS_ESCOLA`, que traz, para cada escola **pública**, o percentual de alunos em cada nível (pré-calculado pelo INEP, incluindo `NIVEL_*_LPEM` e `NIVEL_*_MTEM` expostos como `34EM`). A aplicação mostra a **média simples desses percentuais entre as escolas públicas do RJ** — uma aproximação da distribuição dos alunos da rede pública (não pondera pelo tamanho da escola nem inclui a rede privada). Disponível para 5º EF, 9º EF e Ensino Médio (`34EM`).

### 5.4 Perfil dos professores e questionários contextuais

Distribuição das respostas dos professores do RJ aos questionários contextuais:
- **Sexo** (questão Q001)
- **Contribuição da formação em tecnologia** (Q029)
- **Adequação dos computadores na escola** (Q072)

Como `TS_PROFESSOR` possui uma linha por turma avaliada em que o docente leciona (repetindo o mesmo professor em múltiplas turmas) e `TS_DIRETOR` possui uma linha por escola e série avaliada, as tabelas descritivas (`quest_professor_rj` e `quest_diretor_rj`) e funções descritivas de perfil docente filtram questionários efetivamente preenchidos (`IN_PREENCHIMENTO_QUESTIONARIO = 1`) e **deduplicam antes da contagem**:
- **Professor:** 1 linha por docente único (`ID_PROFESSOR`, priorizando a turma principal onde `IN_PREENCHIMENTO_OUTRA_TURMA = 0`, resultando nos 10.239 docentes respondentes únicos no RJ);
- **Diretor:** 1 linha por escola única (`ID_ESCOLA`, resultando nas 3.776 escolas respondentes únicas no RJ).
Apenas questões fechadas presentes no dicionário oficial (`saeb_questionnaire_dict.json`) são tabuladas, excluindo campos dissertativos abertos.

### 5.5 Indicadores TIC Educação

As proporções de escolas são exibidas diretamente como publicadas pela TIC Educação, para o Sudeste e o Brasil — por exemplo, "98,0% das escolas do Sudeste têm acesso à internet (margem de erro ±1,2 p.p.); no Brasil, 92,4%".

---

## 6. Dados cruzados (análises comparativas)

Esses dados **combinam duas variáveis** para responder a perguntas do tipo: "Alunos com acesso a X têm desempenho diferente de alunos sem acesso?"

### 6.1 Lacuna Pública vs. Privada

**Pergunta:** Qual a diferença de proficiência entre alunos de escolas públicas e privadas no RJ?

**Como é calculada:**
1. Separam-se os alunos pela variável `IN_PUBLICA` (0 = privada, 1 = pública)
2. Calcula-se a média ponderada de proficiência para cada grupo
3. A **lacuna** é a subtração: `média_privada − média_pública`

**Teste estatístico aplicado:** teste t com erro-padrão de desenho + d de Cohen (ver [seção 8](#8-métodos-estatísticos-explicados)). No dashboard, a lacuna é exibida a partir das médias pré-computadas; o d de Cohen e o intervalo de confiança da lacuna aparecem no apêndice do relatório PDF.

### 6.2 Proficiência por nível socioeconômico (INSE)

**Pergunta:** O nível socioeconômico do aluno está relacionado ao seu desempenho?

**Como é calculada:**
1. Os alunos **com INSE calculado** (`IN_INSE = 1`) são agrupados por nível INSE (1 a 8)
2. Calcula-se a média ponderada de proficiência para cada nível

### 6.3 Proficiência urbana vs. rural

**Pergunta:** Há diferença de desempenho entre alunos de áreas urbanas e rurais?

**Como é calculada:**
1. Separam-se os alunos por `ID_LOCALIZACAO` (1 = Urbana, 2 = Rural)
2. Calcula-se a média ponderada para cada grupo
3. A lacuna é calculada e testada estatisticamente

### 6.4 Formação docente vs. proficiência

**Pergunta:** Escolas com maior percentual de professores com formação adequada têm melhores resultados?

**Como é calculada:**
1. Para cada escola pública do RJ (uma linha por escola, lida de `TS_ESCOLA`), usa-se o indicador de formação docente do INEP **específico da etapa**: `PC_FORMACAO_DOCENTE_INICIAL` (5º ano), `PC_FORMACAO_DOCENTE_FINAL` (9º ano) ou `PC_FORMACAO_DOCENTE_MEDIO` (Ensino Médio), e a proficiência média da escola na mesma etapa
2. O gráfico de dispersão (scatter plot) mostra essa relação — cada ponto é uma escola
3. Uma **linha de tendência** (regressão linear simples, sem pesos) é traçada
4. O **coeficiente de correlação de Pearson (r)** entre escolas é exibido

### 6.5 Tecnologia do aluno vs. proficiência

Para cada variável de tecnologia do aluno (computador, Wi-Fi, celular com internet, streaming), a análise compara a proficiência média entre os grupos de resposta.

**Exemplo real — Wi-Fi em casa (9º ano, LP, RJ):**

| Grupo | Resposta | Proficiência média (IC 95%) | n |
|-------|----------|-----------------------------|---|
| Sem Wi-Fi | A | 244,2 (242,5 – 245,9) | 9.422 |
| Com Wi-Fi | B | 263,6 (259,5 – 267,6) | 101.587 |

A diferença de 19,3 pontos (d = 0,38) é testada com erro-padrão de desenho: t = 8,5, p < 0,001.

### 6.6 Infraestrutura escolar (diretor) vs. proficiência

As respostas dos diretores sobre tecnologia na escola são cruzadas com a proficiência média da escola (`MEDIA_*` de `TS_ESCOLA`) pelo identificador `ID_ESCOLA`. Como `TS_DIRETOR` tem uma linha por escola **e por série avaliada** (com as mesmas respostas), o questionário é antes reduzido a **uma linha por escola**. A unidade de análise é a escola (médias do INEP, sem pesos); os testes tratam cada escola como uma observação.

### 6.7 Formação tecnológica do professor vs. proficiência

As respostas dos professores são cruzadas com a proficiência dos alunos pelo identificador de turma (`ID_TURMA`). O SAEB **não identifica a disciplina do professor**: em turmas com mais de um professor respondente (em geral LP e MT, no 9º ano e no Ensino Médio), cada aluno é associado a todos eles. A unidade de análise é o **par aluno–professor**; o peso de cada par é o peso do aluno dividido pelo número de professores respondentes da turma (cada aluno soma, no total, o seu peso), e os testes usam a escola como conglomerado — o que também trata a dependência entre os pares de um mesmo aluno.

---

## 7. Dados "criados" por manipulação estatística

Esses dados **não existem diretamente nas fontes originais**. São construídos pela aplicação por meio de cálculos, combinações e transformações.

### 7.1 Índice Digital Composto (0–8)

Este é o dado mais elaborado criado pela aplicação. Combina **quatro perguntas** do questionário do aluno em um único índice numérico. Veja detalhes na [seção 9](#9-índice-digital-composto).

### 7.2 Faixas do Índice Digital

O índice (0–8) é dividido em três faixas para facilitar a interpretação:
- **Baixo** (0–2): Acesso digital muito limitado
- **Médio** (3–5): Acesso parcial
- **Alto** (6–8): Acesso amplo a tecnologias digitais

### 7.3 Intervalos de confiança

Quando a aplicação reporta uma média, ela muitas vezes também calcula um **intervalo de confiança** — uma faixa que indica onde provavelmente está o verdadeiro valor da população. Veja [seção 8.1](#81-intervalo-de-confiança).

### 7.4 Tamanhos de efeito (Cohen's d)

O **d de Cohen** é um valor calculado pela aplicação que expressa a magnitude prática de uma diferença, independentemente do tamanho da amostra. Veja [seção 8.3](#83-tamanho-de-efeito-d-de-cohen).

### 7.5 Estatísticas de teste (t, F, p-valor)

Todos os valores de p-valor, estatísticas t e F são calculados pela aplicação a partir dos dados brutos. Não existem nas fontes originais.

### 7.6 Coeficientes de correlação

Os valores de correlação de Pearson (r) mostrados no dashboard são calculados pela aplicação: ponderados pelos pesos amostrais no nível do aluno (índice digital × proficiência) e simples (sem pesos) no nível da escola (formação docente × proficiência, calculado no navegador).

### 7.7 Linha de tendência (regressão linear)

No gráfico de correlação entre formação docente e proficiência (seção Professores > Correlações), a linha de tendência é calculada pelo frontend usando **regressão linear simples**:

```
y = a × x + b

onde:
    a (inclinação) = [n × Σ(xy) − Σx × Σy] / [n × Σ(x²) − (Σx)²]
    b (intercepto)  = [Σy − a × Σx] / n
```

Essa linha mostra a "direção geral" da relação: se sobe (inclinação positiva), mais formação tende a estar associada a maior proficiência; se é quase horizontal, não há relação clara.

### 7.8 Resumo dos cruzamentos tecnológicos

A tabela-resumo na seção "Cruzamentos Tech" é construída executando **11 análises distintas** (4 do aluno, 5 do diretor, 2 do professor), coletando os resultados e ordenando por **tamanho de efeito numa escala comum**: |d| para as variáveis binárias e, para as ANOVAs, o equivalente-d do η² (d ≈ 2·√(η²/(1−η²))). A estatística F não é usada na ordenação, porque cresce com o tamanho da amostra. Inclui a correção de Bonferroni para múltiplas comparações.

---

## 8. Métodos estatísticos explicados

Esta seção explica, de forma acessível, cada método estatístico utilizado na aplicação.

### 8.1 Intervalo de confiança

#### O que é?

Quando calculamos a proficiência média a partir de uma amostra, estamos **estimando** a média real da população. O intervalo de confiança nos diz: "temos 95% de confiança de que a verdadeira média está entre X e Y."

#### Como é calculado? (erro-padrão de desenho)

Alunos de uma mesma escola não são independentes: compartilham professores, recursos e contexto. Tratá-los como uma amostra aleatória simples produziria intervalos estreitos demais e p-valores pequenos demais. Por isso, nas análises com microdados de alunos, a aplicação calcula o erro-padrão por **linearização de Taylor**, considerando o desenho do SAEB — **estratos** (`ESTRATO`) e **conglomerados** (escolas, `ID_ESCOLA`) —, o mesmo estimador "com reposição" do `svy` do Stata e do pacote `survey` do R:

```
Média ponderada:  ȳ = Σ wᵢ yᵢ / Σ wᵢ
Valores linearizados de cada aluno:  zᵢ = wᵢ (yᵢ − ȳ) / Σ wᵢ
Total por escola g do estrato h:  T_hg = Σ_{i ∈ g} zᵢ

Var(ȳ) = Σ_h  n_h / (n_h − 1) · Σ_g (T_hg − T̄_h)²
EP = √Var(ȳ)
IC = ȳ ± t_crítico × EP,   com gl = nº de escolas − nº de estratos
```

Estratos com uma única escola são centrados na média geral (opção conservadora "adjust" do pacote `survey`). **Subgrupos** (ex.: alunos sem Wi-Fi, um nível de INSE, a rede pública) são estimados como **domínios**: o desenho completo — todos os alunos da UF e série — é mantido, e quem está fora do subgrupo entra com valor linearizado zero. Recortar a amostra ao subgrupo descartaria as escolas sem membros e subestimaria a variância. Grupos concentrados numa única escola não têm variância estimável: seu intervalo e seus testes não são calculados. A implementação está em `backend/analysis/stats_utils.py` e foi validada contra o estimador de conglomerados do `statsmodels` (mesmos erros-padrão).

Nas análises em que a **escola é a unidade** (infraestrutura do diretor × média da escola; formação docente × média da escola), cada escola é uma observação e usa-se a fórmula de amostragem aleatória simples.

#### Exemplo real

A proficiência média de LP no 9º ano do RJ é 261,3, com IC 95% de [257,5 ; 265,1]: "estimamos que a verdadeira média da população está entre 257,5 e 265,1 pontos, com 95% de confiança". O intervalo é relativamente largo porque a rede privada — com média bem mais alta — é representada por uma amostra de escolas.

#### Efeito do desenho amostral (DEFF)

O **DEFF** (Design Effect) é a razão entre a variância de desenho e a variância que se teria com uma amostra aleatória simples do mesmo tamanho. Com a conglomeração por escola, o DEFF costuma ser bem maior que 1 — por isso os intervalos e testes de desenho são mais largos e mais conservadores que os ingênuos.

### 8.2 Teste t (diferença de duas médias)

#### O que é?

É um teste que responde à pergunta: "a diferença observada entre dois grupos é grande o suficiente para não ser atribuída ao acaso?"

#### Quando é usado?

Sempre que comparamos **dois grupos** — por exemplo, escolas públicas vs. privadas, ou alunos com Wi-Fi vs. sem Wi-Fi.

#### Como funciona?

1. Calculam-se as médias ponderadas dos dois grupos
2. Calcula-se a diferença das médias (sempre "Sim − Não" nas variáveis de tecnologia)
3. Calcula-se o erro-padrão da diferença **pelo desenho amostral**: as duas médias são linearizadas conjuntamente, de modo que escolas com alunos nos dois grupos contribuem também com a covariância entre as médias:

```
Var(ȳ₁ − ȳ₂) = Var(ȳ₁) + Var(ȳ₂) − 2·Cov(ȳ₁, ȳ₂)
t = (ȳ₁ − ȳ₂) / √Var(ȳ₁ − ȳ₂),   gl = nº de escolas − nº de estratos
```

4. Calcula-se o **p-valor** (bicaudal): a probabilidade de observar uma diferença tão grande ou maior se não houvesse diferença real entre os grupos.

Nas comparações em que a escola é a unidade (variáveis do diretor), usa-se o teste t de Welch clássico (ponderado), com graus de liberdade de Welch–Satterthwaite.

#### Interpretação do p-valor

- **p < 0,05**: Consideramos a diferença **estatisticamente significativa** (improvável de ter ocorrido por acaso)
- **p < 0,001**: Diferença altamente significativa
- **p ≥ 0,05**: Não podemos afirmar que há diferença real

> **Cuidado:** Um p-valor pequeno não diz nada sobre a **magnitude** da diferença. Por isso, a aplicação também calcula o d de Cohen.

#### Exemplo real

Wi-Fi em casa, 9º ano, LP, RJ: com Wi-Fi 263,6, sem Wi-Fi 244,2 — diferença de 19,3 pontos, t = 8,5 com erro-padrão de desenho, p < 0,001. (Tratando os alunos como independentes, o t seria muito maior; a conglomeração por escola reduz a "quantidade efetiva de informação".)

### 8.3 Tamanho de efeito (d de Cohen)

#### O que é?

O d de Cohen mede a **magnitude prática** de uma diferença entre dois grupos. Enquanto o p-valor diz se a diferença é estatisticamente significativa, o d de Cohen diz se ela é **grande o suficiente para importar na prática**.

#### Fórmula

```
         média₁ − média₂
d = ─────────────────────────
        √(variância_pooled)

onde:
                   Σw₁ × var₁ + Σw₂ × var₂
variância_pooled = ────────────────────────
                         Σw₁ + Σw₂
```

Cada variância intragrupo `var_g` utiliza correção de Bessel para pesos de confiabilidade (*reliability weights*): `V₁ / (V₁ − V₂/V₁)`, com `V₁ = Σw_i` e `V₂ = Σw_i²` (exigindo pelo menos 2 observações válidas com peso positivo em cada grupo). A variância *pooled* (combinada) pondera cada grupo pela sua fração populacional `Σw_g / (Σw₁ + Σw₂)`, o que torna o estimador **estritamente invariante à escala dos pesos** (multiplicar todos os pesos por qualquer constante positiva `c > 0` preserva exatamente o valor de `d`).

#### Classificação (convenção de Cohen)

| Valor de |d| | Classificação | Significado prático |
|------------|---------------|---------------------|
| < 0,2 | **Insignificante** | Diferença negligenciável |
| 0,2 – 0,5 | **Pequeno** | Diferença perceptível, mas modesta |
| 0,5 – 0,8 | **Médio** | Diferença substantiva |
| > 0,8 | **Grande** | Diferença muito expressiva |

#### Exemplo

Na comparação com/sem Wi-Fi (9º ano, LP, RJ), d = 0,38: a diferença entre os grupos equivale a pouco mais de um terço de desvio padrão. É um efeito **pequeno** — perceptível, mas não dramático.

### 8.4 ANOVA (Análise de Variância)

#### O que é?

Enquanto o teste t compara **dois** grupos, a ANOVA compara **três ou mais** grupos simultaneamente. Responde: "há pelo menos um grupo significativamente diferente dos demais?"

#### Quando é usada?

Quando a variável de tecnologia tem mais de duas categorias — por exemplo, "computadores na escola" com respostas de A (não tem) a E (muito adequado). Além do F, a aplicação reporta o **η²** (proporção da variância explicada pelos grupos) como tamanho de efeito; para ordenar o resumo dos cruzamentos em uma escala comum ao d de Cohen, o η² é convertido em f de Cohen (f = √(η²/(1−η²))) e em d ≈ 2f.

#### Como funciona?

A ANOVA clássica decompõe a variação total dos dados em duas partes:

1. **Variação entre grupos** (SS_entre): quanto as médias dos grupos diferem da média geral

```
SS_entre = Σ [Σw_g × (média_g − média_geral)²]
```

2. **Variação dentro dos grupos** (SS_dentro): quanto os indivíduos variam dentro de cada grupo

```
SS_dentro = Σ_g [Σ w_i × (x_i − média_g)²]
```

3. O **η²** = SS_entre / (SS_entre + SS_dentro) é a proporção da variação explicada pelos grupos (tamanho de efeito).

**Teste de significância com o desenho amostral.** Nas análises com microdados de alunos (e pares aluno–professor), a igualdade das k médias é testada por um **teste de Wald** com a matriz de covariância das médias obtida por linearização (seção 8.1), com a correção F de Korn–Graubard usada pelo Stata `svy`:

```
W = (C ȳ)ᵀ (C V Cᵀ)⁻¹ (C ȳ)        (C = contrastes "grupo 1 − grupo j")
F = (d − q + 1) / (d · q) × W,     q = k − 1,  d = nº de escolas − nº de estratos
p-valor: distribuição F(q, d − q + 1)
```

Grupos concentrados numa única escola ficam fora do teste (continuam nas médias descritivas). Nas análises em que a escola é a unidade (diretor), usa-se o F clássico, MS_entre / MS_dentro, com (k − 1, N − k) graus de liberdade.

#### Interpretação

- **F grande + p pequeno**: Pelo menos um grupo é significativamente diferente
- **F ≈ 1**: As diferenças entre grupos são comparáveis à variação esperada pelo acaso (sem efeito)
- O **η²** indica a magnitude: ~0,01 pequeno, ~0,06 médio, ~0,14 grande (convenção de Cohen)

### 8.5 Correlação de Pearson (ponderada)

#### O que é?

Mede a **força e direção** da relação linear entre duas variáveis numéricas. O valor r varia de −1 a +1.

#### Fórmula (versão ponderada)

```
              Σ w_i × (x_i − x̄) × (y_i − ȳ)
r = ───────────────────────────────────────────────────
    √[Σ w_i × (x_i − x̄)²] × √[Σ w_i × (y_i − ȳ)²]

onde x̄ e ȳ são médias ponderadas
```

#### P-valor da correlação

Para testar se r é diferente de zero, a aplicação testa a inclinação da regressão ponderada de y em x (a hipótese nula é a mesma: ausência de relação linear), com erro-padrão de desenho (estratos e escolas) e gl = nº de escolas − nº de estratos. Sem informação de desenho, usa-se o teste clássico:

```
t = r × √(n − 2) / √(1 − r²),   com (n − 2) graus de liberdade
```

#### Interpretação

| Valor de |r| | Interpretação |
|-------------|---------------|
| 0,0 – 0,1 | Correlação negligenciável |
| 0,1 – 0,3 | Correlação fraca |
| 0,3 – 0,5 | Correlação moderada |
| 0,5 – 0,7 | Correlação forte |
| 0,7 – 1,0 | Correlação muito forte |

#### Exemplo na aplicação

Na relação entre o Índice Digital (0–8) e a proficiência (9º ano, LP, RJ), r = 0,25 (p < 0,001 com erro-padrão de desenho): uma correlação fraca e positiva — alunos com maior acesso digital tendem a ter proficiência mais alta, mas muitos outros fatores influenciam o desempenho.

> **Atenção:** Correlação não implica causalidade! O fato de alunos com mais tecnologia terem melhores notas não significa que a tecnologia *causou* as melhores notas. O nível socioeconômico é um **fator confundidor**: famílias mais ricas tendem a ter mais tecnologia E melhores condições de estudo. Por isso a aplicação oferece a estratificação por INSE.

### 8.6 Teste qui-quadrado

#### O que é?

Testa se duas variáveis categóricas são independentes. É usado quando ambas as variáveis são qualitativas (não numéricas).

#### Na aplicação

Disponível no módulo de análises, mas menos proeminente no dashboard. Utiliza a implementação padrão de `scipy.stats.chi2_contingency()`.

---

## 9. Índice Digital Composto

### Por que criar um índice?

As quatro perguntas sobre tecnologia no questionário do aluno medem aspectos diferentes do acesso digital. Analisá-las isoladamente é útil, mas combiná-las em um único índice permite uma visão mais completa: **qual o nível geral de acesso digital do aluno?**

### Como é construído?

Cada resposta é convertida em um valor numérico:

| Pergunta | Resposta A | Resposta B | Resposta C | Resposta D |
|----------|-----------|-----------|-----------|-----------|
| Q12b (computadores) | 0 | 1 | 2 | 3 |
| Q12g (celulares com internet) | 0 | 1 | 2 | 3 |
| Q13a (streaming) | 0 | 1 | — | — |
| Q13b (Wi-Fi) | 0 | 1 | — | — |

O **índice** é a soma dos quatro valores:

```
Índice = Q12b_código + Q12g_código + Q13a_código + Q13b_código

Resultado: valor entre 0 (nenhum acesso) e 8 (acesso máximo)
```

### Exemplo

Um aluno que tem 1 computador (B=1), 2 celulares com internet (C=2), não tem streaming (A=0) e tem Wi-Fi (B=1):

```
Índice = 1 + 2 + 0 + 1 = 4 → Faixa "Médio"
```

### Faixas interpretativas

| Faixa | Índice | Interpretação |
|-------|--------|---------------|
| **Baixo** | 0–2 | Acesso digital muito limitado (sem computador, sem internet fixa) |
| **Médio** | 3–5 | Acesso parcial (tem alguns dispositivos, mas não todos) |
| **Alto** | 6–8 | Acesso amplo (múltiplos dispositivos, Wi-Fi, streaming) |

### Análise realizada

Com o índice construído, a aplicação:

1. Calcula a **média de proficiência** para cada valor do índice (0, 1, 2, ..., 8)
2. Calcula a **correlação de Pearson** entre o índice e a proficiência
3. Calcula médias por **faixa** (Baixo, Médio, Alto)
4. Opcionalmente, repete a análise **estratificada por INSE** (apenas alunos com `IN_INSE = 1`) para controlar o efeito socioeconômico

---

## 10. Correção para comparações múltiplas (Bonferroni)

### O problema

Quando realizamos muitos testes estatísticos simultaneamente, a chance de encontrar um resultado "significativo" por acaso aumenta. É como jogar uma moeda: se jogar 1 vez, a chance de dar cara é 50%. Se jogar 20 vezes, é quase certo que ao menos uma será cara.

Na aplicação, realizamos **11 testes** simultâneos (4 variáveis do aluno + 5 do diretor + 2 do professor). Com α = 0,05 (5% de chance de falso positivo por teste), a probabilidade de pelo menos um falso positivo é:

```
P(ao menos 1 falso positivo) = 1 − (1 − 0,05)¹¹ ≈ 43%
```

Quase metade das vezes encontraríamos pelo menos um resultado "significativo" que na verdade é falso!

### A solução: Bonferroni

A correção de Bonferroni divide o nível de significância pelo número de testes:

```
α_ajustado = 0,05 / 11 ≈ 0,0045
```

Agora, para um resultado ser considerado significativo, o p-valor precisa ser menor que 0,0045 (em vez de 0,05). Isso é mais rigoroso, mas reduz drasticamente a chance de falsos positivos.

### Na aplicação

A tabela-resumo de cruzamentos tecnológicos mostra:
- **"Sim"** (badge verde): significativo mesmo após Bonferroni (p < α_ajustado)
- **"*"** (badge amarelo): significativo pelo critério convencional (p < 0,05) mas não após Bonferroni
- **"Não"** (badge cinza): não significativo

---

## 11. Fluxo completo dos dados

```
┌──────────────────────────────────────────────────────────────────┐
│                     FONTES ORIGINAIS                             │
│                                                                  │
│   SAEB 2023 (INEP/MEC)              TIC Educação 2023           │
│   • Microdados CSV                   (CETIC.br/NIC.br)          │
│   • ~7,1 milhões de alunos           • Planilhas XLSX           │
│   • ~411 mil professores             • 69 indicadores           │
│   • ~107 mil diretores               • Sudeste (proxy) e Brasil │
│   • ~70 mil escolas                                             │
└──────────────────────┬──────────────────────────┬───────────────┘
                       │                          │
                       ▼                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CONVERSÃO (ETL)                                │
│                                                                  │
│   CSV / XLSX  ──►  Parquet (formato colunar eficiente)           │
│   Microdados ficam só nos Parquet (lidos pelas análises)         │
└──────────────────────┬──────────────────────────────────────────-┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                PRÉ-COMPUTAÇÃO (DuckDB)                           │
│                                                                  │
│   14 tabelas agregadas (~5 MB):                                  │
│                                                                  │
│   DESCRITIVOS DIRETOS          CRUZAMENTOS             CRIADOS   │
│   • KPIs do RJ                 • Profic. × INSE        • Índice  │
│   • Contagem de escolas        • Profic. × Localiz.      Digital │
│   • Ranking por UF             • Profic. × Rede         (0–8)   │
│   • Níveis de proficiência     • Tech aluno × Profic.   • Faixas │
│   • Respostas questionários    • Profic. × INSE (aluno)          │
│   • Indicadores TIC                                              │
│                                                                  │
│   Calculados sob demanda (Parquet): testes t/ANOVA/correlação    │
│   com erro-padrão de desenho, d de Cohen, η², tech escola e      │
│   professor × proficiência, formação docente por escola          │
└──────────────────────┬──────────────────────────────────────────-┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     API (FastAPI)                                 │
│                                                                  │
│   /saeb/overview           → KPIs e visão geral                  │
│   /saeb/proficiency        → Proficiência por UF/série           │
│   /saeb/equity/gap         → Lacuna pública × privada            │
│   /saeb/equity/inse        → Proficiência por nível INSE         │
│   /saeb/equity/location    → Urbana × Rural                      │
│   /saeb/teachers/formation → Formação docente × proficiência     │
│   /saeb/questionnaire/*    → Respostas de questionários          │
│   /tic/*                   → Indicadores TIC (Sudeste e Brasil)  │
│   /cross/student-tech      → Tecnologia aluno × desempenho       │
│   /cross/director-tech     → Infraestrutura escola × desempenho  │
│   /cross/teacher-tech      → Formação tech prof. × desempenho    │
│   /cross/digital-index     → Índice digital × desempenho         │
│   /cross/summary           → Resumo com 11 testes + Bonferroni   │
└──────────────────────┬──────────────────────────────────────────-┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    DASHBOARD (Frontend)                           │
│                                                                  │
│   Gráficos interativos com ECharts:                              │
│   • Barras (proporções, contagens, comparações)                  │
│   • Dispersão com linha de tendência (correlações)               │
│   • Forest plot (tamanhos de efeito)                             │
│   • Linhas (índice digital)                                      │
│                                                                  │
│   + Cálculos no frontend:                                        │
│   • Regressão linear (linha de tendência)                        │
│   • Pearson r (correlação formação × proficiência)               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 12. Limitações e cuidados na interpretação

### 12.1 Correlação ≠ Causalidade

A principal limitação deste tipo de análise é que **associações estatísticas não provam causas**. Por exemplo:

- Alunos com Wi-Fi em casa têm notas mais altas → Isso não significa que Wi-Fi *causa* melhor desempenho. Famílias com mais recursos financeiros têm mais chance de ter Wi-Fi E de oferecer melhores condições de estudo.

Para mitigar isso, a aplicação permite **estratificar por INSE**: ao comparar apenas alunos do mesmo nível socioeconômico, controlamos parcialmente esse fator confundidor.

### 12.2 TIC Educação por região, não por estado

Os indicadores de tecnologia da TIC Educação são da **região Sudeste** (SP, MG, ES e RJ), usada como proxy do RJ, e do Brasil. Os valores específicos do RJ podem diferir. As margens de erro do Sudeste ficam, em geral, entre ±1 e ±5 pontos percentuais.

### 12.3 Dados de escola vs. dados individuais

Algumas análises usam dados agregados por escola (médias da escola), enquanto outras usam dados individuais (cada aluno). Análises em nível de escola tendem a mostrar correlações mais fortes, porque a agregação suaviza a variação individual — um fenômeno chamado **falácia ecológica** quando generalizamos conclusões do nível agregado para o individual.

### 12.4 Respostas autodeclaradas

Os dados dos questionários do SAEB são baseados em respostas autodeclaradas por alunos, professores e diretores. Estão sujeitas a vieses de resposta social (tendência a dar respostas "socialmente desejáveis") e a erros de interpretação das perguntas.

### 12.5 Significância estatística vs. significância prática

Com amostras de centenas de milhares de alunos, mesmo diferenças pequenas podem ser estatisticamente significativas. Por isso a aplicação reporta o **d de Cohen** e o **η²** (tamanhos de efeito) para que o leitor avalie se a diferença é relevante na prática.

### 12.6 Comparações múltiplas

A aplicação realiza 11 testes simultâneos na análise de cruzamentos tecnológicos. A correção de Bonferroni é aplicada para evitar falsos positivos, mas é uma correção conservadora — pode deixar de detectar efeitos reais (falsos negativos).

### 12.7 Desenho amostral e inferência

Erros-padrão, intervalos e testes com microdados de alunos consideram estratos e conglomerados (escolas), mas não os ajustes finos de calibração dos pesos nem a correção para população finita (relevante na rede pública, censitária). Assim, devem ser lidos como inferência sobre a relação entre as variáveis (modelo de superpopulação), não como margens de erro oficiais do INEP. As análises com a escola como unidade não usam pesos de escola.

### 12.8 Vínculo professor–aluno

O SAEB não identifica a disciplina do professor. Em turmas com professores de LP e de MT, os dois são associados a todos os alunos da turma; a unidade de análise é o par aluno–professor (com o peso do aluno dividido entre os professores da turma).

### 12.9 Cobertura das tabelas de escola

`TS_ESCOLA` (níveis de proficiência, formação docente, médias por escola) contém apenas escolas públicas. Os gráficos de níveis de proficiência e de formação docente referem-se, portanto, à rede pública.

---

## 13. Glossário de termos técnicos

| Termo | Significado |
|-------|------------|
| **ANOVA** | Análise de Variância — teste que compara médias de 3 ou mais grupos |
| **Bonferroni** | Correção que ajusta o nível de significância quando múltiplos testes são realizados |
| **Cohen's d** | Medida do tamanho de efeito que expressa a diferença entre dois grupos em unidades de desvio padrão |
| **Correlação de Pearson (r)** | Medida da força e direção da relação linear entre duas variáveis (-1 a +1) |
| **Conglomerado** | Grupo de observações selecionado em conjunto (no SAEB, a escola); observações do mesmo conglomerado tendem a ser parecidas |
| **DEFF** | Design Effect — razão entre a variância com o desenho amostral real e a variância de uma amostra aleatória simples |
| **Estrato** | Subdivisão da população em que a seleção da amostra é feita separadamente (`ESTRATO` no SAEB) |
| **η² (eta ao quadrado)** | Proporção da variação explicada pelos grupos numa ANOVA (tamanho de efeito) |
| **Linearização de Taylor** | Técnica para calcular erros-padrão de estimadores (médias, diferenças, inclinações) considerando o desenho amostral |
| **Desvio padrão** | Medida de dispersão que indica o quanto os valores se afastam da média |
| **ETL** | Extract, Transform, Load — processo de preparação dos dados |
| **Estatística F** | Razão entre variação entre grupos e variação dentro dos grupos (usada na ANOVA) |
| **Graus de liberdade** | Parâmetro que reflete o tamanho efetivo da amostra, usado no cálculo de p-valores |
| **INSE** | Indicador de Nível Socioeconômico do aluno, baseado em bens e renda familiar |
| **Intervalo de confiança** | Faixa de valores onde provavelmente está o verdadeiro parâmetro da população |
| **Lacuna (gap)** | Diferença de proficiência entre dois grupos (ex: pública vs. privada) |
| **Média ponderada** | Média que leva em conta o peso (importância relativa) de cada observação |
| **Microdados** | Registros individuais (um por aluno/professor/escola) de uma pesquisa |
| **Nível de proficiência** | Classificação do desempenho do aluno em faixas (0 a 9 ou 10) |
| **p-valor** | Probabilidade de observar os dados se não houvesse efeito real. Quanto menor, mais forte a evidência |
| **Parquet** | Formato de arquivo otimizado para dados tabulares grandes |
| **Peso amostral** | Fator que indica quantas pessoas da população cada indivíduo da amostra representa |
| **Proficiência (escala SAEB)** | Nota padronizada (~100 a ~400) que mede as habilidades demonstradas pelo aluno |
| **Regressão linear** | Modelo que encontra a reta que melhor descreve a relação entre duas variáveis |
| **SAEB** | Sistema de Avaliação da Educação Básica — avaliação nacional do MEC |
| **Significância estatística** | Quando o p-valor é menor que o nível α (usualmente 0,05), indicando resultado improvável por acaso |
| **Teste t** | Teste que compara médias de dois grupos; na aplicação, com erro-padrão de desenho (aluno) ou de Welch (escola) |
| **TIC** | Tecnologias da Informação e Comunicação |
| **Variância** | Medida de dispersão — a média dos quadrados dos desvios em relação à média |
