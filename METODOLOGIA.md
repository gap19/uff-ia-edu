# Metodologia Estatística

Documentação técnica das metodologias estatísticas empregadas no Dashboard de Pesquisa: IA na Educação (UFF).

---

## 1. Fontes de Dados

### 1.1 SAEB 2023 (INEP/MEC)

O Sistema de Avaliação da Educação Básica (SAEB) 2023 é uma avaliação em larga escala aplicada pelo INEP a alunos de escolas públicas e privadas do Brasil.

**Download dos dados brutos:** Os microdados estão disponíveis no portal de dados abertos do INEP em https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/saeb (arquivo "Microdados SAEB 2023", ~1.2 GB compactado). Após o download, extraia e coloque em `data/MICRODADOS_SAEB_2023/`.

**Microdados utilizados:**

| Arquivo | Registros | Descrição |
|---------|----------|-----------|
| TS_ALUNO_5EF | ~2,4M | Alunos do 5º ano do Ensino Fundamental |
| TS_ALUNO_9EF | ~2,5M | Alunos do 9º ano do Ensino Fundamental |
| TS_ALUNO_34EM | ~2,1M | Alunos do 3º/4º ano do Ensino Médio |
| TS_ESCOLA | ~70K | Escolas avaliadas |
| TS_PROFESSOR | ~411K | Professores respondentes |
| TS_DIRETOR | ~107K | Diretores respondentes |

**Filtro geográfico:** Rio de Janeiro (`ID_UF = 33`, código IBGE).

**Escala de proficiência:** Os escores do SAEB são expressos na escala SAEB (Teoria de Resposta ao Item), com média nacional em torno de 250 pontos para o 9º EF.

### 1.2 TIC Educação 2023 (CETIC.br/NIC.br)

A pesquisa TIC Educação investiga o acesso, uso e apropriação das TIC nas escolas brasileiras.

**Download dos dados:** As tabelas estão disponíveis no portal do CETIC.br em https://cetic.br/pt/pesquisa/educacao/indicadores/ (tabelas de escolas, formato Excel, edição 2023). Coloque os arquivos `.xlsx` em `data/tic_educacao_2023_escolas_tabelas_xlsx_v1.0/`.

**Dados disponíveis publicamente:** Tabelas agregadas por região (não por UF). Utilizamos os dados da região **Sudeste**.

**Formato:** 4 arquivos Excel (proporção, total, margem de erro, margem de erro total) com 138 planilhas cada, totalizando 69 indicadores.

---

## 2. Pesos Amostrais

### 2.1 Fundamento

O SAEB utiliza um desenho amostral complexo com estratificação e pesos de expansão. **Todas as estimativas** deste dashboard utilizam os pesos amostrais fornecidos pelo INEP para produzir estimativas representativas da população.

### 2.2 Colunas de Peso

| Disciplina | Coluna de Peso |
|-----------|---------------|
| Língua Portuguesa | `PESO_ALUNO_LP` |
| Matemática | `PESO_ALUNO_MT` |
| Ciências Humanas | `PESO_ALUNO_CH` |
| Ciências da Natureza | `PESO_ALUNO_CN` |
| Indicador Socioeconômico | `PESO_ALUNO_INSE` |

### 2.3 Variável de Estratificação

A variável `ESTRATO` é utilizada para estimação de variância com desenho amostral complexo, permitindo calcular o efeito de desenho (design effect) nos intervalos de confiança.

---

## 3. Funções Estatísticas

Todas as funções estão implementadas em `backend/analysis/stats_utils.py`.

### 3.1 Média Ponderada

$$\bar{x}_w = \frac{\sum_{i=1}^{n} w_i x_i}{\sum_{i=1}^{n} w_i}$$

Onde $w_i$ é o peso amostral e $x_i$ é o valor observado.

### 3.2 Variância Ponderada (com correção de Bessel)

$$s_w^2 = \frac{\sum w_i}{\left(\sum w_i\right)^2 - \sum w_i^2} \sum_{i=1}^{n} w_i (x_i - \bar{x}_w)^2$$

### 3.3 Intervalo de Confiança

O intervalo de confiança para a média ponderada é calculado considerando o efeito de desenho:

$$IC_{1-\alpha} = \bar{x}_w \pm z_{\alpha/2} \cdot \sqrt{DEFF \cdot \frac{s_w^2}{n}}$$

Onde $DEFF$ (design effect) é estimado a partir da variação entre estratos.

### 3.4 Teste t Ponderado (Welch)

Para comparação de duas médias ponderadas (ex: pública vs. privada):

$$t = \frac{\bar{x}_{w,1} - \bar{x}_{w,2}}{\sqrt{\frac{s_{w,1}^2}{n_1^{eff}} + \frac{s_{w,2}^2}{n_2^{eff}}}}$$

Onde $n^{eff} = \frac{(\sum w_i)^2}{\sum w_i^2}$ é o tamanho efetivo da amostra.

Graus de liberdade calculados via aproximação de Welch-Satterthwaite.

### 3.5 d de Cohen Ponderado

Tamanho de efeito padronizado para lacunas de desempenho:

$$d = \frac{\bar{x}_{w,1} - \bar{x}_{w,2}}{s_{pooled}}$$

Onde $s_{pooled} = \sqrt{\frac{s_{w,1}^2 + s_{w,2}^2}{2}}$ é o desvio-padrão ponderado combinado.

**Interpretação (Cohen, 1988):**
| d | Tamanho do Efeito |
|---|---|
| < 0.2 | Negligível |
| 0.2 - 0.5 | Pequeno |
| 0.5 - 0.8 | Médio |
| > 0.8 | Grande |

### 3.6 ANOVA Ponderado (One-way)

Para comparação de múltiplos grupos (ex: proficiência por número de computadores em casa):

$$F = \frac{SS_{between} / (k - 1)}{SS_{within} / (N_{eff} - k)}$$

Onde as somas de quadrados são calculadas com pesos amostrais.

### 3.7 Teste Qui-Quadrado

Para testar independência entre variáveis categóricas nos questionários:

$$\chi^2 = \sum_{i,j} \frac{(O_{ij} - E_{ij})^2}{E_{ij}}$$

### 3.8 Correlação de Pearson Ponderada

$$r_w = \frac{\sum w_i (x_i - \bar{x}_w)(y_i - \bar{y}_w)}{\sqrt{\sum w_i (x_i - \bar{x}_w)^2 \cdot \sum w_i (y_i - \bar{y}_w)^2}}$$

Utilizada para a correlação INSE x proficiência e para o índice digital composto.

---

## 4. Análises de Cruzamento Tecnologia x Desempenho

### 4.1 Variáveis de Interesse

**Nível Aluno (SAEB):**
- `TX_RESP_Q12b` — Computadores em casa (A=Nenhum, B=1, C=2, D=3+)
- `TX_RESP_Q12g` — Celulares com internet (A=Nenhum, B=1, C=2, D=3+)
- `TX_RESP_Q13a` — TV por internet/streaming (A=Não, B=Sim)
- `TX_RESP_Q13b` — Rede Wi-Fi em casa (A=Não, B=Sim)

**Nível Escola (Diretor):**
- `TX_Q034` — Computadores na escola (A-E, escala de adequação)
- `TX_Q035` — Softwares educacionais (A-E)
- `TX_Q036` — Internet banda larga (A-E)
- `TX_Q194` — Projetos de ciência e tecnologia (A=Sim, B=Não)
- `TX_Q219` — Novas tecnologias educacionais (A=Sim, B=Não)

**Nível Professor:**
- `TX_Q029` — Contribuição da formação em tecnologia
- `TX_Q037` — Uso de TICs na prática pedagógica

### 4.2 Índice Digital Composto

Soma das variáveis de acesso digital do aluno:

$$I_{digital} = Q12b_{(0-3)} + Q12g_{(0-3)} + Q13a_{(0-1)} + Q13b_{(0-1)} \in [0, 8]$$

**Faixas:**
| Faixa | Pontuação | Interpretação |
|-------|-----------|---------------|
| Baixo | 0-2 | Acesso digital limitado |
| Médio | 3-5 | Acesso digital moderado |
| Alto | 6-8 | Acesso digital amplo |

### 4.3 Controle por INSE

Todas as análises de cruzamento são executadas duas vezes:

1. **Bruta (raw):** Sem controle — estima a associação total entre tecnologia e proficiência.
2. **Estratificada por INSE:** Análise repetida dentro de cada nível INSE (1-8) — permite verificar se o efeito persiste após controlar pelo nível socioeconômico.

**Interpretação:**
- Se o gap se mantém dentro dos estratos INSE → efeito independente da tecnologia.
- Se o gap desaparece → tecnologia é proxy de renda/nível socioeconômico.
- Se o gap reduz parcialmente → efeito misto (confundimento parcial).

### 4.4 Correção para Comparações Múltiplas

Com ~12 variáveis testadas simultaneamente, aplicamos correção de Bonferroni:

$$\alpha_{ajustado} = \frac{0.05}{12} \approx 0.004$$

Resultados com $p < 0.05$ mas $p > 0.004$ são sinalizados como "significativo sem correção" (asterisco).

---

## 5. Limitações Metodológicas

1. **Correlação ≠ causalidade:** Os cruzamentos mostram associações, não efeitos causais. Fatores não observados podem confundir as relações.

2. **Confundimento socioeconômico:** O acesso a tecnologia correlaciona fortemente com renda. A estratificação por INSE mitiga, mas não elimina completamente esse confundimento.

3. **TIC regional vs. SAEB escolar:** Os dados TIC Educação são de nível regional (Sudeste), não podendo ser cruzados diretamente com escolas individuais do SAEB.

4. **Missing data:** Respostas em branco (`'.'` e `'*'`) são filtradas das análises. Isso pode introduzir viés de seleção se o padrão de não-resposta não for aleatório.

5. **Viés de seleção:** A participação no SAEB não é universal para todas as redes e séries, o que pode afetar a representatividade dos resultados.

6. **Temporalidade:** Os dados SAEB e TIC são de corte transversal (2023), impossibilitando análise de tendências temporais.

---

## 6. Valores de Referência Validados

Os seguintes resultados foram validados manualmente contra os dados brutos e/ou publicações oficiais do INEP:

| Análise | Resultado | Referência |
|---------|-----------|-----------|
| Média LP pública 5EF RJ | ~206 | Compatível com TS_UF publicado |
| Média LP privada 5EF RJ | ~240 | Compatível com TS_UF publicado |
| Gap WiFi (9EF LP RJ) | 19.3 pts | Validado via consulta direta aos microdados |
| N sem WiFi (9EF RJ) | ~9.5K | Confirmado |
| N com WiFi (9EF RJ) | ~102K | Confirmado |
| Computadores: gradiente (9EF LP) | 247→265→275→287 | 40 pts de spread |
| Índice digital: gradiente (9EF LP) | 237→252→274 | 37 pts de spread |
| Controle INSE: gap WiFi | Reduz de 19→4-14 pts | Confundimento SES parcial |
| Projetos tech (Q194 diretor) | Sem efeito (252.7 vs 252.8) | Resultado nulo validado |
| Uso TICs (Q037 professor) | Curvilíneo (261→265→267→264) | Uso moderado é ótimo |

---

## 7. Referências

- BRASIL. Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira (INEP). **Microdados do SAEB 2023.** Brasília: INEP, 2024.
- CETIC.BR. **TIC Educação 2023: Pesquisa sobre o uso das tecnologias de informação e comunicação nas escolas brasileiras.** São Paulo: Comitê Gestor da Internet no Brasil, 2024.
- Cohen, J. (1988). **Statistical Power Analysis for the Behavioral Sciences** (2nd ed.). Lawrence Erlbaum Associates.
- OECD (2023). **PISA 2022 Results (Volume I): The State of Learning and Equity in Education.** OECD Publishing.
- UNESCO (2023). **Global Education Monitoring Report 2023: Technology in education.** UNESCO Publishing.
- Kish, L. (1965). **Survey Sampling.** John Wiley & Sons.
