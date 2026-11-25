"""
Teacher analysis module for the SAEB/TIC education dashboard.

Role in the architecture
------------------------
Programmatic analytical library over ``TS_PROFESSOR.parquet`` and student
microdata Parquets (used by validation scripts, analytical notebooks, and
regression tests alongside the pre-computed ``quest_professor_rj`` DuckDB
table served by ``/api/saeb/questionnaire/professor``).

Units of analysis
-----------------
* Descriptive functions (:func:`get_teacher_profile_rj`,
  :func:`get_teacher_tech_training_rj` / :func:`get_teacher_tech_usage_rj`):
  deduplicate ``TS_PROFESSOR`` to **one row per unique teacher**
  (``ID_PROFESSOR``, prioritizing the main class where
  ``IN_PREENCHIMENTO_OUTRA_TURMA = 0``), matching ``quest_professor_rj``.
* Class–student cross-analysis (:func:`get_formation_vs_proficiency_rj`):
  deduplicates ``(ID_TURMA, ID_PROFESSOR)`` pairs and divides each student's
  sampling weight by the number of responding teachers in their class.
"""

from typing import Any, Dict, List, Optional

import duckdb
import numpy as np

from backend.analysis.stats_utils import (
    confidence_interval_mean,
    to_float,
    to_str,
)
from backend.config import (
    ID_UF_RJ,
    PROFICIENCY_COLS,
    SAEB_PARQUET_DIR,
    WEIGHT_COLS,
)

_PROFESSOR_PARQUET = str(SAEB_PARQUET_DIR / "TS_PROFESSOR.parquet")

# Professor questionnaire mappings (SAEB 2023), following the official
# dictionary (data/processed/saeb_questionnaire_dict.json, sheet TS_PROFESSOR):
#   TX_Q001 = sexo, TX_Q020 = maior nível de escolaridade concluído.
# (TX_Q004–TX_Q007 ask about disability/ASD/giftedness — not formation —
# and the 2023 questionnaire has no "years of experience" item.)
_GENDER_COL = "TX_Q001"
_EDUCATION_COL = "TX_Q020"

_GENDER_MAP: Dict[str, str] = {
    "A": "Masculino",
    "B": "Feminino",
    "C": "Não quero declarar",
}

_EDUCATION_MAP: Dict[str, str] = {
    "A": "Ensino Médio - Magistério",
    "B": "Graduação",
    "C": "Especialização",
    "D": "Mestrado",
    "E": "Doutorado",
}


def _dedup_professor_cte(parquet_path: str) -> str:
    """CTE SQL deduplicating TS_PROFESSOR to 1 row per unique ID_PROFESSOR."""
    return f"""
        WITH dedup_prof AS (
            SELECT *
            FROM '{parquet_path}'
            WHERE ID_UF = ?
              AND COALESCE(IN_PREENCHIMENTO_QUESTIONARIO, 1) = 1
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY ID_PROFESSOR
                ORDER BY COALESCE(IN_PREENCHIMENTO_OUTRA_TURMA, 0) ASC, ID_ESCOLA ASC, ID_TURMA ASC
            ) = 1
        )
    """


def _count_by_category(
    con: duckdb.DuckDBPyConnection,
    column: str,
    label_map: Dict[str, str],
    uf: int = ID_UF_RJ,
) -> List[Dict[str, Any]]:
    """Count unique teachers by category for a given questionnaire column in RJ."""
    query = f"""
        {_dedup_professor_cte(_PROFESSOR_PARQUET)}
        SELECT {column} AS cat, COUNT(*) AS cnt
        FROM dedup_prof
        WHERE {column} IS NOT NULL
          AND {column} NOT IN ('*', '.', '')
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


_SERIE_FILE_MAP: Dict[str, str] = {
    "5EF": "TS_ALUNO_5EF",
    "9EF": "TS_ALUNO_9EF",
    "EM": "TS_ALUNO_34EM",
    "3EM": "TS_ALUNO_34EM",
    "4EM": "TS_ALUNO_34EM",
    "34EM": "TS_ALUNO_34EM",
}

_SERIE_ID_MAP: Dict[str, int] = {
    "3EM": 12,
    "4EM": 13,
}

_SERIE_DISCIPLINAS: Dict[str, frozenset[str]] = {
    "TS_ALUNO_5EF": frozenset({"LP", "MT", "CH", "CN"}),
    "TS_ALUNO_9EF": frozenset({"LP", "MT", "CH", "CN"}),
    "TS_ALUNO_34EM": frozenset({"LP", "MT"}),
}


def get_teacher_profile_rj(
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return unique teacher demographics for RJ: gender and education level.

    Returns
    -------
    dict with keys: total_teachers, gender, education.
    Each sub-key contains a list of {code, label, count, proportion}.
    """
    con = duckdb.connect()
    try:
        total_query = f"""
            {_dedup_professor_cte(_PROFESSOR_PARQUET)}
            SELECT COUNT(*) FROM dedup_prof
        """
        row = con.execute(total_query, [uf]).fetchone()
        total = int(row[0]) if row is not None else 0

        gender = _count_by_category(con, _GENDER_COL, _GENDER_MAP, uf)
        education = _count_by_category(con, _EDUCATION_COL, _EDUCATION_MAP, uf)
    finally:
        con.close()

    return {
        "total_teachers": total,
        "gender": gender,
        "education": education,
    }


def get_teacher_tech_training_rj(
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return technology training data from teacher questionnaire (unique teachers).

    Analyzes TX_Q029 (how much this year's training contributed to using new
    technologies) and TX_Q037 (how much the teacher *needs* training on the
    use of new ICTs), deduplicating ``TS_PROFESSOR`` by ``ID_PROFESSOR``.

    Returns
    -------
    dict with keys: tech_training (TX_Q029 distribution),
    tech_training_need (TX_Q037 distribution), total_respondents.
    """
    con = duckdb.connect()
    try:
        cte = _dedup_professor_cte(_PROFESSOR_PARQUET)
        total_query = f"{cte} SELECT COUNT(*) FROM dedup_prof"
        row = con.execute(total_query, [uf]).fetchone()
        total = int(row[0]) if row is not None else 0

        # TX_Q029 - contribution of training to the use of new technologies
        q029_query = f"""
            {cte}
            SELECT TX_Q029 AS cat, COUNT(*) AS cnt
            FROM dedup_prof
            WHERE TX_Q029 IS NOT NULL
              AND TX_Q029 NOT IN ('*', '.', '')
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

        # TX_Q037 - need for training on the use of new ICTs
        q037_query = f"""
            {cte}
            SELECT TX_Q037 AS cat, COUNT(*) AS cnt
            FROM dedup_prof
            WHERE TX_Q037 IS NOT NULL
              AND TX_Q037 NOT IN ('*', '.', '')
            GROUP BY TX_Q037
            ORDER BY TX_Q037
        """
        q037_rows = con.execute(q037_query, [uf]).fetchall()
        q037_total = sum(r[1] for r in q037_rows)
        tech_training_need: List[Dict[str, Any]] = []
        for cat_val, cnt in q037_rows:
            tech_training_need.append({
                "code": str(cat_val),
                "count": int(cnt),
                "proportion": round(cnt / q037_total, 4) if q037_total > 0 else 0.0,
            })
    finally:
        con.close()

    return {
        "total_respondents": total,
        "tech_training": tech_training,
        "tech_training_need": tech_training_need,
    }


get_teacher_tech_usage_rj = get_teacher_tech_training_rj


def get_formation_vs_proficiency_rj(
    serie: str = "9EF",
    disciplina: str = "LP",
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return relationship between teacher formation and student performance.

    Joins professor data with student proficiency data via class (ID_TURMA)
    to compute mean proficiency by teacher education level (TX_Q020).
    Classes may have more than one responding teacher (no discipline
    indicator exists), so each student–teacher pair is weighted by
    1 / (number of responding teachers of the class).

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
    mean proficiency, CI and n_pairs = number of student–teacher pairs).
    """
    serie_key = serie.strip().upper()
    aluno_file = _SERIE_FILE_MAP.get(serie_key)
    if aluno_file is None:
        raise ValueError(
            f"Serie '{serie}' not recognized. Valid: {list(_SERIE_FILE_MAP.keys())}"
        )

    disc = disciplina.strip().upper()
    allowed = _SERIE_DISCIPLINAS[aluno_file]
    prof_col = PROFICIENCY_COLS.get(disc)
    weight_col = WEIGHT_COLS.get(disc)
    if disc not in allowed or prof_col is None or weight_col is None:
        raise ValueError(
            f"Disciplina '{disciplina}' not available for serie '{serie}'. "
            f"Valid: {sorted(allowed)}"
        )

    aluno_parquet = str(SAEB_PARQUET_DIR / f"{aluno_file}.parquet")
    id_serie = _SERIE_ID_MAP.get(serie_key)
    serie_clause = " AND ID_SERIE = ?" if id_serie is not None else ""
    params: List[int] = [uf, uf] + ([id_serie] if id_serie is not None else [])

    con = duckdb.connect()
    try:
        # Join teachers with students via ID_TURMA to link formation to proficiency.
        # Deduplicate (ID_TURMA, ID_PROFESSOR) in case the same teacher answered
        # more than once for the same class.
        query = f"""
            WITH teacher_formation AS (
                SELECT
                    ID_TURMA,
                    ID_PROFESSOR,
                    MIN({_EDUCATION_COL}) AS formation
                FROM '{_PROFESSOR_PARQUET}'
                WHERE ID_UF = ?
                  AND {_EDUCATION_COL} IS NOT NULL
                  AND {_EDUCATION_COL} NOT IN ('*', '.', '')
                  AND IN_PREENCHIMENTO_QUESTIONARIO = 1
                GROUP BY ID_TURMA, ID_PROFESSOR
            ),
            teachers_per_class AS (
                SELECT ID_TURMA, COUNT(*) AS n_prof
                FROM teacher_formation
                GROUP BY ID_TURMA
            ),
            student_prof AS (
                SELECT
                    ID_TURMA,
                    ID_ESCOLA,
                    ESTRATO,
                    {prof_col} AS prof,
                    {weight_col} AS peso
                FROM '{aluno_parquet}'
                WHERE ID_UF = ?{serie_clause}
            )
            -- LEFT JOIN: alunos sem professor respondente ficam no desenho
            -- (estimação por domínio), com formação NULL
            SELECT
                tf.formation,
                sp.prof,
                sp.peso / COALESCE(k.n_prof, 1) AS peso,
                sp.ID_ESCOLA AS escola,
                sp.ESTRATO AS estrato
            FROM student_prof sp
            LEFT JOIN teacher_formation tf ON sp.ID_TURMA = tf.ID_TURMA
            LEFT JOIN teachers_per_class k ON sp.ID_TURMA = k.ID_TURMA
        """
        df = con.execute(query, params).fetchnumpy()
    finally:
        con.close()

    formation = to_str(df["formation"])
    prof_vals = to_float(df["prof"])
    peso_vals = to_float(df["peso"])
    escola = np.asarray(df["escola"])
    estrato = np.asarray(df["estrato"])
    valid = ~np.isnan(prof_vals) & ~np.isnan(peso_vals) & np.isin(formation, list(_EDUCATION_MAP))

    def _sf(x: float) -> Optional[float]:
        return None if x is None or np.isnan(x) else float(x)

    by_formation: List[Dict[str, Any]] = []
    for raw_code in sorted(set(formation[valid])):
        form_code = str(raw_code)
        mask = valid & (formation == form_code)
        # IC de desenho (domínio): estratos + escolas; os pares do mesmo aluno
        # ficam no mesmo conglomerado
        mean_val, ci_lo, ci_hi = confidence_interval_mean(
            prof_vals, peso_vals, strata=estrato, clusters=escola, domain=mask
        )
        by_formation.append({
            "formation_code": form_code,
            "formation_label": _EDUCATION_MAP.get(form_code, form_code),
            "mean_proficiency": _sf(mean_val),
            "ci_lower": _sf(ci_lo),
            "ci_upper": _sf(ci_hi),
            "n_pairs": int(mask.sum()),
        })

    return {"by_formation": by_formation}
