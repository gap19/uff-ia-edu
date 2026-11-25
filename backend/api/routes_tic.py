"""Rotas da API para dados da TIC Educacao 2023 (CETIC.br)."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.analysis.tic import TIC_GROUPS, get_tic_group
from backend.db import db_query

router = APIRouter()

TABLE = "tic_indicadores"


def _table_exists() -> bool:
    """Verifica se a tabela tic_indicadores existe no DuckDB."""
    try:
        tables = db_query("SHOW TABLES")
        return TABLE in [t["name"] for t in tables]
    except Exception:
        return False


def _no_table_response():
    """Resposta padrao quando a tabela ainda nao foi criada."""
    return {
        "data": [],
        "message": (
            "Tabela tic_indicadores ainda nao disponivel. "
            "Execute o ETL (scripts/init_db.py) com as planilhas da TIC Educacao 2023."
        ),
    }


def _group(key: str):
    if not _table_exists():
        return _no_table_response()
    return get_tic_group(key)


@router.get("/indicators")
def list_indicators():
    """Lista os indicadores disponiveis com titulo e universo."""
    if not _table_exists():
        return _no_table_response()
    data = db_query(f"""
        SELECT DISTINCT indicador, titulo, universo
        FROM {TABLE}
        ORDER BY indicador
    """)
    return {"count": len(data), "data": data}


@router.get("/indicator/{code}")
def get_indicator(
    code: str,
    tipo: str = Query(default="proporcao", description="proporcao, total, margem_erro ou margem_erro_total"),
    variavel_corte: Optional[str] = Query(
        default=None, description="Filtrar por variavel de corte (TOTAL, REGIÃO, ÁREA, ...)"
    ),
):
    """Retorna todas as linhas de um indicador (formato longo)."""
    if not _table_exists():
        return _no_table_response()

    code_norm = code.strip().upper()
    sql = f"""
        SELECT indicador, titulo, universo, tipo, variavel_corte, valor_corte,
               item, resposta, coluna, valor
        FROM {TABLE}
        WHERE indicador = ? AND tipo = ?
    """
    params: list = [code_norm, tipo]
    if variavel_corte is not None:
        sql += " AND variavel_corte = ?"
        params.append(variavel_corte)
    sql += " ORDER BY variavel_corte, valor_corte, coluna"

    data = db_query(sql, params)
    return {"indicator": code_norm, "tipo": tipo, "count": len(data), "data": data}


@router.get("/groups")
def list_groups():
    """Grupos temáticos e os indicadores curados de cada um."""
    return {
        key: {
            "label": cfg["label"],
            "indicators": [
                {k: v for k, v in spec.items()} for spec in cfg["indicators"]
            ],
        }
        for key, cfg in TIC_GROUPS.items()
    }


@router.get("/infrastructure")
def infrastructure():
    """Infraestrutura e conectividade (A1, A2, A4, A6–A8, B1, B1B)."""
    return _group("infrastructure")


@router.get("/ai")
def ai_indicators():
    """Dados, vigilância e IA (E3, E4A, E4B, E6, F6)."""
    return _group("ai")


@router.get("/privacy")
def privacy():
    """Privacidade e proteção de dados (H1, H3, H5, H6)."""
    return _group("privacy")


@router.get("/teacher-training")
def teacher_training():
    """Formação docente em tecnologias (J1, J2, J3)."""
    return _group("teacher-training")


@router.get("/digital-literacy")
def digital_literacy():
    """Uso seguro, responsável e crítico da internet (I1, I3)."""
    return _group("digital-literacy")


@router.get("/group/{key}")
def group(key: str):
    """Qualquer grupo temático pelo identificador (ver /groups)."""
    if key not in TIC_GROUPS:
        raise HTTPException(status_code=404, detail=f"Grupo '{key}' inexistente: {list(TIC_GROUPS)}")
    return _group(key)
