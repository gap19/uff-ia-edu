"""Rotas da API para dados SAEB 2023."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.api.app import get_db
from backend.config import ID_UF_RJ, ID_REGIAO_SUDESTE, UF_MAP, SERIES_MAP

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _query(sql: str, params: list | None = None) -> list[dict]:
    """Execute a DuckDB query and return rows as list of dicts."""
    db = get_db()
    rel = db.execute(sql, params or [])
    columns = [desc[0] for desc in rel.description]
    return [dict(zip(columns, row)) for row in rel.fetchall()]


# UFs that belong to the Sudeste region (codes starting with 3x)
_SUDESTE_UFS = [id_uf for id_uf in UF_MAP if id_uf // 10 == ID_REGIAO_SUDESTE]


# ---------------------------------------------------------------------------
# 1. GET /overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def overview():
    """KPIs gerais do RJ: total de alunos, escolas e proficiencia media por serie."""
    try:
        kpi_alunos = _query("SELECT * FROM kpi_rj ORDER BY serie")
        kpi_escolas = _query("SELECT * FROM kpi_escolas_rj")

        return {
            "alunos_por_serie": kpi_alunos,
            "escolas": kpi_escolas[0] if kpi_escolas else {},
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 2. GET /proficiency
# ---------------------------------------------------------------------------

@router.get("/proficiency")
async def proficiency(
    serie: Optional[str] = Query(None, description="Filtro de serie (ex: 5EF, 9EF)"),
    disciplina: Optional[str] = Query(None, description="Filtro de disciplina (LP, MT, etc.)"),
    rede: Optional[str] = Query(None, description="Filtro de rede (publica, privada, total)"),
):
    """Proficiencia por UF, serie e disciplina."""
    try:
        conditions = []
        params = []

        if serie:
            conditions.append("serie = ?")
            params.append(serie)
        if disciplina:
            conditions.append("disciplina = ?")
            params.append(disciplina)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""

        if rede:
            conditions_rede = list(conditions)
            conditions_rede.append("rede = ?")
            params_rede = list(params) + [rede]
            where_rede = " WHERE " + " AND ".join(conditions_rede)
            sql = f"SELECT * FROM prof_by_uf_serie_disc{where_rede} ORDER BY ID_UF, serie, disciplina"
            rows = _query(sql, params_rede)
        else:
            # Agregar por UF (média ponderada de todas as redes)
            sql = (
                f"SELECT ID_UF, serie, disciplina, "
                f"  SUM(media_proficiencia * soma_pesos) / SUM(soma_pesos) AS media_proficiencia, "
                f"  SUM(n_alunos) AS n_alunos "
                f"FROM prof_by_uf_serie_disc{where} "
                f"GROUP BY ID_UF, serie, disciplina "
                f"ORDER BY ID_UF, serie, disciplina"
            )
            rows = _query(sql, params)

        # Enrich with UF sigla
        for row in rows:
            row["uf_sigla"] = UF_MAP.get(row.get("ID_UF"), "??")

        return {"data": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 3. GET /proficiency/comparison
# ---------------------------------------------------------------------------

@router.get("/proficiency/comparison")
async def proficiency_comparison():
    """Comparacao RJ vs Sudeste vs Brasil por serie e disciplina."""
    try:
        # RJ
        rj = _query(
            "SELECT serie, disciplina, rede, media_proficiencia, n_alunos "
            "FROM prof_by_uf_serie_disc WHERE ID_UF = ? ORDER BY serie, disciplina",
            [ID_UF_RJ],
        )

        # Sudeste: media ponderada das UFs da regiao
        placeholders = ",".join(["?"] * len(_SUDESTE_UFS))
        sudeste = _query(
            f"SELECT serie, disciplina, rede, "
            f"  SUM(media_proficiencia * soma_pesos) / SUM(soma_pesos) AS media_proficiencia, "
            f"  SUM(n_alunos) AS n_alunos "
            f"FROM prof_by_uf_serie_disc "
            f"WHERE ID_UF IN ({placeholders}) "
            f"GROUP BY serie, disciplina, rede "
            f"ORDER BY serie, disciplina",
            _SUDESTE_UFS,
        )

        # Brasil: media ponderada de todas as UFs
        brasil = _query(
            "SELECT serie, disciplina, rede, "
            "  SUM(media_proficiencia * soma_pesos) / SUM(soma_pesos) AS media_proficiencia, "
            "  SUM(n_alunos) AS n_alunos "
            "FROM prof_by_uf_serie_disc "
            "GROUP BY serie, disciplina, rede "
            "ORDER BY serie, disciplina",
        )

        return {
            "rj": rj,
            "sudeste": sudeste,
            "brasil": brasil,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 4. GET /proficiency/levels
# ---------------------------------------------------------------------------

@router.get("/proficiency/levels")
async def proficiency_levels(
    scope: str = Query("rj", description="Escopo: 'rj' ou 'nacional'"),
):
    """Distribuicao de niveis de proficiencia."""
    try:
        if scope == "nacional":
            rows = _query("SELECT * FROM prof_niveis_nacional")
        else:
            rows = _query("SELECT * FROM prof_niveis_rj")

        return {"scope": scope, "data": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 5. GET /equity/gap
# ---------------------------------------------------------------------------

@router.get("/equity/gap")
async def equity_gap(
    serie: Optional[str] = Query(None, description="Filtro de serie"),
    disciplina: Optional[str] = Query(None, description="Filtro de disciplina"),
):
    """Gap publico vs privado no RJ."""
    try:
        conditions = ["ID_UF = ?"]
        params: list = [ID_UF_RJ]

        if serie:
            conditions.append("serie = ?")
            params.append(serie)
        if disciplina:
            conditions.append("disciplina = ?")
            params.append(disciplina)

        where = " AND ".join(conditions)
        sql = (
            f"SELECT serie, disciplina, rede, media_proficiencia, n_alunos "
            f"FROM prof_by_uf_serie_disc WHERE {where} "
            f"ORDER BY serie, disciplina, rede"
        )
        rows = _query(sql, params)

        # Pivot by rede to compute gaps
        # rede: 1 = pública, 0 = privada (IN_PUBLICA)
        grouped: dict[tuple, dict] = {}
        for row in rows:
            key = (row["serie"], row["disciplina"])
            rede_key = "publica" if row["rede"] == 1 else "privada"
            grouped.setdefault(key, {})[rede_key] = row["media_proficiencia"]

        gaps = []
        for (s, d), redes in grouped.items():
            pub = redes.get("publica")
            priv = redes.get("privada")
            gap_value = round(priv - pub, 2) if pub is not None and priv is not None else None
            gaps.append({
                "serie": s,
                "disciplina": d,
                "media_publica": pub,
                "media_privada": priv,
                "gap": gap_value,
            })

        return {"data": gaps}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 6. GET /equity/inse
# ---------------------------------------------------------------------------

@router.get("/equity/inse")
async def equity_inse():
    """INSE vs proficiencia."""
    try:
        rows = _query(
            "SELECT * FROM prof_by_inse ORDER BY nivel_inse, serie, disciplina"
        )
        return {"data": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 7. GET /equity/location
# ---------------------------------------------------------------------------

@router.get("/equity/location")
async def equity_location():
    """Proficiência por localização (urbana/rural) no RJ."""
    try:
        rows = _query(
            "SELECT * FROM prof_by_location_rj ORDER BY serie, disciplina, localizacao"
        )
        # Map ID_LOCALIZACAO: 1=Urbana, 2=Rural
        loc_map = {1: "Urbana", 2: "Rural"}
        for row in rows:
            row["localizacao_label"] = loc_map.get(row["localizacao"], str(row["localizacao"]))
        return {"data": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 8. GET /teachers/formation
# ---------------------------------------------------------------------------

@router.get("/teachers/formation")
async def teachers_formation():
    """Formacao docente vs desempenho dos alunos no RJ."""
    try:
        rows = _query("SELECT * FROM escola_formacao_rj ORDER BY rede")
        return {"data": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 8. GET /questionnaire/{dataset}
# ---------------------------------------------------------------------------

_QUESTIONNAIRE_TABLES = {
    "aluno_5ef": ("quest_aluno_rj", "5EF"),
    "aluno_9ef": ("quest_aluno_rj", "9EF"),
    "professor": ("quest_professor_rj", None),
    "diretor": ("quest_diretor_rj", None),
}


@router.get("/questionnaire/{dataset}")
async def questionnaire(
    dataset: str,
    questao: Optional[str] = Query(None, description="Filtro por codigo da questao"),
):
    """Distribuicao de respostas de questionarios contextuais."""
    if dataset not in _QUESTIONNAIRE_TABLES:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{dataset}' nao encontrado. "
                   f"Opcoes: {list(_QUESTIONNAIRE_TABLES.keys())}",
        )

    try:
        table, serie_filter = _QUESTIONNAIRE_TABLES[dataset]
        conditions = []
        params: list = []

        if serie_filter:
            conditions.append("serie = ?")
            params.append(serie_filter)
        if questao:
            conditions.append("questao = ?")
            params.append(questao)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM {table}{where} ORDER BY questao, resposta"

        rows = _query(sql, params)
        return {"dataset": dataset, "data": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 9. GET /proficiency/ranking
# ---------------------------------------------------------------------------

@router.get("/proficiency/ranking")
async def proficiency_ranking(
    serie: str = Query(..., description="Serie (ex: 5EF, 9EF)"),
    disciplina: str = Query(..., description="Disciplina (LP, MT, etc.)"),
    rede: Optional[str] = Query(None, description="Filtro de rede"),
):
    """Ranking de UFs por proficiencia para serie/disciplina especifica."""
    try:
        conditions = ["serie = ?", "disciplina = ?"]
        params: list = [serie, disciplina]

        if rede:
            conditions.append("rede = ?")
            params.append(rede)
            sql = (
                f"SELECT ID_UF, serie, disciplina, rede, media_proficiencia, n_alunos "
                f"FROM prof_by_uf_serie_disc WHERE {' AND '.join(conditions)} "
                f"ORDER BY media_proficiencia DESC"
            )
        else:
            # Sem filtro de rede: média ponderada de todas as redes por UF
            sql = (
                f"SELECT ID_UF, serie, disciplina, "
                f"  SUM(media_proficiencia * soma_pesos) / SUM(soma_pesos) AS media_proficiencia, "
                f"  SUM(n_alunos) AS n_alunos "
                f"FROM prof_by_uf_serie_disc WHERE {' AND '.join(conditions)} "
                f"GROUP BY ID_UF, serie, disciplina "
                f"ORDER BY media_proficiencia DESC"
            )

        rows = _query(sql, params)

        for i, row in enumerate(rows, 1):
            row["uf_sigla"] = UF_MAP.get(row.get("ID_UF"), "??")
            row["ranking"] = i

        # Find RJ position
        rj_rank = next((r["ranking"] for r in rows if r.get("ID_UF") == ID_UF_RJ), None)

        return {
            "serie": serie,
            "disciplina": disciplina,
            "rj_ranking": rj_rank,
            "total_ufs": len(rows),
            "data": rows,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
