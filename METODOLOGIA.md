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
| **TIC Educação** | CETIC.br / NIC.br | 2023 | Uso de tecnologia, IA e infraestrutura digital nas escolas | Por região (não por estado) |

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
| `TS_ESCOLA` | Dados agregados por escola | ~70 mil escolas |
| `TS_PROFESSOR` | Respostas dos professores | ~411 mil registros |
| `TS_DIRETOR` | Respostas dos diretores | ~107 mil registros |

### 2.2 Variáveis de proficiência

Cada aluno possui uma **nota na escala SAEB** para cada disciplina avaliada:

- **`PROFICIENCIA_LP_SAEB`** — Língua Portuguesa
- **`PROFICIENCIA_MT_SAEB`** — Matemática

Essas notas **não são como notas de prova** (0 a 10). São valores em uma escala contínua (tipicamente entre 100 e 400 pontos) que permite comparar desempenho entre séries, anos e regiões. Quanto maior o valor, maior a proficiência do aluno.

### 2.3 Pesos amostrais

O SAEB utiliza **amostragem estratificada**, o que significa que nem todos os alunos têm a mesma probabilidade de serem incluídos na amostra. Para compensar isso, cada aluno recebe um **peso** que indica quantos alunos da população ele "representa":

- **`PESO_ALUNO_LP`** — Peso para análises de Língua Portuguesa
- **`PESO_ALUNO_MT`** — Peso para análises de Matemática

> **Exemplo:** Se um aluno tem peso 3,5, isso significa que ele "vale por" 3,5 alunos na estimativa populacional. Sem usar os pesos, os resultados seriam enviesados — superestimando regiões com maior cobertura amostral.

**Toda média calculada nesta aplicação é uma média ponderada** que utiliza esses pesos. Isso é fundamental para que os resultados reflitam a realidade da população escolar, e não apenas da amostra.

### 2.4 Variáveis socioeconômicas

- **`INSE_ALUNO`** — Índice de Nível Socioeconômico (escala contínua de 0 a ~200)
- **`NU_TIPO_NIVEL_INSE`** — Nível INSE categorizado em faixas de 1 (mais baixo) a 8 (mais alto)
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
| `TX_Q037` | Frequência de uso de tecnologia no ensino | A = Nunca ... E = Sempre |

### 2.7 Variáveis do questionário do diretor

| Código | Pergunta | Respostas |
|--------|----------|-----------|
| `TX_Q034` | Qualidade dos computadores da escola | A = Não tem ... E = Excelente |
| `TX_Q035` | Software educacional | A = Não tem ... E = Excelente |
| `TX_Q036` | Internet banda larga | A = Não tem ... E = Excelente |
| `TX_Q194` | Escola promove projetos de ciência/tecnologia? | A = Sim, B = Não |
| `TX_Q219` | Escola adotou novas tecnologias educacionais? | A = Sim, B = Não |

### 2.8 Variáveis da escola

| Coluna | Descrição |
|--------|-----------|
| `MEDIA_5EF_LP`, `MEDIA_5EF_MT` | Proficiência média dos alunos do 5º ano |
| `MEDIA_9EF_LP`, `MEDIA_9EF_MT` | Proficiência média dos alunos do 9º ano |
| `PC_FORMACAO_DOCENTE_INICIAL` | % de professores com formação adequada na escola |
| `NIVEL_0_LP5` a `NIVEL_9_LP5` | % de alunos em cada nível de proficiência (LP, 5º ano) |

---

## 3. TIC Educação 2023 — Tecnologia nas escolas

### 3.1 O que é a pesquisa TIC Educação?

A pesquisa TIC Educação, conduzida pelo CETIC.br (Centro Regional de Estudos para o Desenvolvimento da Sociedade da Informação), investiga o uso de tecnologias da informação e comunicação nas escolas brasileiras.

> **Importante:** Os dados da TIC Educação são disponibilizados **por região** (Norte, Nordeste, Sudeste, Sul, Centro-Oeste), e não por estado. Na aplicação, utilizamos os dados da **região Sudeste** como proxy para o Rio de Janeiro. Isso é informado ao usuário no dashboard.

### 3.2 Arquivos utilizados

| Arquivo | Conteúdo |
|---------|----------|
| `tic_educacao_2023_escolas_tabela_proporcao_v1.0.xlsx` | Proporções (%) de escolas com cada característica |
| `tic_educacao_2023_escolas_tabela_total_v1.0.xlsx` | Contagens absolutas |
| `tic_educacao_2023_escolas_tabela_margem_de_erro_v1.0.xlsx` | Margens de erro das estimativas |

### 3.3 Indicadores utilizados

Os indicadores são organizados em categorias temáticas:

#### Infraestrutura (A1–A8)

| Indicador | O que mede |
|-----------|------------|
| A1 | % de escolas com computador |
| A2 | % com portátil disponível para alunos |
| A3 | % com tablet disponível para alunos |
| A4 | % com acesso à internet |
| A5 | % com banda larga |
| A6 | % com Wi-Fi |
| A7 | % com projetor |
| A8 | % com lousa digital |

#### IA e Sistemas de Dados (E4A, E4B, E5, E6, F6)

| Indicador | O que mede |
|-----------|------------|
| E4A | % de escolas usando biometria |
| E4B | % usando reconhecimento facial |
| E5 | % usando analytics/learning analytics |
| E6 | % usando sistemas de inteligência artificial |
| F6 | % usando chatbot |

#### Formação Digital Docente (J1–J4)

| Indicador | O que mede |
|-----------|------------|
| J1 | % de escolas que oferecem formação em programação |
| J2 | % que oferecem formação em robótica |
| J3 | % que oferecem formação em uso pedagógico de TIC |
| J4 | % que oferecem formação em segurança online |

#### Privacidade e Ética (H1–H7)

| Indicador | O que mede |
|-----------|------------|
| H1 | % de escolas com política de privacidade |
| H3 | % que promovem debate sobre privacidade |
| H4 | % que obtêm consentimento para uso de dados |
| H5 | % com proteção de dados implementada |
| H6 | % que não adotaram medidas de privacidade |
| H7 | % com preocupação com privacidade |

### 3.4 Filtros aplicados

Ao exibir esses dados, a aplicação filtra apenas registros onde:
- `tipo = 'proporcao'` (proporção, não contagem absoluta)
- `valor_corte = 'TOTAL'` (total geral, sem subdivisão por porte ou rede)

---

## 4. Como os dados são processados (ETL)

ETL significa **Extract, Transform, Load** (Extrair, Transformar, Carregar). É o processo que transforma os dados brutos em tabelas prontas para consulta.

### 4.1 Etapa 1: Conversão para formato eficiente

Os dados brutos (CSV e XLSX) são convertidos para o formato **Parquet**, um formato colunar otimizado para consultas analíticas. Isso reduz o tempo de leitura de minutos para segundos.

### 4.2 Etapa 2: Pré-computação de tabelas agregadas

O script `precompute.py` lê os arquivos Parquet e cria **15 tabelas pré-computadas** no banco de dados DuckDB. Essas tabelas armazenam resultados já agregados (médias, contagens, etc.) para que o dashboard responda em milissegundos, sem precisar reprocessar milhões de registros a cada consulta.

**Tabelas criadas:**

| Tabela | O que contém | Tipo de dado |
|--------|--------------|--------------|
| `kpi_rj` | Totais de alunos e médias gerais do RJ | Descritivo direto |
| `kpi_escolas_rj` | Contagem de escolas (total, públicas, privadas) | Descritivo direto |
| `prof_by_uf_serie_disc` | Proficiência média por UF, série e disciplina | Descritivo (agregado com pesos) |
| `prof_niveis_rj` | Distribuição dos alunos por nível de proficiência (RJ) | Descritivo direto |
| `prof_niveis_nacional` | Distribuição nacional por nível de proficiência | Descritivo direto |
| `prof_by_inse` | Proficiência por nível socioeconômico (RJ) | Cruzamento |
| `prof_by_location_rj` | Proficiência urbana vs. rural (RJ) | Cruzamento |
| `escola_formacao_rj` | Formação docente vs. proficiência por escola | Cruzamento |
| `escola_inse_rj` | INSE da escola vs. proficiência | Cruzamento |
| `quest_aluno_rj` | Distribuição de respostas dos alunos | Descritivo direto |
| `quest_professor_rj` | Distribuição de respostas dos professores | Descritivo direto |
| `quest_diretor_rj` | Distribuição de respostas dos diretores | Descritivo direto |
| `cross_aluno_tech_rj` | Acesso à tecnologia do aluno vs. proficiência | Cruzamento com estatística |
| `cross_diretor_tech_rj` | Infraestrutura tecnológica (diretor) vs. proficiência | Cruzamento com estatística |
| `cross_professor_tech_rj` | Formação tecnológica do professor vs. proficiência | Cruzamento com estatística |
| `cross_digital_index_rj` | Índice digital composto vs. proficiência | Criado por manipulação estatística |
| `tic_indicadores` | Indicadores TIC Educação | Descritivo direto |

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

- **Total de alunos avaliados** no RJ, por série
- **Total de escolas** (públicas e privadas)
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

O SAEB classifica os alunos em **níveis de proficiência** (0 a 9 para LP, 0 a 10 para MT), onde cada nível corresponde a um conjunto de habilidades que o aluno demonstra dominar. A aplicação mostra o percentual de alunos do RJ em cada nível.

Esses percentuais vêm diretamente da tabela `TS_ESCOLA` do SAEB, que já traz os valores pré-calculados pelo INEP.

### 5.4 Perfil dos professores

Distribuição das respostas dos professores do RJ aos questionários contextuais:
- **Sexo** (questão Q001)
- **Contribuição da formação em tecnologia** (Q029)
- **Adequação dos computadores na escola** (Q072)

Esses dados são contagens diretas das respostas, sem manipulação estatística.

### 5.5 Indicadores TIC Educação

As proporções de escolas com cada tipo de tecnologia são exibidas diretamente como informadas pela pesquisa TIC Educação — por exemplo, "92,4% das escolas da região Sudeste possuem computador."

---

## 6. Dados cruzados (análises comparativas)

Esses dados **combinam duas variáveis** para responder a perguntas do tipo: "Alunos com acesso a X têm desempenho diferente de alunos sem acesso?"

### 6.1 Lacuna Pública vs. Privada

**Pergunta:** Qual a diferença de proficiência entre alunos de escolas públicas e privadas no RJ?

**Como é calculada:**
1. Separam-se os alunos pela variável `IN_PUBLICA` (0 = privada, 1 = pública)
2. Calcula-se a média ponderada de proficiência para cada grupo
3. A **lacuna** é a subtração: `média_privada − média_pública`

**Teste estatístico aplicado:** Teste t de Welch + Cohen's d (ver [seção 8](#8-métodos-estatísticos-explicados))

### 6.2 Proficiência por nível socioeconômico (INSE)

**Pergunta:** O nível socioeconômico do aluno está relacionado ao seu desempenho?

**Como é calculada:**
1. Os alunos são agrupados por nível INSE (1 a 8)
2. Calcula-se a média ponderada de proficiência para cada nível
3. Calcula-se a **correlação de Pearson** entre o INSE contínuo e a proficiência

### 6.3 Proficiência urbana vs. rural

**Pergunta:** Há diferença de desempenho entre alunos de áreas urbanas e rurais?

**Como é calculada:**
1. Separam-se os alunos por `ID_LOCALIZACAO` (1 = Urbana, 2 = Rural)
2. Calcula-se a média ponderada para cada grupo
3. A lacuna é calculada e testada estatisticamente

### 6.4 Formação docente vs. proficiência

**Pergunta:** Escolas com maior percentual de professores com formação adequada têm melhores resultados?

**Como é calculada:**
1. A tabela `escola_formacao_rj` contém, para cada escola do RJ, o percentual de formação docente (`PC_FORMACAO_DOCENTE_INICIAL`) e a proficiência média dos alunos
2. O gráfico de dispersão (scatter plot) mostra essa relação
3. Uma **linha de tendência** (regressão linear) é traçada
4. O **coeficiente de correlação de Pearson (r)** é exibido

### 6.5 Tecnologia do aluno vs. proficiência

Para cada variável de tecnologia do aluno (computador, Wi-Fi, celular com internet, streaming), a análise compara a proficiência média entre os grupos de resposta.

**Exemplo — Wi-Fi em casa:**

| Grupo | Resposta | Proficiência média |
|-------|----------|--------------------|
| Sem Wi-Fi | A | 195,3 |
| Com Wi-Fi | B | 218,7 |

A diferença de 23,4 pontos é testada estatisticamente para verificar se é significativa.

### 6.6 Infraestrutura escolar (diretor) vs. proficiência

As respostas dos diretores sobre tecnologia na escola são cruzadas com a proficiência média dos alunos daquela escola. Isso usa um **join** (ligação) entre a tabela de diretores e a tabela de escolas pelo identificador `ID_ESCOLA`.

### 6.7 Formação tecnológica do professor vs. proficiência

As respostas dos professores sobre formação tecnológica são cruzadas com a proficiência dos seus alunos. A ligação é feita pelo identificador de turma (`ID_TURMA`): cada professor é vinculado aos alunos que ensina.

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

Os valores de correlação de Pearson (r) mostrados no dashboard são calculados pela aplicação, tanto para relações simples (INSE vs. proficiência) quanto ponderados pelos pesos amostrais.

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

A tabela-resumo na seção "Cruzamentos Tech" é construída executando **11 análises distintas** (4 do aluno, 5 do diretor, 2 do professor), coletando os resultados e ordenando por tamanho de efeito. Inclui a correção de Bonferroni para múltiplas comparações.

---

## 8. Métodos estatísticos explicados

Esta seção explica, de forma acessível, cada método estatístico utilizado na aplicação.

### 8.1 Intervalo de confiança

#### O que é?

Quando calculamos a proficiência média a partir de uma amostra, estamos **estimando** a média real da população. O intervalo de confiança nos diz: "temos 95% de confiança de que a verdadeira média está entre X e Y."

#### Como é calculado?

```
IC = média ± t_crítico × EP

onde:
    EP (erro padrão) = √(variância_ponderada × Σ(w²) / (Σw)²)
    t_crítico = valor da distribuição t de Student com (n − 1) graus de liberdade
```

#### Exemplo

Se a proficiência média de LP no 9º ano do RJ é 245,3 com IC [243,1 ; 247,5], isso significa: "estimamos que a verdadeira média da população está entre 243,1 e 247,5 pontos, com 95% de confiança."

#### Efeito do desenho amostral (DEFF)

O SAEB usa amostragem estratificada, não amostragem aleatória simples. Isso afeta a precisão das estimativas. A aplicação calcula o **DEFF** (Design Effect), que mede quanto a variância é inflada pelo desenho amostral. Quando o DEFF é maior que 1, os intervalos de confiança ficam mais largos para refletir a incerteza adicional.

### 8.2 Teste t de Welch

#### O que é?

É um teste que responde à pergunta: "a diferença observada entre dois grupos é grande o suficiente para não ser atribuída ao acaso?"

#### Quando é usado?

Sempre que comparamos **dois grupos** — por exemplo, escolas públicas vs. privadas, ou alunos com Wi-Fi vs. sem Wi-Fi.

#### Como funciona?

1. Calcula-se a média e a variância ponderada de cada grupo
2. Calcula-se a diferença das médias
3. Calcula-se o erro padrão dessa diferença:

```
EP = √(EP₁² + EP₂²)

onde EP_g = √(variância_g × Σ(w_g²) / (Σw_g)²)
```

4. Calcula-se a **estatística t**:

```
t = (média₁ − média₂) / EP
```

5. Calculam-se os **graus de liberdade** pela fórmula de Welch-Satterthwaite:

```
         (EP₁² + EP₂²)²
gl = ─────────────────────────
     EP₁⁴/(n₁−1) + EP₂⁴/(n₂−1)
```

6. Calcula-se o **p-valor** (bicaudal): a probabilidade de observar uma diferença tão grande ou maior se não houvesse diferença real entre os grupos.

#### Interpretação do p-valor

- **p < 0,05**: Consideramos a diferença **estatisticamente significativa** (improvável de ter ocorrido por acaso)
- **p < 0,001**: Diferença altamente significativa
- **p ≥ 0,05**: Não podemos afirmar que há diferença real

> **Cuidado:** Um p-valor pequeno não diz nada sobre a **magnitude** da diferença. Uma diferença de 0,5 pontos pode ser significativa com amostras enormes, mas ser irrelevante na prática. Por isso, a aplicação também calcula o d de Cohen.

#### Exemplo

Comparando proficiência em LP de alunos com e sem Wi-Fi:

| | Com Wi-Fi | Sem Wi-Fi |
|---|---|---|
| Média ponderada | 218,7 | 195,3 |
| n | 180.000 | 22.000 |

Se o teste retorna t = 15,2 e p < 0,001, concluímos que a diferença de 23,4 pontos é estatisticamente significativa — muito improvável de ter ocorrido ao acaso.

### 8.3 Tamanho de efeito (d de Cohen)

#### O que é?

O d de Cohen mede a **magnitude prática** de uma diferença entre dois grupos. Enquanto o p-valor diz se a diferença é estatisticamente significativa, o d de Cohen diz se ela é **grande o suficiente para importar na prática**.

#### Fórmula

```
         média₁ − média₂
d = ─────────────────────────
        √(variância_pooled)

onde:
                   (Σw₁ − 1) × var₁ + (Σw₂ − 1) × var₂
variância_pooled = ──────────────────────────────────────
                         Σw₁ + Σw₂ − 2
```

A variância *pooled* (combinada) é uma média ponderada das variâncias dos dois grupos, usada como "régua" para medir a diferença.

#### Classificação (convenção de Cohen)

| Valor de |d| | Classificação | Significado prático |
|------------|---------------|---------------------|
| < 0,2 | **Insignificante** | Diferença negligenciável |
| 0,2 – 0,5 | **Pequeno** | Diferença perceptível, mas modesta |
| 0,5 – 0,8 | **Médio** | Diferença substantiva |
| > 0,8 | **Grande** | Diferença muito expressiva |

#### Exemplo

Se d = 0,45 na comparação com/sem Wi-Fi, isso significa que a diferença entre os grupos equivale a quase metade de um desvio padrão. É um efeito **pequeno a médio** — perceptível, mas não dramático.

### 8.4 ANOVA (Análise de Variância)

#### O que é?

Enquanto o teste t compara **dois** grupos, a ANOVA compara **três ou mais** grupos simultaneamente. Responde: "há pelo menos um grupo significativamente diferente dos demais?"

#### Quando é usada?

Quando a variável de tecnologia tem mais de duas categorias — por exemplo, "computadores na escola" com respostas de A (não tem) a E (excelente).

#### Como funciona?

A ANOVA decompõe a variação total dos dados em duas partes:

1. **Variação entre grupos** (SS_between): quanto as médias dos grupos diferem da média geral

```
SS_entre = Σ [Σw_g × (média_g − média_geral)²]
```

2. **Variação dentro dos grupos** (SS_within): quanto os indivíduos variam dentro de cada grupo

```
SS_dentro = Σ_g [Σ w_i × (x_i − média_g)²]
```

3. A **estatística F** é a razão entre as variações:

```
         SS_entre / (k − 1)        MS_entre
F = ──────────────────────── = ────────────
     SS_dentro / (N − k)          MS_dentro

onde k = número de grupos, N = tamanho total
```

Se F é grande, a variação entre os grupos é muito maior do que a variação dentro deles, sugerindo que os grupos são genuinamente diferentes.

#### Interpretação

- **F grande + p pequeno**: Pelo menos um grupo é significativamente diferente
- **F ≈ 1**: As diferenças entre grupos são comparáveis à variação natural dentro dos grupos (sem efeito)

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

Para testar se r é significativamente diferente de zero:

```
              r × √(n − 2)
t_stat = ─────────────────
            √(1 − r²)

p-valor = teste bicaudal com (n − 2) graus de liberdade
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

Na relação entre o Índice Digital (0–8) e a proficiência, um r = 0,35 indicaria uma correlação moderada e positiva: alunos com maior acesso digital tendem a ter proficiência mais alta, embora a relação não seja perfeita (muitos fatores influenciam o desempenho).

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
4. Opcionalmente, repete a análise **estratificada por INSE** para controlar o efeito socioeconômico

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
│   • ~9 milhões de alunos             • Planilhas XLSX           │
│   • ~411 mil professores             • 69 indicadores           │
│   • ~107 mil diretores               • Região Sudeste           │
│   • ~70 mil escolas                                             │
└──────────────────────┬──────────────────────────┬───────────────┘
                       │                          │
                       ▼                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CONVERSÃO (ETL)                                │
│                                                                  │
│   CSV / XLSX  ──►  Parquet (formato colunar eficiente)           │
│   Redução de tempo de leitura: minutos → segundos                │
└──────────────────────┬──────────────────────────────────────────-┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                PRÉ-COMPUTAÇÃO (DuckDB)                           │
│                                                                  │
│   17 tabelas agregadas:                                          │
│                                                                  │
│   DESCRITIVOS DIRETOS          CRUZAMENTOS             CRIADOS   │
│   • KPIs do RJ                 • Profic. × INSE        • Índice  │
│   • Contagem de escolas        • Profic. × Localiz.      Digital │
│   • Ranking por UF             • Profic. × Rede         (0–8)   │
│   • Níveis de proficiência     • Tech aluno × Profic.   • Faixas │
│   • Respostas questionários    • Tech escola × Profic.  • Cohen  │
│   • Indicadores TIC            • Tech prof. × Profic.     d     │
│                                • Formação × Profic.     • p-val  │
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
│   /tic/*                   → Indicadores TIC Educação            │
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

Os dados de tecnologia da TIC Educação são para a **região Sudeste** inteira, não apenas para o RJ. Isso significa que os indicadores incluem também SP, MG e ES. Os valores específicos do RJ podem diferir.

### 12.3 Dados de escola vs. dados individuais

Algumas análises usam dados agregados por escola (médias da escola), enquanto outras usam dados individuais (cada aluno). Análises em nível de escola tendem a mostrar correlações mais fortes, porque a agregação suaviza a variação individual — um fenômeno chamado **falácia ecológica** quando generalizamos conclusões do nível agregado para o individual.

### 12.4 Respostas autodeclaradas

Os dados dos questionários do SAEB são baseados em respostas autodeclaradas por alunos, professores e diretores. Estão sujeitas a vieses de resposta social (tendência a dar respostas "socialmente desejáveis") e a erros de interpretação das perguntas.

### 12.5 Significância estatística vs. significância prática

Com amostras de milhões de alunos, até diferenças muito pequenas podem ser estatisticamente significativas (p < 0,001). Por isso a aplicação reporta o **d de Cohen** (tamanho de efeito) para que o leitor avalie se a diferença é relevante na prática.

### 12.6 Comparações múltiplas

A aplicação realiza 11 testes simultâneos na análise de cruzamentos tecnológicos. A correção de Bonferroni é aplicada para evitar falsos positivos, mas é uma correção conservadora — pode deixar de detectar efeitos reais (falsos negativos).

---

## 13. Glossário de termos técnicos

| Termo | Significado |
|-------|------------|
| **ANOVA** | Análise de Variância — teste que compara médias de 3 ou mais grupos |
| **Bonferroni** | Correção que ajusta o nível de significância quando múltiplos testes são realizados |
| **Cohen's d** | Medida do tamanho de efeito que expressa a diferença entre dois grupos em unidades de desvio padrão |
| **Correlação de Pearson (r)** | Medida da força e direção da relação linear entre duas variáveis (-1 a +1) |
| **DEFF** | Design Effect — fator que ajusta os intervalos de confiança para desenhos amostrais complexos |
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
| **Teste t de Welch** | Teste que compara médias de dois grupos, sem assumir variâncias iguais |
| **TIC** | Tecnologias da Informação e Comunicação |
| **Variância** | Medida de dispersão — a média dos quadrados dos desvios em relação à média |
