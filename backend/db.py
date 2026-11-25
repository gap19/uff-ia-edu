"""Conexão DuckDB compartilhada (somente leitura) e helper de consulta.

Fica fora de ``backend.api.app`` para que rotas e o gerador de PDF possam
importá-la sem criar import circular (app -> rotas -> pdf_generator -> app).
"""

import threading

import duckdb

from backend.config import DUCKDB_PATH

_db: duckdb.DuckDBPyConnection | None = None
_db_lock = threading.Lock()


def get_db() -> duckdb.DuckDBPyConnection:
    """Retorna a conexão DuckDB compartilhada (aberta sob demanda)."""
    global _db
    with _db_lock:
        if _db is None:
            _db = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        return _db


def close_db() -> None:
    """Fecha a conexão compartilhada, se aberta."""
    global _db
    with _db_lock:
        if _db is not None:
            _db.close()
            _db = None


def _open_cursor() -> duckdb.DuckDBPyConnection:
    """Abre um cursor isolado sob o lock da conexão compartilhada."""
    global _db
    with _db_lock:
        if _db is None:
            _db = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        return _db.cursor()


def db_query(sql: str, params: list | None = None) -> list[dict]:
    """Executa uma consulta e retorna as linhas como lista de dicts.

    Usa um cursor próprio (conexão duplicada) por chamada: o objeto de
    conexão do DuckDB não é thread-safe, e as rotas síncronas do FastAPI
    rodam em um threadpool.
    """
    cur = _open_cursor()
    try:
        rel = cur.execute(sql, params or [])
        columns = [desc[0] for desc in rel.description]
        return [dict(zip(columns, row)) for row in rel.fetchall()]
    finally:
        cur.close()
