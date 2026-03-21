"""
Teacher analysis module for the SAEB/TIC education dashboard.

Provides functions to analyze teacher demographics, technology training,
and the relationship between teacher formation and student proficiency.
"""

from typing import Any, Dict, List, Optional

import duckdb
import numpy as np

from backend.analysis.stats_utils import (
    confidence_interval_mean,
    weighted_mean,
)
from backend.config import (
    DUCKDB_PATH,
    ID_UF_RJ,
    PROFICIENCY_COLS,
    SAEB_PARQUET_DIR,
    WEIGHT_COLS,
)

_PROFESSOR_PARQUET = str(SAEB_PARQUET_DIR / "TS_PROFESSOR.parquet")

# Professor questionnaire mappings (SAEB 2023).
# TX_Q001 = Gender, TX_Q004 = Education level, TX_Q005 = Experience years
_GENDER_MAP: Dict[str, str] = {
    "A": "Masculino",
    "B": "Feminino",
    "C": "Não quero declarar",
}

_EDUCATION_MAP: Dict[str, str] = {
    "A": "Ensino Médio - Magistério/Normal",
    "B": "Ensino Médio - Outros",
    "C": "Ensino Superior - Pedagogia",
    "D": "Ensino Superior - Licenciatura LP",
    "E": "Ensino Superior - Licenciatura MT",
    "F": "Ensino Superior - Licenciatura Outros",
    "G": "Ensino Superior - Outros",
}

_EXPERIENCE_MAP: Dict[str, str] = {
    "A": "Menos de 1 ano",
    "B": "1 a 2 anos",
    "C": "3 a 5 anos",
    "D": "6 a 9 anos",
    "E": "10 a 15 anos",
    "F": "16 a 20 anos",
    "G": "Mais de 20 anos",
}


def _count_by_category(
    con: duckdb.DuckDBPyConnection,
    column: str,
    label_map: Dict[str, str],
    uf: int = ID_UF_RJ,
) -> List[Dict[str, Any]]:
    """Count teachers by category for a given questionnaire column in RJ."""
    query = f"""
        SELECT {column} AS cat, COUNT(*) AS cnt
        FROM '{_PROFESSOR_PARQUET}'
        WHERE ID_UF = ?
          AND {column} IS NOT NULL
          AND IN_PREENCHIMENTO_QUESTIONARIO = 1
        GROUP BY {column}
        ORDER BY {column}
    """
    rows = con.execute(query, [uf]).fetchall()
    total = sum(r[1] for r in rows)
    result: List[Dict[str, Any]] = []
    for cat_val, cnt in rows:
        result.append({
            "code": str(cat_val),
            "label": label_map.get(str(cat_val), str(cat_val)),
            "count": int(cnt),
            "proportion": round(cnt / total, 4) if total > 0 else 0.0,
        })
    return result


def get_teacher_profile_rj(
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return teacher demographics for RJ: gender, education, experience.

    Returns
    -------
    dict with keys: total_teachers, gender, education, experience.
    Each sub-key contains a list of {code, label, count, proportion}.
    """
    con = duckdb.connect()

    # Total teachers with completed questionnaire
    total_query = f"""
        SELECT COUNT(*) FROM '{_PROFESSOR_PARQUET}'
        WHERE ID_UF = ? AND IN_PREENCHIMENTO_QUESTIONARIO = 1
    """
    total = con.execute(total_query, [uf]).fetchone()[0]

    gender = _count_by_category(con, "TX_Q001", _GENDER_MAP, uf)
    education = _count_by_category(con, "TX_Q004", _EDUCATION_MAP, uf)
    experience = _count_by_category(con, "TX_Q005", _EXPERIENCE_MAP, uf)

    con.close()

    return {
        "total_teachers": int(total),
        "gender": gender,
        "education": education,
        "experience": experience,
    }


def get_teacher_tech_training_rj(
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return technology training data from teacher questionnaire.

    Analyzes TX_Q029 (participation in continuing education / tech training)
    and TX_Q037 (use of technology in pedagogical practice).

    Returns
    -------
    dict with keys: tech_training (TX_Q029 distribution),
    tech_usage (TX_Q037 distribution), total_respondents.
    """
    con = duckdb.connect()

    total_query = f"""
        SELECT COUNT(*) FROM '{_PROFESSOR_PARQUET}'
        WHERE ID_UF = ? AND IN_PREENCHIMENTO_QUESTIONARIO = 1
    """
    total = con.execute(total_query, [uf]).fetchone()[0]

    # TX_Q029 - tech training participation
    q029_query = f"""
        SELECT TX_Q029 AS cat, COUNT(*) AS cnt
        FROM '{_PROFESSOR_PARQUET}'
        WHERE ID_UF = ?
          AND TX_Q029 IS NOT NULL
          AND IN_PREENCHIMENTO_QUESTIONARIO = 1
        GROUP BY TX_Q029
        ORDER BY TX_Q029
    """
    q029_rows = con.execute(q029_query, [uf]).fetchall()
    q029_total = sum(r[1] for r in q029_rows)
    tech_training: List[Dict[str, Any]] = []
    for cat_val, cnt in q029_rows:
        tech_training.append({
            "code": str(cat_val),
            "count": int(cnt),
            "proportion": round(cnt / q029_total, 4) if q029_total > 0 else 0.0,
        })

    # TX_Q037 - technology usage in practice
    q037_query = f"""
        SELECT TX_Q037 AS cat, COUNT(*) AS cnt
        FROM '{_PROFESSOR_PARQUET}'
        WHERE ID_UF = ?
          AND TX_Q037 IS NOT NULL
          AND IN_PREENCHIMENTO_QUESTIONARIO = 1
        GROUP BY TX_Q037
        ORDER BY TX_Q037
    """
    q037_rows = con.execute(q037_query, [uf]).fetchall()
    q037_total = sum(r[1] for r in q037_rows)
    tech_usage: List[Dict[str, Any]] = []
    for cat_val, cnt in q037_rows:
        tech_usage.append({
            "code": str(cat_val),
            "count": int(cnt),
            "proportion": round(cnt / q037_total, 4) if q037_total > 0 else 0.0,
        })

    con.close()

    return {
        "total_respondents": int(total),
        "tech_training": tech_training,
        "tech_usage": tech_usage,
    }


def get_formation_vs_proficiency_rj(
    serie: str = "9EF",
    disciplina: str = "LP",
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return relationship between teacher formation and student performance.

    Joins professor data with student proficiency data via school/class
    to compute mean proficiency by teacher education level (TX_Q004).

    Parameters
    ----------
    serie : str
        Student serie (e.g. '5EF', '9EF').
    disciplina : str
        'LP', 'MT', etc.
    uf : int
        IBGE UF code.

    Returns
    -------
    dict with keys: by_formation (list of dicts with formation level,
    mean proficiency, CI, n_teachers, n_students).
    """
    disc = disciplina.upper()
    prof_col = PROFICIENCY_COLS.get(disc)
    weight_col = WEIGHT_COLS.get(disc)
    if prof_col is None or weight_col is None:
        raise ValueError(f"Disciplina '{disciplina}' not recognized.")

    # Determine aluno parquet file
    serie_map: Dict[str, str] = {
        "2EF": "TS_ALUNO_2EF",
        "5EF": "TS_ALUNO_5EF",
        "9EF": "TS_ALUNO_9EF",
        "EM": "TS_ALUNO_34EM",
        "3EM": "TS_ALUNO_34EM",
        "4EM": "TS_ALUNO_34EM",
        "34EM": "TS_ALUNO_34EM",
    }
    aluno_file = serie_map.get(serie.upper())
    if aluno_file is None:
        raise ValueError(f"Serie '{serie}' not recognized.")

    aluno_parquet = str(SAEB_PARQUET_DIR / f"{aluno_file}.parquet")

    con = duckdb.connect()

    # Join teachers with students via ID_TURMA to link formation to proficiency.
    # A teacher may teach multiple classes; a class has one teacher for the subject.
    query = f"""
        WITH teacher_formation AS (
            SELECT
                ID_TURMA,
                TX_Q004 AS formation,
                ID_PROFESSOR
            FROM '{_PROFESSOR_PARQUET}'
            WHERE ID_UF = ?
              AND TX_Q004 IS NOT NULL
              AND IN_PREENCHIMENTO_QUESTIONARIO = 1
        ),
        student_prof AS (
            SELECT
                ID_TURMA,
                {prof_col} AS prof,
                {weight_col} AS peso
            FROM '{aluno_parquet}'
            WHERE ID_UF = ?
              AND {prof_col} IS NOT NULL
              AND {weight_col} IS NOT NULL
        )
        SELECT
            tf.formation,
            sp.prof,
            sp.peso
        FROM student_prof sp
        INNER JOIN teacher_formation tf ON sp.ID_TURMA = tf.ID_TURMA
    """
    df = con.execute(query, [uf, uf]).fetchnumpy()
    con.close()

    if len(df.get("formation", [])) == 0:
        return {"by_formation": []}

    formation = np.asarray(df["formation"])
    prof_vals = np.asarray(df["prof"], dtype=np.float64)
    peso_vals = np.asarray(df["peso"], dtype=np.float64)

    # Group by formation level
    unique_formations = sorted(set(str(f) for f in formation if f is not None))
    by_formation: List[Dict[str, Any]] = []

    for form_code in unique_formations:
        mask = np.array([str(f) == form_code for f in formation])
        if not mask.any():
            continue

        v = prof_vals[mask]
        w = peso_vals[mask]
        valid = ~np.isnan(v) & ~np.isnan(w)
        if not valid.any():
            continue

        mean_val, ci_lo, ci_hi = confidence_interval_mean(v[valid], w[valid])

        by_formation.append({
            "formation_code": form_code,
            "formation_label": _EDUCATION_MAP.get(form_code, form_code),
            "mean_proficiency": float(mean_val),
            "ci_lower": float(ci_lo),
            "ci_upper": float(ci_hi),
            "n_students": int(valid.sum()),
        })

    return {"by_formation": by_formation}
