"""Rotas da API para cruzamentos tecnologia x desempenho."""

import logging
from typing import Optional

import duckdb
from fastapi import APIRouter, HTTPException, Query

from backend.config import ID_UF_RJ, SAEB_PARQUET_DIR
from backend.analysis.cross_analysis import (
    DIRECTOR_TECH_VARS,
    SCHOOL_MEDIA_COLS,
    STUDENT_TECH_VARS,
    get_cross_summary,
    get_digital_access_index,
    get_director_tech_gap,
    get_student_tech_gap,
    get_teacher_tech_impact,
    validate_student_params,
)

logger = logging.getLogger(__name__)
_INTERNAL_ERROR_DETAIL = "Erro interno ao processar a consulta."

router = APIRouter()


# ---------------------------------------------------------------------------
# 1. GET /student-tech
# ---------------------------------------------------------------------------

@router.get("/student-tech")
def student_tech(
    serie: str = Query("9EF", description="Serie (5EF, 9EF, 34EM)"),
    disciplina: str = Query("LP", description="Disciplina (LP, MT)"),
    variable: Optional[str] = Query(None, description="Variavel tech (TX_RESP_Q12b, Q12g, Q13a, Q13b)"),
    stratify_inse: bool = Query(False, description="Estratificar por INSE"),
    use_precomputed: bool = Query(
        True,
        description="Mantido por compatibilidade; retorna sempre a análise estatística completa (com cache).",
    ),
):
    """Acesso digital do aluno vs proficiencia (sempre retorna contrato estatístico completo)."""
    _ = use_precomputed
    try:
        serie_norm, disc_norm, *_ = validate_student_params(serie, disciplina)
        if variable is not None and variable not in STUDENT_TECH_VARS:
            raise ValueError(
                f"Variable '{variable}' not recognized. "
                f"Valid: {list(STUDENT_TECH_VARS.keys())}"
            )

        if variable:
            return get_student_tech_gap(serie_norm, disc_norm, variable, stratify_inse=stratify_inse)

        results = [
            get_student_tech_gap(serie_norm, disc_norm, var, stratify_inse=stratify_inse)
            for var in STUDENT_TECH_VARS
        ]
        return {"variables": results}

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception(
            "Erro em /api/cross/student-tech (serie=%s, disciplina=%s, variable=%s)",
            serie, disciplina, variable,
        )
        raise HTTPException(status_code=500, detail=_INTERNAL_ERROR_DETAIL)


# ---------------------------------------------------------------------------
# 2. GET /director-tech
# ---------------------------------------------------------------------------

@router.get("/director-tech")
def director_tech(
    variable: str = Query("TX_Q194", description="Variavel tech do diretor"),
    serie: str = Query("9EF", description="Serie"),
    disciplina: str = Query("LP", description="Disciplina"),
    use_precomputed: bool = Query(
        True,
        description="Ignorado (mantido por compatibilidade): a análise é sempre "
                    "calculada a partir dos parquets de escola/diretor, que são pequenos.",
    ),
):
    """Infraestrutura tech da escola (diretor) vs proficiencia.

    Sempre usa a análise completa (uma linha por escola, com teste t/ANOVA).
    A antiga tabela ``cross_diretor_tech_rj`` contava escolas repetidas
    (TS_DIRETOR tem uma linha por escola e série) e não é mais utilizada.
    """
    try:
        return get_director_tech_gap(variable, serie, disciplina)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception(
            "Erro em /api/cross/director-tech (variable=%s, serie=%s, disciplina=%s)",
            variable, serie, disciplina,
        )
        raise HTTPException(status_code=500, detail=_INTERNAL_ERROR_DETAIL)


# ---------------------------------------------------------------------------
# 3. GET /teacher-tech
# ---------------------------------------------------------------------------

@router.get("/teacher-tech")
def teacher_tech(
    variable: str = Query("TX_Q029", description="Variavel tech do professor"),
    serie: str = Query("9EF", description="Serie"),
    disciplina: str = Query("LP", description="Disciplina"),
    use_precomputed: bool = Query(
        True,
        description="Ignorado (mantido por compatibilidade): a análise é sempre "
                    "calculada com ponderação por número de professores da turma.",
    ),
):
    """Formacao/necessidade de tecnologia do professor vs proficiencia do aluno.

    Sempre usa a análise completa: a antiga tabela ``cross_professor_tech_rj``
    contava duas vezes alunos de turmas com mais de um professor respondente.
    """
    try:
        return get_teacher_tech_impact(serie, disciplina, variable)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception(
            "Erro em /api/cross/teacher-tech (variable=%s, serie=%s, disciplina=%s)",
            variable, serie, disciplina,
        )
        raise HTTPException(status_code=500, detail=_INTERNAL_ERROR_DETAIL)


# ---------------------------------------------------------------------------
# 4. GET /digital-index
# ---------------------------------------------------------------------------

@router.get("/digital-index")
def digital_index(
    serie: str = Query("9EF", description="Serie"),
    disciplina: str = Query("LP", description="Disciplina"),
    stratify_inse: bool = Query(False, description="Estratificar por INSE"),
    use_precomputed: bool = Query(
        True,
        description="Mantido por compatibilidade; retorna sempre a análise estatística completa (com cache).",
    ),
):
    """Indice digital composto vs proficiencia (sempre retorna contrato estatístico completo)."""
    _ = use_precomputed
    try:
        serie_norm, disc_norm, *_ = validate_student_params(serie, disciplina)
        return get_digital_access_index(serie_norm, disc_norm, stratify_inse=stratify_inse)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception(
            "Erro em /api/cross/digital-index (serie=%s, disciplina=%s)",
            serie, disciplina,
        )
        raise HTTPException(status_code=500, detail=_INTERNAL_ERROR_DETAIL)


# ---------------------------------------------------------------------------
# 5. GET /summary
# ---------------------------------------------------------------------------

@router.get("/summary")
def summary(
    serie: str = Query("9EF", description="Serie"),
    disciplina: str = Query("LP", description="Disciplina"),
):
    """Resumo de todas as analises cruzadas: gaps, efeitos, significancia."""
    try:
        return get_cross_summary(serie, disciplina)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception(
            "Erro em /api/cross/summary (serie=%s, disciplina=%s)",
            serie, disciplina,
        )
        raise HTTPException(status_code=500, detail=_INTERNAL_ERROR_DETAIL)


# ---------------------------------------------------------------------------
# 6. GET /school-scatter
# ---------------------------------------------------------------------------

@router.get("/school-scatter")
def school_scatter(
    serie: str = Query("9EF", description="Serie"),
    disciplina: str = Query("LP", description="Disciplina"),
    tech_var: str = Query("TX_Q034", description="Variavel tech do diretor para eixo X"),
):
    """Dados scatter escola: INSE x proficiencia x tech (para grafico de dispersao)."""
    # tech_var é interpolado no SQL como nome de coluna: só aceitar a whitelist
    if tech_var not in DIRECTOR_TECH_VARS:
        raise HTTPException(
            status_code=400,
            detail=f"Variavel '{tech_var}' invalida. Opcoes: {list(DIRECTOR_TECH_VARS)}",
        )
    serie_norm = serie.strip().upper()
    disc_norm = disciplina.strip().upper()
    media_col = SCHOOL_MEDIA_COLS.get((serie_norm, disc_norm))
    if not media_col:
        raise HTTPException(
            status_code=400,
            detail=f"Combinacao serie={serie}, disciplina={disciplina} invalida",
        )

    pq_esc = str(SAEB_PARQUET_DIR / "TS_ESCOLA.parquet")
    pq_dir = str(SAEB_PARQUET_DIR / "TS_DIRETOR.parquet")
    try:
        con = duckdb.connect()
        try:
            rows = con.execute(f"""
                WITH dir AS (
                    -- TS_DIRETOR repete a escola em uma linha por série avaliada
                    SELECT ID_ESCOLA, MIN({tech_var}) AS tech_value
                    FROM '{pq_dir}'
                    WHERE ID_UF = ?
                      AND {tech_var} IS NOT NULL
                      AND {tech_var} NOT IN ('*', '.', '')
                      AND IN_PREENCHIMENTO_QUESTIONARIO = 1
                    GROUP BY ID_ESCOLA
                )
                SELECT
                    e.NIVEL_SOCIO_ECONOMICO AS inse,
                    TRY_CAST(e.{media_col} AS DOUBLE) AS proficiencia,
                    d.tech_value,
                    e.IN_PUBLICA AS rede
                FROM '{pq_esc}' e
                INNER JOIN dir d ON e.ID_ESCOLA = d.ID_ESCOLA
                WHERE e.ID_UF = ?
                  AND e.{media_col} IS NOT NULL
                ORDER BY e.ID_ESCOLA
                LIMIT 5000
            """, [ID_UF_RJ, ID_UF_RJ]).fetchall()
        finally:
            con.close()

        return {
            "serie": serie_norm, "disciplina": disc_norm, "tech_var": tech_var,
            "data": [
                {"inse": r[0], "proficiencia": r[1], "tech_value": r[2], "rede": r[3]}
                for r in rows
            ],
        }
    except Exception:
        logger.exception(
            "Erro em /api/cross/school-scatter (serie=%s, disciplina=%s, tech_var=%s)",
            serie, disciplina, tech_var,
        )
        raise HTTPException(status_code=500, detail=_INTERNAL_ERROR_DETAIL)
