"""
Cross-analysis module: Technology access/usage vs student proficiency.

Provides functions to analyze relationships between technology indicators
(from SAEB questionnaires) and student performance, at the student,
school/director, and teacher levels. All analyses support INSE
stratification to control for socioeconomic confounding.
"""

from typing import Any, Dict, List, Optional

import duckdb
import numpy as np

from backend.analysis.stats_utils import (
    cohens_d_weighted,
    confidence_interval_mean,
    pearson_weighted,
    weighted_anova_oneway,
    weighted_mean,
    weighted_std,
    weighted_ttest,
)
from backend.config import (
    DUCKDB_PATH,
    ID_UF_RJ,
    PROFICIENCY_COLS,
    SAEB_PARQUET_DIR,
    WEIGHT_COLS,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SERIE_FILE_MAP: Dict[str, str] = {
    "2EF": "TS_ALUNO_2EF",
    "5EF": "TS_ALUNO_5EF",
    "9EF": "TS_ALUNO_9EF",
    "EM": "TS_ALUNO_34EM",
    "3EM": "TS_ALUNO_34EM",
    "4EM": "TS_ALUNO_34EM",
    "34EM": "TS_ALUNO_34EM",
}

_PROFESSOR_PARQUET = str(SAEB_PARQUET_DIR / "TS_PROFESSOR.parquet")
_DIRETOR_PARQUET = str(SAEB_PARQUET_DIR / "TS_DIRETOR.parquet")
_ESCOLA_PARQUET = str(SAEB_PARQUET_DIR / "TS_ESCOLA.parquet")

# Student technology questions and their response labels (SAEB 2023)
STUDENT_TECH_VARS: Dict[str, Dict[str, Any]] = {
    "TX_RESP_Q12b": {
        "label": "Computadores em casa",
        "responses": {"A": "Nenhum", "B": "1", "C": "2", "D": "3 ou mais"},
        "type": "ordinal",
        "numeric_map": {"A": 0, "B": 1, "C": 2, "D": 3},
    },
    "TX_RESP_Q12g": {
        "label": "Celulares com internet",
        "responses": {"A": "Nenhum", "B": "1", "C": "2", "D": "3 ou mais"},
        "type": "ordinal",
        "numeric_map": {"A": 0, "B": 1, "C": 2, "D": 3},
    },
    "TX_RESP_Q13a": {
        "label": "TV por internet (streaming)",
        "responses": {"A": "Não", "B": "Sim"},
        "type": "binary",
        "numeric_map": {"A": 0, "B": 1},
    },
    "TX_RESP_Q13b": {
        "label": "Rede Wi-Fi em casa",
        "responses": {"A": "Não", "B": "Sim"},
        "type": "binary",
        "numeric_map": {"A": 0, "B": 1},
    },
}

# Director technology questions
DIRECTOR_TECH_VARS: Dict[str, Dict[str, Any]] = {
    "TX_Q034": {
        "label": "Computadores na escola",
        "responses": {
            "A": "Inexistente", "B": "Insuficiente", "C": "Regular",
            "D": "Bom", "E": "Excelente",
        },
        "type": "ordinal",
    },
    "TX_Q035": {
        "label": "Softwares educacionais",
        "responses": {
            "A": "Inexistente", "B": "Insuficiente", "C": "Regular",
            "D": "Bom", "E": "Excelente",
        },
        "type": "ordinal",
    },
    "TX_Q036": {
        "label": "Internet banda larga",
        "responses": {
            "A": "Inexistente", "B": "Insuficiente", "C": "Regular",
            "D": "Bom", "E": "Excelente",
        },
        "type": "ordinal",
    },
    "TX_Q194": {
        "label": "Projetos de ciência e tecnologia",
        "responses": {"A": "Sim", "B": "Não"},
        "type": "binary",
    },
    "TX_Q219": {
        "label": "Novas tecnologias educacionais",
        "responses": {"A": "Sim", "B": "Não"},
        "type": "binary",
    },
}

# Professor technology questions
PROFESSOR_TECH_VARS: Dict[str, Dict[str, Any]] = {
    "TX_Q029": {
        "label": "Contribuição da formação em tecnologia",
        "responses": {
            "A": "Não contribuiu",
            "B": "Contribuiu pouco",
            "C": "Contribuiu razoavelmente",
            "D": "Contribuiu muito",
        },
        "type": "ordinal",
    },
    "TX_Q037": {
        "label": "Uso de TICs na prática pedagógica",
        "responses": {
            "A": "Nunca", "B": "Raramente", "C": "Algumas vezes",
            "D": "Frequentemente", "E": "Sempre",
        },
        "type": "ordinal",
    },
}


def _aluno_parquet(serie: str) -> str:
    key = serie.upper()
    filename = _SERIE_FILE_MAP.get(key)
    if filename is None:
        raise ValueError(f"Serie '{serie}' not recognized.")
    return str(SAEB_PARQUET_DIR / f"{filename}.parquet")


def _resolve_cols(disciplina: str) -> tuple[str, str]:
    disc = disciplina.upper()
    prof_col = PROFICIENCY_COLS.get(disc)
    weight_col = WEIGHT_COLS.get(disc)
    if prof_col is None or weight_col is None:
        raise ValueError(f"Disciplina '{disciplina}' not recognized.")
    return prof_col, weight_col


def _safe_float(val: float) -> Optional[float]:
    if val is None or np.isnan(val):
        return None
    return float(val)


def _group_stats_from_arrays(
    prof: np.ndarray, peso: np.ndarray, mask: np.ndarray, label: str
) -> Dict[str, Any]:
    if not mask.any():
        return {"label": label, "mean": None, "ci_lower": None, "ci_upper": None, "n": 0}
    v, w = prof[mask], peso[mask]
    mean, ci_lo, ci_hi = confidence_interval_mean(v, w)
    return {
        "label": label,
        "mean": _safe_float(mean),
        "ci_lower": _safe_float(ci_lo),
        "ci_upper": _safe_float(ci_hi),
        "n": int(mask.sum()),
    }


# ---------------------------------------------------------------------------
# 1. Student technology access vs proficiency
# ---------------------------------------------------------------------------


def get_student_tech_gap(
    serie: str,
    disciplina: str,
    tech_variable: str = "TX_RESP_Q13b",
    uf: int = ID_UF_RJ,
    stratify_inse: bool = False,
) -> Dict[str, Any]:
    """Compare proficiency across student technology access groups.

    Returns groups with mean, CI, n; plus statistical test results.
    For binary variables: t-test + Cohen's d.
    For ordinal variables: ANOVA + linear trend (Pearson on numeric mapping).
    """
    if tech_variable not in STUDENT_TECH_VARS:
        raise ValueError(
            f"Variable '{tech_variable}' not recognized. "
            f"Valid: {list(STUDENT_TECH_VARS.keys())}"
        )

    var_info = STUDENT_TECH_VARS[tech_variable]
    path = _aluno_parquet(serie)
    prof_col, weight_col = _resolve_cols(disciplina)

    con = duckdb.connect()
    query = f"""
        SELECT
            {prof_col} AS prof,
            {weight_col} AS peso,
            {tech_variable} AS tech_resp,
            NU_TIPO_NIVEL_INSE AS nivel_inse
        FROM '{path}'
        WHERE ID_UF = ?
          AND {prof_col} IS NOT NULL
          AND {weight_col} IS NOT NULL
          AND {tech_variable} IS NOT NULL
          AND {tech_variable} NOT IN ('*', '.', '')
    """
    df = con.execute(query, [uf]).fetchnumpy()
    con.close()

    if len(df.get("prof", [])) == 0:
        return {"variable": tech_variable, "label": var_info["label"], "groups": [], "test": None}

    prof = np.asarray(df["prof"], dtype=np.float64)
    peso = np.asarray(df["peso"], dtype=np.float64)
    tech = np.asarray(df["tech_resp"], dtype=str)
    inse = np.asarray(df["nivel_inse"], dtype=np.float64)

    def _analyze_subset(
        prof_s: np.ndarray, peso_s: np.ndarray, tech_s: np.ndarray,
        inse_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        responses = var_info["responses"]
        groups: List[Dict[str, Any]] = []
        for code in sorted(responses.keys()):
            mask = tech_s == code
            stats = _group_stats_from_arrays(prof_s, peso_s, mask, responses[code])
            stats["code"] = code
            groups.append(stats)

        result: Dict[str, Any] = {"groups": groups, "inse_level": inse_level}

        if var_info["type"] == "binary":
            codes = sorted(responses.keys())
            if len(codes) == 2:
                m1 = tech_s == codes[0]
                m2 = tech_s == codes[1]
                if m1.any() and m2.any():
                    t_stat, p_val, diff = weighted_ttest(
                        prof_s[m2], peso_s[m2], prof_s[m1], peso_s[m1]
                    )
                    d = cohens_d_weighted(
                        prof_s[m2], peso_s[m2], prof_s[m1], peso_s[m1]
                    )
                    result["test"] = {
                        "type": "t-test",
                        "t_stat": _safe_float(t_stat),
                        "p_value": _safe_float(p_val),
                        "gap": _safe_float(diff),
                        "cohens_d": _safe_float(d),
                    }
        else:
            # Ordinal: ANOVA + linear trend
            f_stat, p_val, df_b = weighted_anova_oneway(prof_s, peso_s, tech_s)
            result["test"] = {
                "type": "anova",
                "f_stat": _safe_float(f_stat),
                "p_value": _safe_float(p_val),
                "df_between": df_b,
            }
            # Linear trend using numeric mapping
            num_map = var_info.get("numeric_map", {})
            if num_map:
                numeric_vals = np.array([num_map.get(str(t), np.nan) for t in tech_s])
                valid = ~np.isnan(numeric_vals)
                if valid.sum() >= 3:
                    r, p_r = pearson_weighted(
                        numeric_vals[valid], prof_s[valid], peso_s[valid]
                    )
                    result["test"]["trend_r"] = _safe_float(r)
                    result["test"]["trend_p"] = _safe_float(p_r)

        return result

    # Overall analysis
    overall = _analyze_subset(prof, peso, tech)

    result: Dict[str, Any] = {
        "variable": tech_variable,
        "label": var_info["label"],
        "serie": serie,
        "disciplina": disciplina,
        "overall": overall,
    }

    # INSE-stratified analysis
    if stratify_inse:
        by_inse: List[Dict[str, Any]] = []
        valid_inse = ~np.isnan(inse)
        if valid_inse.any():
            levels = sorted(set(int(x) for x in inse[valid_inse]))
            for lvl in levels:
                mask_lvl = (inse == lvl) & valid_inse
                if mask_lvl.sum() < 10:
                    continue
                analysis = _analyze_subset(
                    prof[mask_lvl], peso[mask_lvl], tech[mask_lvl],
                    inse_level=lvl,
                )
                by_inse.append(analysis)
        result["by_inse"] = by_inse

    return result


# ---------------------------------------------------------------------------
# 2. Director-reported school tech vs proficiency
# ---------------------------------------------------------------------------


def get_director_tech_gap(
    tech_variable: str = "TX_Q194",
    serie: str = "9EF",
    disciplina: str = "LP",
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Compare school proficiency by director-reported technology availability.

    Joins TS_DIRETOR with TS_ESCOLA via ID_ESCOLA using MEDIA_* columns.
    """
    if tech_variable not in DIRECTOR_TECH_VARS:
        raise ValueError(
            f"Variable '{tech_variable}' not recognized. "
            f"Valid: {list(DIRECTOR_TECH_VARS.keys())}"
        )

    var_info = DIRECTOR_TECH_VARS[tech_variable]

    # Map serie+disciplina to MEDIA column in TS_ESCOLA
    serie_upper = serie.upper()
    disc_upper = disciplina.upper()
    media_col_map = {
        ("5EF", "LP"): "MEDIA_5EF_LP", ("5EF", "MT"): "MEDIA_5EF_MT",
        ("9EF", "LP"): "MEDIA_9EF_LP", ("9EF", "MT"): "MEDIA_9EF_MT",
        ("34EM", "LP"): "MEDIA_EM_LP", ("34EM", "MT"): "MEDIA_EM_MT",
        ("EM", "LP"): "MEDIA_EM_LP", ("EM", "MT"): "MEDIA_EM_MT",
    }
    media_col = media_col_map.get((serie_upper, disc_upper))
    if media_col is None:
        raise ValueError(f"No MEDIA column for serie={serie}, disciplina={disciplina}")

    con = duckdb.connect()
    query = f"""
        SELECT
            d.{tech_variable} AS tech_resp,
            TRY_CAST(e.{media_col} AS DOUBLE) AS media_prof,
            e.IN_PUBLICA AS rede
        FROM '{_DIRETOR_PARQUET}' d
        INNER JOIN '{_ESCOLA_PARQUET}' e ON d.ID_ESCOLA = e.ID_ESCOLA
        WHERE d.ID_UF = ?
          AND d.{tech_variable} IS NOT NULL
          AND d.{tech_variable} NOT IN ('*', '.', '')
          AND d.IN_PREENCHIMENTO_QUESTIONARIO = 1
          AND e.{media_col} IS NOT NULL
    """
    df = con.execute(query, [uf]).fetchnumpy()
    con.close()

    if len(df.get("tech_resp", [])) == 0:
        return {"variable": tech_variable, "label": var_info["label"], "groups": [], "test": None}

    tech = np.asarray(df["tech_resp"], dtype=str)
    media = np.asarray(df["media_prof"], dtype=np.float64)
    # Use uniform weights for school-level analysis (each school = 1)
    weights = np.ones_like(media)

    responses = var_info["responses"]
    groups: List[Dict[str, Any]] = []
    for code in sorted(responses.keys()):
        mask = tech == code
        stats = _group_stats_from_arrays(media, weights, mask, responses[code])
        stats["code"] = code
        groups.append(stats)

    result: Dict[str, Any] = {
        "variable": tech_variable,
        "label": var_info["label"],
        "serie": serie,
        "disciplina": disciplina,
        "groups": groups,
    }

    if var_info["type"] == "binary":
        codes = sorted(responses.keys())
        if len(codes) == 2:
            m1, m2 = tech == codes[0], tech == codes[1]
            if m1.any() and m2.any():
                t_stat, p_val, diff = weighted_ttest(
                    media[m1], weights[m1], media[m2], weights[m2]
                )
                d = cohens_d_weighted(media[m1], weights[m1], media[m2], weights[m2])
                result["test"] = {
                    "type": "t-test",
                    "t_stat": _safe_float(t_stat), "p_value": _safe_float(p_val),
                    "gap": _safe_float(diff), "cohens_d": _safe_float(d),
                }
    else:
        f_stat, p_val, df_b = weighted_anova_oneway(media, weights, tech)
        result["test"] = {
            "type": "anova",
            "f_stat": _safe_float(f_stat), "p_value": _safe_float(p_val),
            "df_between": df_b,
        }

    return result


# ---------------------------------------------------------------------------
# 3. Teacher tech training vs student proficiency
# ---------------------------------------------------------------------------


def get_teacher_tech_impact(
    serie: str = "9EF",
    disciplina: str = "LP",
    tech_variable: str = "TX_Q029",
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Analyze teacher tech training/usage impact on student proficiency.

    Joins TS_PROFESSOR with TS_ALUNO via ID_TURMA.
    """
    if tech_variable not in PROFESSOR_TECH_VARS:
        raise ValueError(
            f"Variable '{tech_variable}' not recognized. "
            f"Valid: {list(PROFESSOR_TECH_VARS.keys())}"
        )

    var_info = PROFESSOR_TECH_VARS[tech_variable]
    prof_col, weight_col = _resolve_cols(disciplina)
    aluno_path = _aluno_parquet(serie)

    con = duckdb.connect()
    query = f"""
        WITH teacher_tech AS (
            SELECT ID_TURMA, {tech_variable} AS tech_resp
            FROM '{_PROFESSOR_PARQUET}'
            WHERE ID_UF = ?
              AND {tech_variable} IS NOT NULL
              AND {tech_variable} NOT IN ('*', '.', '')
              AND IN_PREENCHIMENTO_QUESTIONARIO = 1
        ),
        student_prof AS (
            SELECT ID_TURMA, {prof_col} AS prof, {weight_col} AS peso
            FROM '{aluno_path}'
            WHERE ID_UF = ?
              AND {prof_col} IS NOT NULL
              AND {weight_col} IS NOT NULL
        )
        SELECT tt.tech_resp, sp.prof, sp.peso
        FROM student_prof sp
        INNER JOIN teacher_tech tt ON sp.ID_TURMA = tt.ID_TURMA
    """
    df = con.execute(query, [uf, uf]).fetchnumpy()
    con.close()

    if len(df.get("tech_resp", [])) == 0:
        return {"variable": tech_variable, "label": var_info["label"], "groups": [], "test": None}

    tech = np.asarray(df["tech_resp"], dtype=str)
    prof = np.asarray(df["prof"], dtype=np.float64)
    peso = np.asarray(df["peso"], dtype=np.float64)

    responses = var_info["responses"]
    groups: List[Dict[str, Any]] = []
    for code in sorted(responses.keys()):
        mask = tech == code
        stats = _group_stats_from_arrays(prof, peso, mask, responses[code])
        stats["code"] = code
        groups.append(stats)

    f_stat, p_val, df_b = weighted_anova_oneway(prof, peso, tech)
    result: Dict[str, Any] = {
        "variable": tech_variable,
        "label": var_info["label"],
        "serie": serie,
        "disciplina": disciplina,
        "groups": groups,
        "test": {
            "type": "anova",
            "f_stat": _safe_float(f_stat),
            "p_value": _safe_float(p_val),
            "df_between": df_b,
        },
    }
    return result


# ---------------------------------------------------------------------------
# 4. Composite digital access index
# ---------------------------------------------------------------------------


def get_digital_access_index(
    serie: str = "9EF",
    disciplina: str = "LP",
    uf: int = ID_UF_RJ,
    stratify_inse: bool = False,
) -> Dict[str, Any]:
    """Compute composite digital access index and its correlation with proficiency.

    Index = Q12b(0-3) + Q12g(0-3) + Q13a(0-1) + Q13b(0-1) = 0 to 8.
    Bands: Baixo(0-2), Medio(3-5), Alto(6-8).
    """
    path = _aluno_parquet(serie)
    prof_col, weight_col = _resolve_cols(disciplina)

    con = duckdb.connect()
    query = f"""
        SELECT
            {prof_col} AS prof,
            {weight_col} AS peso,
            TX_RESP_Q12b, TX_RESP_Q12g, TX_RESP_Q13a, TX_RESP_Q13b,
            NU_TIPO_NIVEL_INSE AS nivel_inse
        FROM '{path}'
        WHERE ID_UF = ?
          AND {prof_col} IS NOT NULL AND {weight_col} IS NOT NULL
          AND TX_RESP_Q12b IS NOT NULL AND TX_RESP_Q12b NOT IN ('*', '.', '')
          AND TX_RESP_Q12g IS NOT NULL AND TX_RESP_Q12g NOT IN ('*', '.', '')
          AND TX_RESP_Q13a IS NOT NULL AND TX_RESP_Q13a NOT IN ('*', '.', '')
          AND TX_RESP_Q13b IS NOT NULL AND TX_RESP_Q13b NOT IN ('*', '.', '')
    """
    df = con.execute(query, [uf]).fetchnumpy()
    con.close()

    if len(df.get("prof", [])) == 0:
        return {"serie": serie, "disciplina": disciplina, "faixas": [], "correlation": None}

    prof = np.asarray(df["prof"], dtype=np.float64)
    peso = np.asarray(df["peso"], dtype=np.float64)
    inse = np.asarray(df["nivel_inse"], dtype=np.float64)

    q12b_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    q12g_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    q13a_map = {"A": 0, "B": 1}
    q13b_map = {"A": 0, "B": 1}

    index = np.array([
        q12b_map.get(str(a), 0) + q12g_map.get(str(b), 0) +
        q13a_map.get(str(c), 0) + q13b_map.get(str(d), 0)
        for a, b, c, d in zip(
            df["TX_RESP_Q12b"], df["TX_RESP_Q12g"],
            df["TX_RESP_Q13a"], df["TX_RESP_Q13b"],
        )
    ], dtype=np.float64)

    # Correlation
    r, p_r = pearson_weighted(index, prof, peso)
    correlation = {"pearson_r": _safe_float(r), "p_value": _safe_float(p_r), "n": len(prof)}

    # Means by band
    band_labels = {"Baixo": (0, 2), "Médio": (3, 5), "Alto": (6, 8)}
    faixas: List[Dict[str, Any]] = []
    for band_name, (lo, hi) in band_labels.items():
        mask = (index >= lo) & (index <= hi)
        stats = _group_stats_from_arrays(prof, peso, mask, band_name)
        stats["range"] = f"{lo}-{hi}"
        faixas.append(stats)

    # Means by individual index level
    by_level: List[Dict[str, Any]] = []
    for lvl in range(9):
        mask = index == lvl
        if mask.any():
            m = weighted_mean(prof[mask], peso[mask])
            by_level.append({"index": lvl, "mean": _safe_float(m), "n": int(mask.sum())})

    result: Dict[str, Any] = {
        "serie": serie,
        "disciplina": disciplina,
        "faixas": faixas,
        "by_level": by_level,
        "correlation": correlation,
    }

    if stratify_inse:
        by_inse: List[Dict[str, Any]] = []
        valid_inse = ~np.isnan(inse)
        if valid_inse.any():
            inse_levels = sorted(set(int(x) for x in inse[valid_inse]))
            for inse_lvl in inse_levels:
                mask_inse = (inse == inse_lvl) & valid_inse
                if mask_inse.sum() < 10:
                    continue
                r_i, p_i = pearson_weighted(
                    index[mask_inse], prof[mask_inse], peso[mask_inse]
                )
                inse_faixas = []
                for band_name, (lo, hi) in band_labels.items():
                    band_mask = mask_inse & (index >= lo) & (index <= hi)
                    stats = _group_stats_from_arrays(prof, peso, band_mask, band_name)
                    inse_faixas.append(stats)
                by_inse.append({
                    "inse_level": inse_lvl,
                    "correlation": {"pearson_r": _safe_float(r_i), "p_value": _safe_float(p_i)},
                    "faixas": inse_faixas,
                    "n": int(mask_inse.sum()),
                })
        result["by_inse"] = by_inse

    return result


# ---------------------------------------------------------------------------
# 5. Summary of all cross-analyses
# ---------------------------------------------------------------------------


def get_cross_summary(
    serie: str = "9EF",
    disciplina: str = "LP",
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return summary of all cross-analyses for one serie/disciplina.

    For each technology variable, returns the gap, effect size, significance.
    Ranked by absolute effect size.
    """
    analyses: List[Dict[str, Any]] = []

    # Student-level variables
    for var_name, var_info in STUDENT_TECH_VARS.items():
        try:
            result = get_student_tech_gap(serie, disciplina, var_name, uf)
            overall = result.get("overall", {})
            test = overall.get("test")
            entry: Dict[str, Any] = {
                "level": "aluno",
                "variable": var_name,
                "label": var_info["label"],
                "type": var_info["type"],
            }
            if test:
                entry["p_value"] = test.get("p_value")
                if var_info["type"] == "binary":
                    entry["gap"] = test.get("gap")
                    entry["cohens_d"] = test.get("cohens_d")
                    entry["test_type"] = "t-test"
                else:
                    entry["f_stat"] = test.get("f_stat")
                    entry["trend_r"] = test.get("trend_r")
                    entry["test_type"] = "anova"
                # Collect group means for context
                groups = overall.get("groups", [])
                if groups:
                    entry["group_means"] = {
                        g["code"]: g["mean"] for g in groups if g.get("mean") is not None
                    }
            analyses.append(entry)
        except Exception:
            continue

    # Director-level variables
    for var_name, var_info in DIRECTOR_TECH_VARS.items():
        try:
            result = get_director_tech_gap(var_name, serie, disciplina, uf)
            test = result.get("test")
            entry = {
                "level": "diretor",
                "variable": var_name,
                "label": var_info["label"],
                "type": var_info["type"],
            }
            if test:
                entry["p_value"] = test.get("p_value")
                if var_info["type"] == "binary":
                    entry["gap"] = test.get("gap")
                    entry["cohens_d"] = test.get("cohens_d")
                    entry["test_type"] = "t-test"
                else:
                    entry["f_stat"] = test.get("f_stat")
                    entry["test_type"] = "anova"
                groups = result.get("groups", [])
                if groups:
                    entry["group_means"] = {
                        g["code"]: g["mean"] for g in groups if g.get("mean") is not None
                    }
            analyses.append(entry)
        except Exception:
            continue

    # Professor-level variables
    for var_name, var_info in PROFESSOR_TECH_VARS.items():
        try:
            result = get_teacher_tech_impact(serie, disciplina, var_name, uf)
            test = result.get("test")
            entry = {
                "level": "professor",
                "variable": var_name,
                "label": var_info["label"],
                "type": var_info["type"],
            }
            if test:
                entry["p_value"] = test.get("p_value")
                entry["f_stat"] = test.get("f_stat")
                entry["test_type"] = "anova"
                groups = result.get("groups", [])
                if groups:
                    entry["group_means"] = {
                        g["code"]: g["mean"] for g in groups if g.get("mean") is not None
                    }
            analyses.append(entry)
        except Exception:
            continue

    # Sort by absolute effect size (Cohen's d for binary, F for ordinal)
    def sort_key(a: Dict) -> float:
        d = a.get("cohens_d")
        if d is not None:
            return abs(d)
        f = a.get("f_stat")
        if f is not None:
            return f
        return 0.0

    analyses.sort(key=sort_key, reverse=True)

    # Note about multiple comparisons
    n_tests = len(analyses)
    bonferroni_alpha = 0.05 / n_tests if n_tests > 0 else 0.05

    return {
        "serie": serie,
        "disciplina": disciplina,
        "analyses": analyses,
        "n_tests": n_tests,
        "bonferroni_alpha": round(bonferroni_alpha, 6),
        "note": f"Correcao de Bonferroni: alfa ajustado = {bonferroni_alpha:.4f} para {n_tests} testes",
    }
