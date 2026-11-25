"""Rotas da API para cruzamentos tecnologia x desempenho."""

from typing import Optional

import duckdb
from fastapi import APIRouter, HTTPException, Query

from backend.config import ID_UF_RJ, SAEB_PARQUET_DIR
from backend.db import db_query
from backend.analysis.cross_analysis import (
    DIRECTOR_TECH_VARS,
    SCHOOL_MEDIA_COLS,
    STUDENT_TECH_VARS,
    get_cross_summary,
    get_digital_access_index,
    get_director_tech_gap,
    get_student_tech_gap,
    get_teacher_tech_impact,
)

router = APIRouter()

_query = db_query

_FAIXA_LABELS = {"Baixo": "Baixo", "Medio": "Médio", "Alto": "Alto"}


# ---------------------------------------------------------------------------
# 1. GET /student-tech
# ---------------------------------------------------------------------------

@router.get("/student-tech")
def student_tech(
    serie: str = Query("9EF", description="Serie (5EF, 9EF, 34EM)"),
    disciplina: str = Query("LP", description="Disciplina (LP, MT)"),
    variable: Optional[str] = Query(None, description="Variavel tech (TX_RESP_Q12b, Q12g, Q13a, Q13b)"),
    stratify_inse: bool = Query(False, description="Estratificar por INSE"),
    use_precomputed: bool = Query(True, description="Usar tabela pre-computada"),
):
    """Acesso digital do aluno vs proficiencia."""
    try:
        if use_precomputed and not stratify_inse and variable:
            # Fast path: pre-computed table
            rows = _query(
                """SELECT tech_response, media_proficiencia, soma_pesos, n_alunos
                   FROM cross_aluno_tech_rj
                   WHERE serie = ? AND disciplina = ? AND tech_variable = ?
                     AND nivel_inse IS NULL
                   ORDER BY tech_response""",
                [serie.upper(), disciplina.upper(), variable],
            )
            if rows:
                var_info = STUDENT_TECH_VARS.get(variable, {})
                responses = var_info.get("responses", {})
                groups = [
                    {
                        "code": r["tech_response"],
                        "label": responses.get(r["tech_response"], r["tech_response"]),
                        "mean": r["media_proficiencia"],
                        "n": r["n_alunos"],
                    }
                    for r in rows
                ]
                return {
                    "variable": variable,
                    "label": var_info.get("label", variable),
                    "serie": serie, "disciplina": disciplina,
                    "groups": groups, "source": "precomputed",
                }

        # Full statistical analysis
        if variable:
            return get_student_tech_gap(serie, disciplina, variable, stratify_inse=stratify_inse)

        # All variables
        results = []
        for var in STUDENT_TECH_VARS:
            try:
                r = get_student_tech_gap(serie, disciplina, var, stratify_inse=stratify_inse)
                results.append(r)
            except Exception:
                continue
        return {"variables": results}

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 4. GET /digital-index
# ---------------------------------------------------------------------------

@router.get("/digital-index")
def digital_index(
    serie: str = Query("9EF", description="Serie"),
    disciplina: str = Query("LP", description="Disciplina"),
    stratify_inse: bool = Query(False, description="Estratificar por INSE"),
    use_precomputed: bool = Query(True, description="Usar tabela pre-computada"),
):
    """Indice digital composto vs proficiencia."""
    try:
        if use_precomputed:
            rows = _query(
                """SELECT digital_index, faixa_digital, media_proficiencia, soma_pesos, n_alunos
                   FROM cross_digital_index_rj
                   WHERE serie = ? AND disciplina = ? AND nivel_inse IS NULL
                   ORDER BY digital_index""",
                [serie.upper(), disciplina.upper()],
            )
            if rows:
                by_level = [
                    {"index": r["digital_index"], "mean": r["media_proficiencia"], "n": r["n_alunos"]}
                    for r in rows
                ]
                faixas_map = {}
                for r in rows:
                    f = r["faixa_digital"]
                    if f not in faixas_map:
                        faixas_map[f] = {"label": f, "total_n": 0, "weighted_sum": 0.0, "total_weight": 0.0}
                    faixas_map[f]["total_n"] += r["n_alunos"]
                    faixas_map[f]["weighted_sum"] += (r["media_proficiencia"] or 0) * (r["soma_pesos"] or 0)
                    faixas_map[f]["total_weight"] += (r["soma_pesos"] or 0)

                faixas = []
                for f_name in ["Baixo", "Medio", "Alto"]:
                    fm = faixas_map.get(f_name)
                    if fm and fm["total_weight"] > 0:
                        faixas.append({
                            "code": f_name,
                            "label": _FAIXA_LABELS[f_name],
                            "mean": fm["weighted_sum"] / fm["total_weight"],
                            "n": fm["total_n"],
                        })

                result = {
                    "serie": serie, "disciplina": disciplina,
                    "faixas": faixas, "by_level": by_level,
                    "source": "precomputed",
                }

                if stratify_inse:
                    inse_rows = _query(
                        """SELECT nivel_inse, digital_index, faixa_digital,
                                  media_proficiencia, soma_pesos, n_alunos
                           FROM cross_digital_index_rj
                           WHERE serie = ? AND disciplina = ? AND nivel_inse IS NOT NULL
                           ORDER BY nivel_inse, digital_index""",
                        [serie.upper(), disciplina.upper()],
                    )
                    result["by_inse"] = inse_rows

                return result

        return get_digital_access_index(serie, disciplina, stratify_inse=stratify_inse)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    media_col = SCHOOL_MEDIA_COLS.get((serie.upper(), disciplina.upper()))
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
            "serie": serie, "disciplina": disciplina, "tech_var": tech_var,
            "data": [
                {"inse": r[0], "proficiencia": r[1], "tech_value": r[2], "rede": r[3]}
                for r in rows
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
