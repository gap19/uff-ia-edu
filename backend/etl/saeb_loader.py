"""Conversão de microdados SAEB 2023 (CSV) para Parquet via DuckDB.

Lê os CSVs com delimitador `;`, corrige tipos das colunas de
proficiência e peso amostral para DOUBLE, e exporta cada tabela
como Parquet (snappy).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.config import (
    DUCKDB_PATH,
    PROFICIENCY_COLS,
    SAEB_CSV_DIR,
    SAEB_CSV_FILES,
    SAEB_PARQUET_DIR,
    WEIGHT_COLS,
)

# Colunas que devem ser DOUBLE (proficiência + peso amostral)
_DOUBLE_COLUMNS: set[str] = {*PROFICIENCY_COLS.values(), *WEIGHT_COLS.values()}


def _ensure_dirs() -> None:
    """Cria diretórios de saída caso não existam."""
    SAEB_PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _convert_to_utf8(src: Path, dst: Path) -> None:
    """Converte arquivo de latin-1 para UTF-8 em streaming."""
    with open(src, "r", encoding="latin-1") as fin, \
         open(dst, "w", encoding="utf-8") as fout:
        for line in fin:
            fout.write(line)


def _cast_double_columns(con: duckdb.DuckDBPyConnection, rel: duckdb.DuckDBPyRelation) -> duckdb.DuckDBPyRelation:
    """Converte para DOUBLE as colunas de proficiência/peso presentes na relação."""
    existing_cols = {c.upper() for c in rel.columns}
    casts_needed = _DOUBLE_COLUMNS & existing_cols

    if not casts_needed:
        return rel

    projections: list[str] = []
    for col in rel.columns:
        if col.upper() in casts_needed:
            projections.append(f'CAST("{col}" AS DOUBLE) AS "{col}"')
        else:
            projections.append(f'"{col}"')

    return con.sql(f"SELECT {', '.join(projections)} FROM rel")


def _csv_path(name: str) -> Path:
    """Retorna o caminho completo do CSV para um dado nome de tabela."""
    return SAEB_CSV_DIR / f"{name}.csv"


def _parquet_path(name: str) -> Path:
    """Retorna o caminho de destino Parquet para um dado nome de tabela."""
    return SAEB_PARQUET_DIR / f"{name}.parquet"


def load_single_saeb(name: str) -> int:
    """Carrega um único CSV SAEB e exporta como Parquet.

    Parameters
    ----------
    name:
        Nome da tabela (ex.: ``TS_ALUNO_5EF``), sem extensão.

    Returns
    -------
    int
        Quantidade de linhas exportadas.

    Raises
    ------
    FileNotFoundError
        Se o CSV correspondente não existir.
    ValueError
        Se *name* não estiver na lista de arquivos esperados.
    """
    if name not in SAEB_CSV_FILES:
        raise ValueError(
            f"Tabela '{name}' não reconhecida. "
            f"Valores válidos: {SAEB_CSV_FILES}"
        )

    csv_file = _csv_path(name)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV não encontrado: {csv_file}")

    _ensure_dirs()

    parquet_file = _parquet_path(name)

    # CSVs do SAEB são latin-1; converter para UTF-8 temporariamente
    utf8_file = SAEB_PARQUET_DIR / f"{name}_utf8.csv"
    try:
        _convert_to_utf8(csv_file, utf8_file)

        con = duckdb.connect(str(DUCKDB_PATH))
        try:
            con.sql(f"""
                CREATE OR REPLACE TABLE "_tmp_{name}" AS
                SELECT * FROM read_csv(
                    '{utf8_file}',
                    delim = ';',
                    header = true,
                    null_padding = true
                )
            """)

            row_count = con.execute(
                f'SELECT COUNT(*) FROM "_tmp_{name}"'
            ).fetchone()[0]
            col_count = len(con.execute(
                f'SELECT * FROM "_tmp_{name}" LIMIT 0'
            ).description)

            print(f"[saeb_loader] {name}: {row_count:,} linhas, {col_count} colunas")

            con.execute(
                f"""COPY "_tmp_{name}" TO '{parquet_file}'
                    (FORMAT PARQUET, COMPRESSION SNAPPY)"""
            )

            con.execute(f'DROP TABLE IF EXISTS "{name}"')
            con.execute(f'ALTER TABLE "_tmp_{name}" RENAME TO "{name}"')

            print(f"[saeb_loader] {name} -> {parquet_file}")
        finally:
            con.close()
    finally:
        if utf8_file.exists():
            utf8_file.unlink()

    return row_count


def load_all_saeb() -> dict[str, int]:
    """Processa todos os CSVs SAEB e retorna contagem de linhas por tabela.

    Returns
    -------
    dict[str, int]
        Dicionário ``{nome_tabela: quantidade_linhas}``.
    """
    _ensure_dirs()

    results: dict[str, int] = {}

    for name in SAEB_CSV_FILES:
        csv_file = _csv_path(name)
        if not csv_file.exists():
            print(f"[saeb_loader] AVISO: {csv_file} não encontrado, pulando.")
            continue

        row_count = load_single_saeb(name)
        results[name] = row_count

    print(f"\n[saeb_loader] Concluído: {len(results)}/{len(SAEB_CSV_FILES)} tabelas processadas.")
    return results


if __name__ == "__main__":
    load_all_saeb()
