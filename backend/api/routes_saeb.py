"""Rotas da API para dados SAEB 2023."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.db import db_query
from backend.config import ID_UF_RJ, ID_REGIAO_SUDESTE, UF_MAP, PROCESSED_DIR, SAEB_PARQUET_DIR

# ---------------------------------------------------------------------------
# Questionnaire dictionary (question texts + response labels)
# ---------------------------------------------------------------------------

_QUEST_DICT: dict | None = None

def _get_quest_dict() -> dict:
    global _QUEST_DICT
    if _QUEST_DICT is None:
        dict_path = PROCESSED_DIR / "saeb_questionnaire_dict.json"
        if dict_path.exists():
            with open(dict_path, encoding="utf-8") as f:
                _QUEST_DICT = json.load(f)
        else:
            _QUEST_DICT = {}
    return _QUEST_DICT

# Map dataset names to dict sheet keys
_DATASET_TO_SHEET = {
    "aluno_5ef": "TS_ALUNO_5EF",
    "aluno_9ef": "TS_ALUNO_9EF",
    "aluno_34em": "TS_ALUNO_34EM",
    "professor": "TS_PROFESSOR",
    "diretor": "TS_DIRETOR",
}

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_query = db_query

# Ordem pedagógica das séries (ORDER BY serie em texto daria 34EM, 5EF, 9EF)
_SERIE_ORDER_SQL = "CASE serie WHEN '5EF' THEN 1 WHEN '9EF' THEN 2 ELSE 3 END"

# rede: IN_PUBLICA (1 = pública, 0 = privada)
_REDE_CODES = {"publica": 1, "pública": 1, "1": 1, "privada": 0, "0": 0}


def _parse_rede(rede: Optional[str]) -> Optional[int]:
    """Converte o filtro textual de rede para o código IN_PUBLICA.

    ``None``, ``""`` e ``"total"`` significam sem filtro (todas as redes).
    """
    if rede is None or rede.strip().lower() in ("", "total"):
        return None
    code = _REDE_CODES.get(rede.strip().lower())
    if code is None:
        raise HTTPException(
            status_code=400,
            detail=f"Rede '{rede}' inválida. Opções: publica, privada, total",
        )
    return code


# UFs that belong to the Sudeste region (codes starting with 3x)
_SUDESTE_UFS = [id_uf for id_uf in UF_MAP if id_uf // 10 == ID_REGIAO_SUDESTE]


# ---------------------------------------------------------------------------
# 1. GET /overview
# ---------------------------------------------------------------------------

@router.get("/overview")
def overview():
    """KPIs gerais do RJ: total de alunos, escolas e proficiencia media por serie."""
    try:
        kpi_alunos = _query(f"SELECT * FROM kpi_rj ORDER BY {_SERIE_ORDER_SQL}")
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
def proficiency(
    serie: Optional[str] = Query(None, description="Filtro de serie (ex: 5EF, 9EF)"),
    disciplina: Optional[str] = Query(None, description="Filtro de disciplina (LP, MT, etc.)"),
    rede: Optional[str] = Query(None, description="Filtro de rede (publica, privada, total)"),
):
    """Proficiencia por UF, serie e disciplina."""
    rede_code = _parse_rede(rede)
    try:
        conditions = []
        params = []

        if serie:
            conditions.append("serie = ?")
            params.append(serie.upper())
        if disciplina:
            conditions.append("disciplina = ?")
            params.append(disciplina.upper())

        where = " WHERE " + " AND ".join(conditions) if conditions else ""

        if rede_code is not None:
            conditions_rede = list(conditions)
            conditions_rede.append("rede = ?")
            params_rede = list(params) + [rede_code]
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
def proficiency_comparison():
    """Comparacao RJ vs Sudeste vs Brasil por serie e disciplina."""
    try:
        # RJ
        rj = _query(
            "SELECT serie, disciplina, rede, media_proficiencia, soma_pesos, n_alunos "
            "FROM prof_by_uf_serie_disc WHERE ID_UF = ? ORDER BY serie, disciplina, rede",
            [ID_UF_RJ],
        )

        # Sudeste: media ponderada das UFs da regiao
        placeholders = ",".join(["?"] * len(_SUDESTE_UFS))
        sudeste = _query(
            f"SELECT serie, disciplina, rede, "
            f"  SUM(media_proficiencia * soma_pesos) / SUM(soma_pesos) AS media_proficiencia, "
            f"  SUM(soma_pesos) AS soma_pesos, SUM(n_alunos) AS n_alunos "
            f"FROM prof_by_uf_serie_disc "
            f"WHERE ID_UF IN ({placeholders}) "
            f"GROUP BY serie, disciplina, rede "
            f"ORDER BY serie, disciplina, rede",
            _SUDESTE_UFS,
        )

        # Brasil: media ponderada de todas as UFs
        brasil = _query(
            "SELECT serie, disciplina, rede, "
            "  SUM(media_proficiencia * soma_pesos) / SUM(soma_pesos) AS media_proficiencia, "
            "  SUM(soma_pesos) AS soma_pesos, SUM(n_alunos) AS n_alunos "
            "FROM prof_by_uf_serie_disc "
            "GROUP BY serie, disciplina, rede "
            "ORDER BY serie, disciplina, rede",
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
def proficiency_levels(
    scope: str = Query("rj", description="Escopo: 'rj' ou 'nacional'"),
):
    """Distribuicao de niveis de proficiencia.

    Fonte: TS_ESCOLA, que contém apenas escolas públicas. Os valores são a
    média simples, entre as escolas, do percentual de alunos em cada nível.
    """
    try:
        if scope == "nacional":
            rows = _query("SELECT * FROM prof_niveis_nacional")
        else:
            rows = _query("SELECT * FROM prof_niveis_rj ORDER BY rede DESC")

        return {"scope": scope, "data": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 5. GET /equity/gap
# ---------------------------------------------------------------------------

@router.get("/equity/gap")
def equity_gap(
    serie: Optional[str] = Query(None, description="Filtro de serie"),
    disciplina: Optional[str] = Query(None, description="Filtro de disciplina"),
):
    """Gap publico vs privado no RJ."""
    try:
        conditions = ["ID_UF = ?"]
        params: list = [ID_UF_RJ]

        if serie:
            conditions.append("serie = ?")
            params.append(serie.upper())
        if disciplina:
            conditions.append("disciplina = ?")
            params.append(disciplina.upper())

        where = " AND ".join(conditions)
        sql = (
            f"SELECT serie, disciplina, rede, media_proficiencia, n_alunos "
            f"FROM prof_by_uf_serie_disc WHERE {where} "
            f"ORDER BY {_SERIE_ORDER_SQL}, disciplina, rede"
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
def equity_inse():
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
def equity_location():
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
def teachers_formation():
    """Formacao docente vs desempenho dos alunos no RJ — uma linha por escola.

    Lido diretamente de TS_ESCOLA (pequeno): a antiga tabela pré-computada
    ``escola_formacao_rj`` agrupava escolas com percentuais idênticos, o que
    distorcia a correlação calculada no frontend.
    """
    pq = str(SAEB_PARQUET_DIR / "TS_ESCOLA.parquet")
    try:
        rows = _query(f"""
            SELECT
                IN_PUBLICA AS rede,
                ROUND(TRY_CAST(PC_FORMACAO_DOCENTE_INICIAL AS DOUBLE), 2) AS pc_formacao_docente_inicial,
                ROUND(TRY_CAST(PC_FORMACAO_DOCENTE_FINAL AS DOUBLE), 2) AS pc_formacao_docente_final,
                ROUND(TRY_CAST(PC_FORMACAO_DOCENTE_MEDIO AS DOUBLE), 2) AS pc_formacao_docente_medio,
                ROUND(TRY_CAST(MEDIA_5EF_LP AS DOUBLE), 2) AS media_5ef_lp,
                ROUND(TRY_CAST(MEDIA_5EF_MT AS DOUBLE), 2) AS media_5ef_mt,
                ROUND(TRY_CAST(MEDIA_9EF_LP AS DOUBLE), 2) AS media_9ef_lp,
                ROUND(TRY_CAST(MEDIA_9EF_MT AS DOUBLE), 2) AS media_9ef_mt,
                ROUND(TRY_CAST(MEDIA_EM_LP AS DOUBLE), 2) AS media_em_lp,
                ROUND(TRY_CAST(MEDIA_EM_MT AS DOUBLE), 2) AS media_em_mt
            FROM read_parquet('{pq}')
            WHERE ID_UF = ?
            ORDER BY ID_ESCOLA
        """, [ID_UF_RJ])
        # Cada escola só tem as etapas que oferece: omitir campos nulos reduz
        # o JSON (importante no site estático) — ausente == null no frontend.
        rows = [{k: v for k, v in r.items() if v is not None} for r in rows]
        return {"data": rows, "unit": "escola"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 8. GET /questionnaire/{dataset}
# ---------------------------------------------------------------------------

_QUESTIONNAIRE_TABLES = {
    "aluno_5ef": ("quest_aluno_rj", "5EF"),
    "aluno_9ef": ("quest_aluno_rj", "9EF"),
    "aluno_34em": ("quest_aluno_rj", "34EM"),
    "professor": ("quest_professor_rj", None),
    "diretor": ("quest_diretor_rj", None),
}


@router.get("/questionnaire/{dataset}")
def questionnaire(
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

        # Enrich with dictionary labels
        qdict = _get_quest_dict()
        sheet = _DATASET_TO_SHEET.get(dataset, "")
        sheet_dict = qdict.get(sheet, {})

        question_text = None
        if questao and questao in sheet_dict:
            question_text = sheet_dict[questao].get("text")
            options = sheet_dict[questao].get("options", {})
            for row in rows:
                code = row.get("resposta", "")
                if code in options:
                    row["resposta_label"] = options[code]

        # Build question list with texts for dropdown
        question_list = None
        if not questao:
            question_list = []
            seen = set()
            for row in rows:
                q = row.get("questao")
                if q and q not in seen:
                    seen.add(q)
                    entry = {"code": q}
                    if q in sheet_dict:
                        entry["text"] = sheet_dict[q].get("text", "")
                    question_list.append(entry)
            question_list.sort(key=lambda x: x["code"])

        result = {"dataset": dataset, "data": rows}
        if question_text:
            result["question_text"] = question_text
        if question_list is not None:
            result["questions"] = question_list
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 9. GET /proficiency/ranking
# ---------------------------------------------------------------------------

@router.get("/proficiency/ranking")
def proficiency_ranking(
    serie: str = Query(..., description="Serie (ex: 5EF, 9EF)"),
    disciplina: str = Query(..., description="Disciplina (LP, MT, etc.)"),
    rede: Optional[str] = Query(None, description="Filtro de rede"),
):
    """Ranking de UFs por proficiencia para serie/disciplina especifica."""
    rede_code = _parse_rede(rede)
    try:
        conditions = ["serie = ?", "disciplina = ?"]
        params: list = [serie.upper(), disciplina.upper()]

        if rede_code is not None:
            conditions.append("rede = ?")
            params.append(rede_code)
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
