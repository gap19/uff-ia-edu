"""Pré-computação de tabelas de agregação para o dashboard.

Materializa agregações sobre os Parquet do SAEB e TIC em tabelas
DuckDB para respostas sub-100ms no frontend.
"""

import duckdb
from pathlib import Path

from backend.config import (
    DUCKDB_PATH,
    SAEB_PARQUET_DIR,
    TIC_PARQUET_DIR,
    ID_UF_RJ,
    ID_REGIAO_SUDESTE,
)


def _parquet(name: str) -> str:
    """Retorna o caminho do parquet SAEB como string para SQL."""
    return str(SAEB_PARQUET_DIR / f"{name}.parquet")


def _tic_parquet() -> str:
    return str(TIC_PARQUET_DIR / "tic_educacao_2023.parquet")


def precompute_all() -> list[str]:
    """Executa todas as pré-computações e retorna lista de tabelas criadas."""
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    tables_created = []

    try:
        tables_created += _precompute_proficiency_by_uf(con)
        tables_created += _precompute_proficiency_by_inse(con)
        tables_created += _precompute_proficiency_by_location(con)
        tables_created += _precompute_proficiency_levels_rj(con)
        tables_created += _precompute_proficiency_levels_nacional(con)
        tables_created += _precompute_questionnaire_aluno_rj(con)
        tables_created += _precompute_questionnaire_professor_rj(con)
        tables_created += _precompute_questionnaire_diretor_rj(con)
        tables_created += _precompute_escola_formacao_rj(con)
        tables_created += _precompute_escola_inse_rj(con)
        tables_created += _precompute_tic_indicadores(con)
        tables_created += _precompute_kpi_rj(con)
        tables_created += _precompute_cross_aluno_tech_rj(con)
        tables_created += _precompute_cross_diretor_tech_rj(con)
        tables_created += _precompute_cross_professor_tech_rj(con)
        tables_created += _precompute_cross_digital_index_rj(con)
    finally:
        con.close()

    print(f"\nPré-computação concluída: {len(tables_created)} tabelas criadas.")
    return tables_created


# ---------------------------------------------------------------------------
# Proficiência por UF, série, disciplina, rede
# ---------------------------------------------------------------------------

def _precompute_proficiency_by_uf(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Médias ponderadas de proficiência por UF, série, disciplina e rede."""
    table = "prof_by_uf_serie_disc"
    queries = []

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF", "TS_ALUNO_34EM"]:
        pq = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        for disc, prof_col, peso_col in [
            ("LP", "PROFICIENCIA_LP_SAEB", "PESO_ALUNO_LP"),
            ("MT", "PROFICIENCIA_MT_SAEB", "PESO_ALUNO_MT"),
        ]:
            queries.append(f"""
                SELECT
                    ID_UF,
                    '{serie}' AS serie,
                    '{disc}' AS disciplina,
                    IN_PUBLICA AS rede,
                    SUM({prof_col} * {peso_col}) / NULLIF(SUM({peso_col}), 0) AS media_proficiencia,
                    SUM({peso_col}) AS soma_pesos,
                    COUNT(*) AS n_alunos
                FROM read_parquet('{pq}')
                WHERE IN_PROFICIENCIA_{disc} = 1
                  AND {peso_col} IS NOT NULL
                  AND {prof_col} IS NOT NULL
                GROUP BY ID_UF, IN_PUBLICA
            """)

        # CH e CN apenas para 5EF e 9EF
        if aluno_file in ("TS_ALUNO_5EF", "TS_ALUNO_9EF"):
            for disc, prof_col, peso_col in [
                ("CH", "PROFICIENCIA_CH_SAEB", "PESO_ALUNO_CH"),
                ("CN", "PROFICIENCIA_CN_SAEB", "PESO_ALUNO_CN"),
            ]:
                queries.append(f"""
                    SELECT
                        ID_UF,
                        '{serie}' AS serie,
                        '{disc}' AS disciplina,
                        IN_PUBLICA AS rede,
                        SUM({prof_col} * {peso_col}) / NULLIF(SUM({peso_col}), 0) AS media_proficiencia,
                        SUM({peso_col}) AS soma_pesos,
                        COUNT(*) AS n_alunos
                    FROM read_parquet('{pq}')
                    WHERE IN_PROFICIENCIA_{disc} = 1
                      AND {peso_col} IS NOT NULL
                      AND {prof_col} IS NOT NULL
                    GROUP BY ID_UF, IN_PUBLICA
                """)

    union_sql = "\nUNION ALL\n".join(queries)
    con.execute(f"CREATE OR REPLACE TABLE {table} AS ({union_sql})")
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Proficiência por INSE
# ---------------------------------------------------------------------------

def _precompute_proficiency_by_inse(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Média de proficiência por nível INSE para RJ."""
    table = "prof_by_inse"
    queries = []

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF", "TS_ALUNO_34EM"]:
        pq = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        for disc, prof_col, peso_col in [
            ("LP", "PROFICIENCIA_LP_SAEB", "PESO_ALUNO_LP"),
            ("MT", "PROFICIENCIA_MT_SAEB", "PESO_ALUNO_MT"),
        ]:
            queries.append(f"""
                SELECT
                    NU_TIPO_NIVEL_INSE AS nivel_inse,
                    '{serie}' AS serie,
                    '{disc}' AS disciplina,
                    SUM({prof_col} * {peso_col}) / NULLIF(SUM({peso_col}), 0) AS media_proficiencia,
                    SUM({peso_col}) AS soma_pesos,
                    COUNT(*) AS n_alunos
                FROM read_parquet('{pq}')
                WHERE ID_UF = {ID_UF_RJ}
                  AND IN_PROFICIENCIA_{disc} = 1
                  AND IN_INSE = 1
                  AND NU_TIPO_NIVEL_INSE IS NOT NULL
                  AND {peso_col} IS NOT NULL
                GROUP BY NU_TIPO_NIVEL_INSE
            """)

    union_sql = "\nUNION ALL\n".join(queries)
    con.execute(f"CREATE OR REPLACE TABLE {table} AS ({union_sql})")
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Proficiência por localização (urbana/rural)
# ---------------------------------------------------------------------------

def _precompute_proficiency_by_location(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Média de proficiência por localização (urbana/rural) para RJ."""
    table = "prof_by_location_rj"
    queries = []

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF", "TS_ALUNO_34EM"]:
        pq = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        for disc, prof_col, peso_col in [
            ("LP", "PROFICIENCIA_LP_SAEB", "PESO_ALUNO_LP"),
            ("MT", "PROFICIENCIA_MT_SAEB", "PESO_ALUNO_MT"),
        ]:
            queries.append(f"""
                SELECT
                    ID_LOCALIZACAO AS localizacao,
                    '{serie}' AS serie,
                    '{disc}' AS disciplina,
                    SUM({prof_col} * {peso_col}) / NULLIF(SUM({peso_col}), 0) AS media_proficiencia,
                    SUM({peso_col}) AS soma_pesos,
                    COUNT(*) AS n_alunos
                FROM read_parquet('{pq}')
                WHERE ID_UF = {ID_UF_RJ}
                  AND IN_PROFICIENCIA_{disc} = 1
                  AND ID_LOCALIZACAO IS NOT NULL
                  AND {peso_col} IS NOT NULL
                GROUP BY ID_LOCALIZACAO
            """)

    union_sql = "\nUNION ALL\n".join(queries)
    con.execute(f"CREATE OR REPLACE TABLE {table} AS ({union_sql})")
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Distribuição por nível de proficiência - RJ
# ---------------------------------------------------------------------------

def _nivel_avg_sql(col: str) -> str:
    """Gera AVG(TRY_CAST(col AS DOUBLE)) AS col_lower."""
    return f"AVG(TRY_CAST({col} AS DOUBLE)) AS {col.lower()}"


def _precompute_proficiency_levels_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Percentual de alunos por nível de proficiência no RJ."""
    table = "prof_niveis_rj"
    pq_escola = _parquet("TS_ESCOLA")

    # Colunas NIVEL_* são VARCHAR no CSV - precisa TRY_CAST para DOUBLE
    # Intervalos reais: LP5: 0-9, MT5: 0-10, LP9: 0-8, MT9: 0-9
    nivel_max = {"LP5": 9, "MT5": 10, "LP9": 8, "MT9": 9}
    nivel_cols = []
    for disc_serie, max_n in nivel_max.items():
        for n in range(0, max_n + 1):
            nivel_cols.append(f"NIVEL_{n}_{disc_serie}")

    avgs = ", ".join(_nivel_avg_sql(c) for c in nivel_cols)

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT
            ID_UF,
            IN_PUBLICA AS rede,
            {avgs},
            COUNT(*) AS n_escolas
        FROM read_parquet('{pq_escola}')
        WHERE ID_UF = {ID_UF_RJ}
        GROUP BY ID_UF, IN_PUBLICA
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Distribuição por nível - Nacional
# ---------------------------------------------------------------------------

def _precompute_proficiency_levels_nacional(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Percentual de alunos por nível de proficiência - nacional."""
    table = "prof_niveis_nacional"
    pq_escola = _parquet("TS_ESCOLA")

    nivel_max = {"LP5": 9, "MT5": 10, "LP9": 8, "MT9": 9}
    nivel_cols = []
    for disc_serie, max_n in nivel_max.items():
        for n in range(0, max_n + 1):
            nivel_cols.append(f"NIVEL_{n}_{disc_serie}")

    avgs = ", ".join(_nivel_avg_sql(c) for c in nivel_cols)

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT
            {avgs},
            COUNT(*) AS n_escolas
        FROM read_parquet('{pq_escola}')
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Questionários dos alunos - RJ
# ---------------------------------------------------------------------------

def _precompute_questionnaire_aluno_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Distribuição de respostas dos questionários de alunos no RJ."""
    table = "quest_aluno_rj"
    queries = []

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF"]:
        pq = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        # Pegar colunas TX_RESP_Q* dinamicamente via DuckDB
        queries.append(f"""
            WITH cols AS (
                SELECT column_name
                FROM (SELECT * FROM read_parquet('{pq}') LIMIT 0)
                UNPIVOT (val FOR column_name IN (*))
                WHERE column_name LIKE 'TX_RESP_Q%'
            )
            SELECT
                '{serie}' AS serie,
                col_name AS questao,
                val AS resposta,
                COUNT(*) AS contagem
            FROM read_parquet('{pq}')
            UNPIVOT (val FOR col_name IN (
                SELECT column_name FROM (
                    SELECT column_name
                    FROM parquet_schema('{pq}')
                    WHERE name LIKE 'TX_RESP_Q%'
                )
            ))
            WHERE ID_UF = {ID_UF_RJ}
              AND val IS NOT NULL
              AND val != ''
            GROUP BY col_name, val
        """)

    # UNPIVOT com lista dinâmica é complexo em DuckDB.
    # Abordagem alternativa: query direta para cada arquivo
    con.execute(f"""
        CREATE OR REPLACE TABLE {table} (
            serie VARCHAR,
            questao VARCHAR,
            resposta VARCHAR,
            contagem BIGINT
        )
    """)

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF"]:
        pq = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        # Obter nomes das colunas TX_RESP
        schema = con.execute(f"SELECT name FROM parquet_schema('{pq}') WHERE name LIKE 'TX_RESP_Q%'").fetchall()
        resp_cols = [row[0] for row in schema]

        if not resp_cols:
            continue

        unpivot_cols = ", ".join(resp_cols)
        con.execute(f"""
            INSERT INTO {table}
            SELECT
                '{serie}' AS serie,
                col_name AS questao,
                val AS resposta,
                COUNT(*) AS contagem
            FROM (
                SELECT *
                FROM read_parquet('{pq}')
                WHERE ID_UF = {ID_UF_RJ}
            )
            UNPIVOT (val FOR col_name IN ({unpivot_cols}))
            WHERE val IS NOT NULL AND val != '' AND val != '.'
            GROUP BY col_name, val
        """)

    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Questionários dos professores - RJ
# ---------------------------------------------------------------------------

def _precompute_questionnaire_professor_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Distribuição de respostas dos questionários de professores no RJ."""
    table = "quest_professor_rj"
    pq = _parquet("TS_PROFESSOR")

    # Filtrar apenas colunas TX_Q* do tipo VARCHAR para evitar erro de UNPIVOT
    schema = con.execute(f"""
        SELECT name FROM parquet_schema('{pq}')
        WHERE name LIKE 'TX_Q%' AND type = 'BYTE_ARRAY'
    """).fetchall()
    resp_cols = [row[0] for row in schema]

    if not resp_cols:
        con.execute(f"CREATE OR REPLACE TABLE {table} (questao VARCHAR, resposta VARCHAR, contagem BIGINT)")
        print(f"  [{table}] 0 linhas (sem colunas TX_Q*)")
        return [table]

    unpivot_cols = ", ".join(resp_cols)
    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT
            col_name AS questao,
            val AS resposta,
            COUNT(*) AS contagem
        FROM (
            SELECT {unpivot_cols}, ID_UF FROM read_parquet('{pq}')
            WHERE ID_UF = {ID_UF_RJ}
        )
        UNPIVOT (val FOR col_name IN ({unpivot_cols}))
        WHERE val IS NOT NULL AND val != '' AND val != '.'
        GROUP BY col_name, val
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Questionários dos diretores - RJ
# ---------------------------------------------------------------------------

def _precompute_questionnaire_diretor_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Distribuição de respostas dos questionários de diretores no RJ."""
    table = "quest_diretor_rj"
    pq = _parquet("TS_DIRETOR")

    schema = con.execute(f"""
        SELECT name FROM parquet_schema('{pq}')
        WHERE name LIKE 'TX_Q%' AND type = 'BYTE_ARRAY'
    """).fetchall()
    resp_cols = [row[0] for row in schema]

    if not resp_cols:
        con.execute(f"CREATE OR REPLACE TABLE {table} (questao VARCHAR, resposta VARCHAR, contagem BIGINT)")
        print(f"  [{table}] 0 linhas (sem colunas TX_Q*)")
        return [table]

    unpivot_cols = ", ".join(resp_cols)
    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT
            col_name AS questao,
            val AS resposta,
            COUNT(*) AS contagem
        FROM (
            SELECT {unpivot_cols}, ID_UF FROM read_parquet('{pq}')
            WHERE ID_UF = {ID_UF_RJ}
        )
        UNPIVOT (val FOR col_name IN ({unpivot_cols}))
        WHERE val IS NOT NULL AND val != '' AND val != '.'
        GROUP BY col_name, val
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Formação docente vs proficiência - RJ
# ---------------------------------------------------------------------------

def _precompute_escola_formacao_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Relação entre formação docente e proficiência média por escola no RJ."""
    table = "escola_formacao_rj"
    pq = _parquet("TS_ESCOLA")

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT
            TRY_CAST(PC_FORMACAO_DOCENTE_INICIAL AS DOUBLE) AS pc_formacao_docente_inicial,
            TRY_CAST(PC_FORMACAO_DOCENTE_FINAL AS DOUBLE) AS pc_formacao_docente_final,
            TRY_CAST(PC_FORMACAO_DOCENTE_MEDIO AS DOUBLE) AS pc_formacao_docente_medio,
            IN_PUBLICA AS rede,
            COUNT(*) AS n_escolas,
            AVG(TRY_CAST(MEDIA_5EF_LP AS DOUBLE)) AS media_5ef_lp,
            AVG(TRY_CAST(MEDIA_5EF_MT AS DOUBLE)) AS media_5ef_mt,
            AVG(TRY_CAST(MEDIA_9EF_LP AS DOUBLE)) AS media_9ef_lp,
            AVG(TRY_CAST(MEDIA_9EF_MT AS DOUBLE)) AS media_9ef_mt
        FROM read_parquet('{pq}')
        WHERE ID_UF = {ID_UF_RJ}
        GROUP BY
            TRY_CAST(PC_FORMACAO_DOCENTE_INICIAL AS DOUBLE),
            TRY_CAST(PC_FORMACAO_DOCENTE_FINAL AS DOUBLE),
            TRY_CAST(PC_FORMACAO_DOCENTE_MEDIO AS DOUBLE),
            IN_PUBLICA
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# INSE por escola - RJ
# ---------------------------------------------------------------------------

def _precompute_escola_inse_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """INSE e proficiências médias por escola no RJ."""
    table = "escola_inse_rj"
    pq = _parquet("TS_ESCOLA")

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT
            NIVEL_SOCIO_ECONOMICO,
            IN_PUBLICA AS rede,
            COUNT(*) AS n_escolas,
            AVG(TRY_CAST(MEDIA_5EF_LP AS DOUBLE)) AS media_5ef_lp,
            AVG(TRY_CAST(MEDIA_5EF_MT AS DOUBLE)) AS media_5ef_mt,
            AVG(TRY_CAST(MEDIA_9EF_LP AS DOUBLE)) AS media_9ef_lp,
            AVG(TRY_CAST(MEDIA_9EF_MT AS DOUBLE)) AS media_9ef_mt
        FROM read_parquet('{pq}')
        WHERE ID_UF = {ID_UF_RJ}
          AND NIVEL_SOCIO_ECONOMICO IS NOT NULL
          AND NIVEL_SOCIO_ECONOMICO != ''
        GROUP BY NIVEL_SOCIO_ECONOMICO, IN_PUBLICA
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# TIC Indicadores
# ---------------------------------------------------------------------------

def _precompute_tic_indicadores(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Carrega indicadores TIC já normalizados do Parquet."""
    table = "tic_indicadores"
    tic_pq = _tic_parquet()

    if not Path(tic_pq).exists():
        print(f"  [{table}] SKIP (parquet TIC não encontrado)")
        return []

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT * FROM read_parquet('{tic_pq}')
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# KPIs para visão geral - RJ
# ---------------------------------------------------------------------------

def _precompute_kpi_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """KPIs gerais do RJ para a página de visão geral."""
    table = "kpi_rj"
    queries = []

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF", "TS_ALUNO_34EM"]:
        pq = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        queries.append(f"""
            SELECT
                '{serie}' AS serie,
                COUNT(*) AS total_alunos,
                SUM(CASE WHEN IN_PRESENCA_LP = 1 THEN 1 ELSE 0 END) AS presentes_lp,
                SUM(PROFICIENCIA_LP_SAEB * PESO_ALUNO_LP) / NULLIF(SUM(
                    CASE WHEN IN_PROFICIENCIA_LP = 1 AND PESO_ALUNO_LP IS NOT NULL
                    THEN PESO_ALUNO_LP ELSE 0 END
                ), 0) AS media_lp,
                SUM(PROFICIENCIA_MT_SAEB * PESO_ALUNO_MT) / NULLIF(SUM(
                    CASE WHEN IN_PROFICIENCIA_MT = 1 AND PESO_ALUNO_MT IS NOT NULL
                    THEN PESO_ALUNO_MT ELSE 0 END
                ), 0) AS media_mt
            FROM read_parquet('{pq}')
            WHERE ID_UF = {ID_UF_RJ}
        """)

    union_sql = "\nUNION ALL\n".join(queries)
    con.execute(f"CREATE OR REPLACE TABLE {table} AS ({union_sql})")

    # Total de escolas no RJ
    pq_escola = _parquet("TS_ESCOLA")
    con.execute(f"""
        CREATE OR REPLACE TABLE kpi_escolas_rj AS
        SELECT
            COUNT(*) AS total_escolas,
            SUM(CASE WHEN IN_PUBLICA = 1 THEN 1 ELSE 0 END) AS escolas_publicas,
            SUM(CASE WHEN IN_PUBLICA = 0 THEN 1 ELSE 0 END) AS escolas_privadas
        FROM read_parquet('{pq_escola}')
        WHERE ID_UF = {ID_UF_RJ}
    """)

    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    print(f"  [kpi_escolas_rj] 1 linha")
    return [table, "kpi_escolas_rj"]


# ---------------------------------------------------------------------------
# Cruzamento: acesso digital do aluno vs proficiência - RJ
# ---------------------------------------------------------------------------

def _precompute_cross_aluno_tech_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Proficiência por resposta tecnológica do aluno (com/sem INSE)."""
    table = "cross_aluno_tech_rj"
    con.execute(f"""
        CREATE OR REPLACE TABLE {table} (
            serie VARCHAR, disciplina VARCHAR, tech_variable VARCHAR,
            tech_response VARCHAR, nivel_inse INTEGER,
            media_proficiencia DOUBLE, soma_pesos DOUBLE, n_alunos BIGINT
        )
    """)

    tech_vars = ["TX_RESP_Q12b", "TX_RESP_Q12g", "TX_RESP_Q13a", "TX_RESP_Q13b"]

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF", "TS_ALUNO_34EM"]:
        pq = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        for disc, prof_col, peso_col in [
            ("LP", "PROFICIENCIA_LP_SAEB", "PESO_ALUNO_LP"),
            ("MT", "PROFICIENCIA_MT_SAEB", "PESO_ALUNO_MT"),
        ]:
            for tv in tech_vars:
                # Overall (nivel_inse = NULL)
                con.execute(f"""
                    INSERT INTO {table}
                    SELECT
                        '{serie}', '{disc}', '{tv}',
                        {tv}, NULL,
                        SUM({prof_col} * {peso_col}) / NULLIF(SUM({peso_col}), 0),
                        SUM({peso_col}), COUNT(*)
                    FROM read_parquet('{pq}')
                    WHERE ID_UF = {ID_UF_RJ}
                      AND IN_PROFICIENCIA_{disc} = 1
                      AND {peso_col} IS NOT NULL AND {prof_col} IS NOT NULL
                      AND {tv} IS NOT NULL AND {tv} NOT IN ('*', '.', '')
                    GROUP BY {tv}
                """)
                # Stratified by INSE
                con.execute(f"""
                    INSERT INTO {table}
                    SELECT
                        '{serie}', '{disc}', '{tv}',
                        {tv}, NU_TIPO_NIVEL_INSE,
                        SUM({prof_col} * {peso_col}) / NULLIF(SUM({peso_col}), 0),
                        SUM({peso_col}), COUNT(*)
                    FROM read_parquet('{pq}')
                    WHERE ID_UF = {ID_UF_RJ}
                      AND IN_PROFICIENCIA_{disc} = 1
                      AND {peso_col} IS NOT NULL AND {prof_col} IS NOT NULL
                      AND {tv} IS NOT NULL AND {tv} NOT IN ('*', '.', '')
                      AND NU_TIPO_NIVEL_INSE IS NOT NULL
                    GROUP BY {tv}, NU_TIPO_NIVEL_INSE
                """)

    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Cruzamento: infraestrutura tech do diretor vs proficiência escolar - RJ
# ---------------------------------------------------------------------------

def _precompute_cross_diretor_tech_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Proficiência média escolar por resposta tech do diretor."""
    table = "cross_diretor_tech_rj"
    pq_dir = _parquet("TS_DIRETOR")
    pq_esc = _parquet("TS_ESCOLA")

    tech_vars = ["TX_Q034", "TX_Q035", "TX_Q036", "TX_Q194", "TX_Q219"]
    media_cols = [
        ("5EF", "LP", "MEDIA_5EF_LP"), ("5EF", "MT", "MEDIA_5EF_MT"),
        ("9EF", "LP", "MEDIA_9EF_LP"), ("9EF", "MT", "MEDIA_9EF_MT"),
        ("EM", "LP", "MEDIA_EM_LP"), ("EM", "MT", "MEDIA_EM_MT"),
    ]

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} (
            tech_variable VARCHAR, tech_response VARCHAR,
            serie VARCHAR, disciplina VARCHAR, rede INTEGER,
            media_proficiencia DOUBLE, n_escolas BIGINT
        )
    """)

    for tv in tech_vars:
        for serie, disc, media_col in media_cols:
            con.execute(f"""
                INSERT INTO {table}
                SELECT
                    '{tv}', d.{tv},
                    '{serie}', '{disc}', e.IN_PUBLICA,
                    AVG(TRY_CAST(e.{media_col} AS DOUBLE)),
                    COUNT(*)
                FROM read_parquet('{pq_dir}') d
                INNER JOIN read_parquet('{pq_esc}') e ON d.ID_ESCOLA = e.ID_ESCOLA
                WHERE d.ID_UF = {ID_UF_RJ}
                  AND d.{tv} IS NOT NULL AND d.{tv} NOT IN ('*', '.', '')
                  AND d.IN_PREENCHIMENTO_QUESTIONARIO = 1
                  AND e.{media_col} IS NOT NULL
                GROUP BY d.{tv}, e.IN_PUBLICA
            """)

    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Cruzamento: formação tech professor vs proficiência do aluno - RJ
# ---------------------------------------------------------------------------

def _precompute_cross_professor_tech_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Proficiência ponderada por resposta tech do professor (via ID_TURMA)."""
    table = "cross_professor_tech_rj"
    pq_prof = _parquet("TS_PROFESSOR")

    tech_vars = ["TX_Q029", "TX_Q037"]

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} (
            tech_variable VARCHAR, tech_response VARCHAR,
            serie VARCHAR, disciplina VARCHAR,
            media_proficiencia DOUBLE, soma_pesos DOUBLE, n_alunos BIGINT
        )
    """)

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF", "TS_ALUNO_34EM"]:
        pq_aluno = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        for disc, prof_col, peso_col in [
            ("LP", "PROFICIENCIA_LP_SAEB", "PESO_ALUNO_LP"),
            ("MT", "PROFICIENCIA_MT_SAEB", "PESO_ALUNO_MT"),
        ]:
            for tv in tech_vars:
                con.execute(f"""
                    INSERT INTO {table}
                    SELECT
                        '{tv}', t.{tv},
                        '{serie}', '{disc}',
                        SUM(a.{prof_col} * a.{peso_col}) / NULLIF(SUM(a.{peso_col}), 0),
                        SUM(a.{peso_col}), COUNT(*)
                    FROM read_parquet('{pq_aluno}') a
                    INNER JOIN (
                        SELECT ID_TURMA, {tv}
                        FROM read_parquet('{pq_prof}')
                        WHERE ID_UF = {ID_UF_RJ}
                          AND {tv} IS NOT NULL AND {tv} NOT IN ('*', '.', '')
                          AND IN_PREENCHIMENTO_QUESTIONARIO = 1
                    ) t ON a.ID_TURMA = t.ID_TURMA
                    WHERE a.ID_UF = {ID_UF_RJ}
                      AND a.{prof_col} IS NOT NULL AND a.{peso_col} IS NOT NULL
                    GROUP BY t.{tv}
                """)

    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


# ---------------------------------------------------------------------------
# Cruzamento: índice digital composto vs proficiência - RJ
# ---------------------------------------------------------------------------

def _precompute_cross_digital_index_rj(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Índice digital composto (Q12b+Q12g+Q13a+Q13b) vs proficiência."""
    table = "cross_digital_index_rj"

    con.execute(f"""
        CREATE OR REPLACE TABLE {table} (
            serie VARCHAR, disciplina VARCHAR,
            digital_index INTEGER, faixa_digital VARCHAR,
            nivel_inse INTEGER,
            media_proficiencia DOUBLE, soma_pesos DOUBLE, n_alunos BIGINT
        )
    """)

    for aluno_file in ["TS_ALUNO_5EF", "TS_ALUNO_9EF", "TS_ALUNO_34EM"]:
        pq = _parquet(aluno_file)
        serie = aluno_file.replace("TS_ALUNO_", "")

        index_expr = """
            (CASE TX_RESP_Q12b WHEN 'A' THEN 0 WHEN 'B' THEN 1 WHEN 'C' THEN 2 WHEN 'D' THEN 3 ELSE NULL END)
          + (CASE TX_RESP_Q12g WHEN 'A' THEN 0 WHEN 'B' THEN 1 WHEN 'C' THEN 2 WHEN 'D' THEN 3 ELSE NULL END)
          + (CASE TX_RESP_Q13a WHEN 'A' THEN 0 WHEN 'B' THEN 1 ELSE NULL END)
          + (CASE TX_RESP_Q13b WHEN 'A' THEN 0 WHEN 'B' THEN 1 ELSE NULL END)
        """

        for disc, prof_col, peso_col in [
            ("LP", "PROFICIENCIA_LP_SAEB", "PESO_ALUNO_LP"),
            ("MT", "PROFICIENCIA_MT_SAEB", "PESO_ALUNO_MT"),
        ]:
            # Overall
            con.execute(f"""
                INSERT INTO {table}
                SELECT
                    '{serie}', '{disc}',
                    di, CASE WHEN di <= 2 THEN 'Baixo' WHEN di <= 5 THEN 'Medio' ELSE 'Alto' END,
                    NULL,
                    SUM({prof_col} * {peso_col}) / NULLIF(SUM({peso_col}), 0),
                    SUM({peso_col}), COUNT(*)
                FROM (
                    SELECT *, ({index_expr}) AS di
                    FROM read_parquet('{pq}')
                    WHERE ID_UF = {ID_UF_RJ}
                      AND IN_PROFICIENCIA_{disc} = 1
                      AND {peso_col} IS NOT NULL AND {prof_col} IS NOT NULL
                ) sub
                WHERE di IS NOT NULL
                GROUP BY di
            """)
            # By INSE
            con.execute(f"""
                INSERT INTO {table}
                SELECT
                    '{serie}', '{disc}',
                    di, CASE WHEN di <= 2 THEN 'Baixo' WHEN di <= 5 THEN 'Medio' ELSE 'Alto' END,
                    NU_TIPO_NIVEL_INSE,
                    SUM({prof_col} * {peso_col}) / NULLIF(SUM({peso_col}), 0),
                    SUM({peso_col}), COUNT(*)
                FROM (
                    SELECT *, ({index_expr}) AS di
                    FROM read_parquet('{pq}')
                    WHERE ID_UF = {ID_UF_RJ}
                      AND IN_PROFICIENCIA_{disc} = 1
                      AND {peso_col} IS NOT NULL AND {prof_col} IS NOT NULL
                      AND NU_TIPO_NIVEL_INSE IS NOT NULL
                ) sub
                WHERE di IS NOT NULL
                GROUP BY di, NU_TIPO_NIVEL_INSE
            """)

    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [{table}] {n} linhas")
    return [table]


if __name__ == "__main__":
    precompute_all()
