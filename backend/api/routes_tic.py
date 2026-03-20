"""Rotas da API para dados da TIC Educacao 2023."""

from typing import Optional

from fastapi import APIRouter, Query

from backend.api.app import get_db

router = APIRouter()

TABLE = "tic_indicadores"


def _table_exists() -> bool:
    """Verifica se a tabela tic_indicadores existe no DuckDB."""
    try:
        db = get_db()
        tables = db.execute("SHOW TABLES").fetchall()
        return TABLE in [t[0] for t in tables]
    except Exception:
        return False


def _no_table_response():
    """Resposta padrao quando a tabela ainda nao foi criada."""
    return {
        "data": [],
        "message": (
            "Tabela tic_indicadores ainda nao disponivel. "
            "O processamento dos dados TIC pode estar em andamento."
        ),
    }


def _query(sql: str, params: list | None = None) -> list[dict]:
    """Executa query e retorna lista de dicts."""
    db = get_db()
    result = db.execute(sql, params or []).fetchall()
    columns = [desc[0] for desc in db.description]
    return [dict(zip(columns, row)) for row in result]


def _get_indicator_group(codes: list[str], label: str):
    """Busca grupo de indicadores por lista de codigos."""
    if not _table_exists():
        return _no_table_response()

    placeholders = ", ".join(["?"] * len(codes))
    sql = f"""
        SELECT indicador, tipo, variavel_corte, valor_corte, regiao, valor
        FROM {TABLE}
        WHERE indicador IN ({placeholders})
        ORDER BY indicador, tipo, variavel_corte, valor_corte, regiao
    """
    data = _query(sql, codes)
    return {"group": label, "indicators": codes, "count": len(data), "data": data}


@router.get("/indicators")
async def list_indicators():
    """Lista todos os codigos de indicadores disponiveis e seus tipos."""
    if not _table_exists():
        return _no_table_response()

    sql = f"""
        SELECT DISTINCT indicador, tipo
        FROM {TABLE}
        ORDER BY indicador, tipo
    """
    data = _query(sql)
    return {"count": len(data), "data": data}


@router.get("/indicator/{code}")
async def get_indicator(
    code: str,
    tipo: str = Query(default="proporcao", description="Tipo do indicador"),
    variavel_corte: Optional[str] = Query(
        default=None, description="Filtrar por variavel de corte"
    ),
):
    """Retorna dados de um indicador especifico."""
    if not _table_exists():
        return _no_table_response()

    sql = f"""
        SELECT indicador, tipo, variavel_corte, valor_corte, regiao, valor
        FROM {TABLE}
        WHERE indicador = ? AND tipo = ?
    """
    params: list = [code, tipo]

    if variavel_corte is not None:
        sql += " AND variavel_corte = ?"
        params.append(variavel_corte)

    sql += " ORDER BY variavel_corte, valor_corte, regiao"

    data = _query(sql, params)
    return {"indicator": code, "tipo": tipo, "count": len(data), "data": data}


@router.get("/infrastructure")
async def infrastructure():
    """Indicadores agregados de infraestrutura (A1-A8)."""
    codes = [f"A{i}" for i in range(1, 9)]
    return _get_indicator_group(codes, "Infraestrutura")


@router.get("/ai")
async def ai_indicators():
    """Indicadores de IA e sistemas de dados (E4A, E4B, E5, E6, F6)."""
    codes = ["E4A", "E4B", "E5", "E6", "F6"]
    return _get_indicator_group(codes, "IA e Sistemas de Dados")


@router.get("/privacy")
async def privacy():
    """Indicadores de politica de privacidade (H1-H7)."""
    codes = [f"H{i}" for i in range(1, 8)]
    return _get_indicator_group(codes, "Politica de Privacidade")


@router.get("/teacher-training")
async def teacher_training():
    """Indicadores de formacao digital docente (J1-J4)."""
    codes = [f"J{i}" for i in range(1, 5)]
    return _get_indicator_group(codes, "Formacao Digital Docente")


@router.get("/digital-literacy")
async def digital_literacy():
    """Indicadores de letramento digital (I1-I3)."""
    codes = [f"I{i}" for i in range(1, 4)]
    return _get_indicator_group(codes, "Letramento Digital")
