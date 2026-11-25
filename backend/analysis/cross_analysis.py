"""
Cross-analysis module: Technology access/usage vs student proficiency.

Provides functions to analyze relationships between technology indicators
(from SAEB questionnaires) and student performance, at the student,
school/director, and teacher levels. All analyses support INSE
stratification to control for socioeconomic confounding.
"""

import copy
from functools import lru_cache
from typing import Any, Dict, List, Optional

import duckdb
import numpy as np

from backend.analysis.stats_utils import (
    GroupMeansResult,
    ci_from_group_means,
    cohens_d_weighted,
    confidence_interval_mean,
    design_ttest,
    linearized_group_means,
    pearson_weighted,
    to_float,
    to_str,
    ttest_from_group_means,
    wald_anova_from_group_means,
    weighted_anova_oneway,
    weighted_eta_squared,
    weighted_ttest,
)
from backend.config import (
    ID_UF_RJ,
    PROFICIENCY_COLS,
    SAEB_PARQUET_DIR,
    WEIGHT_COLS,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Series whose student Parquets include tech questionnaire items & INSE columns
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
        "positive_code": "B",
        "numeric_map": {"A": 0, "B": 1},
    },
    "TX_RESP_Q13b": {
        "label": "Rede Wi-Fi em casa",
        "responses": {"A": "Não", "B": "Sim"},
        "type": "binary",
        "positive_code": "B",
        "numeric_map": {"A": 0, "B": 1},
    },
}

# Director technology questions.
# Labels follow the official SAEB 2023 dictionary
# (data/processed/saeb_questionnaire_dict.json, sheet TS_DIRETOR).
_DIRECTOR_RESOURCE_SCALE = {
    "A": "Não tem", "B": "Muito inadequado", "C": "Inadequado",
    "D": "Adequado", "E": "Muito adequado",
}

DIRECTOR_TECH_VARS: Dict[str, Dict[str, Any]] = {
    "TX_Q034": {
        "label": "Computadores na escola",
        "responses": dict(_DIRECTOR_RESOURCE_SCALE),
        "type": "ordinal",
    },
    "TX_Q035": {
        "label": "Softwares educacionais",
        "responses": dict(_DIRECTOR_RESOURCE_SCALE),
        "type": "ordinal",
    },
    "TX_Q036": {
        "label": "Internet banda larga",
        "responses": dict(_DIRECTOR_RESOURCE_SCALE),
        "type": "ordinal",
    },
    "TX_Q194": {
        "label": "Projetos de ciência e tecnologia",
        "responses": {"A": "Não", "B": "Sim"},
        "type": "binary",
        "positive_code": "B",
    },
    "TX_Q219": {
        "label": "Formação da equipe em novas tecnologias",
        "responses": {"A": "Não", "B": "Sim"},
        "type": "binary",
        "positive_code": "B",
    },
}

# Professor technology questions (sheet TS_PROFESSOR of the same dictionary).
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
        "label": "Necessidade de formação em TICs",
        "responses": {
            "A": "Nenhuma necessidade",
            "B": "Pouca necessidade",
            "C": "Moderada necessidade",
            "D": "Muita necessidade",
        },
        "type": "ordinal",
    },
}

# Mapping (serie, disciplina) -> school-level mean column in TS_ESCOLA
SCHOOL_MEDIA_COLS: Dict[tuple, str] = {
    ("5EF", "LP"): "MEDIA_5EF_LP", ("5EF", "MT"): "MEDIA_5EF_MT",
    ("9EF", "LP"): "MEDIA_9EF_LP", ("9EF", "MT"): "MEDIA_9EF_MT",
    ("34EM", "LP"): "MEDIA_EM_LP", ("34EM", "MT"): "MEDIA_EM_MT",
    ("EM", "LP"): "MEDIA_EM_LP", ("EM", "MT"): "MEDIA_EM_MT",
}


def validate_student_params(serie: str, disciplina: str) -> tuple[str, str, str, str, str]:
    """Validate *(serie, disciplina)* against real Parquet columns.

    Returns ``(serie_norm, disc_norm, parquet_path, prof_col, weight_col)`` or
    raises :class:`ValueError` when the series or discipline is unsupported.
    """
    serie_key = serie.strip().upper()
    filename = _SERIE_FILE_MAP.get(serie_key)
    if filename is None:
        raise ValueError(
            f"Serie '{serie}' not recognized. Valid: {list(_SERIE_FILE_MAP.keys())}"
        )
    disc_key = disciplina.strip().upper()
    allowed = _SERIE_DISCIPLINAS[filename]
    prof_col = PROFICIENCY_COLS.get(disc_key)
    weight_col = WEIGHT_COLS.get(disc_key)
    if disc_key not in allowed or prof_col is None or weight_col is None:
        raise ValueError(
            f"Disciplina '{disciplina}' not available for serie '{serie}'. "
            f"Valid: {sorted(allowed)}"
        )
    path = str(SAEB_PARQUET_DIR / f"{filename}.parquet")
    return serie_key, disc_key, path, prof_col, weight_col


def _serie_filter_sql(serie_key: str) -> tuple[str, list[int]]:
    """Return optional SQL ``AND ID_SERIE = ?`` clause for 3EM (12) vs 4EM (13)."""
    id_serie = _SERIE_ID_MAP.get(serie_key)
    if id_serie is not None:
        return " AND ID_SERIE = ?", [id_serie]
    return "", []


def _se_from_group_means(res: GroupMeansResult, index: int) -> Optional[float]:
    """Extract standard error for group *index* in *res*, or None if unestimable."""
    var = float(res["cov"][index, index])
    if res["df"] < 1 or np.isnan(var) or res["n_clusters"][index] < 2:
        return None
    return float(np.sqrt(max(var, 0.0)))


def _safe_float(val: Optional[float]) -> Optional[float]:
    if val is None or np.isnan(val):
        return None
    return float(val)


class Design:
    """Identificadores do desenho amostral alinhados às observações.

    ``clusters`` = escola (ID_ESCOLA, unidade primária de amostragem do SAEB)
    e ``strata`` = ESTRATO, para **todas** as observações da UF/série. Os
    subgrupos são estimados como domínios (máscaras), sem recortar o desenho.
    Com ``clusters=None`` as funções usam fórmulas de amostragem aleatória
    simples (ex.: análises com a escola como unidade).
    """

    def __init__(self, clusters: Optional[np.ndarray] = None, strata: Optional[np.ndarray] = None):
        self.clusters = clusters
        self.strata = strata


_SRS = Design()

# Descrição do método de inferência, devolvida junto com os testes
DESIGN_NOTE = (
    "Erros-padrão por linearização de Taylor considerando o desenho do SAEB "
    "(estratos e conglomerados por escola), com subgrupos estimados como domínios; "
    "gl = nº de escolas − nº de estratos."
)


def _student_design(df: Dict[str, np.ndarray]) -> Design:
    return Design(np.asarray(df["escola"]), np.asarray(df["estrato"]))


def _all_true(n: int) -> np.ndarray:
    return np.ones(n, dtype=bool)


def _group_stats_from_arrays(
    prof: np.ndarray, peso: np.ndarray, mask: np.ndarray, label: str,
    design: Design = _SRS,
) -> Dict[str, Any]:
    """Média, EP e IC 95% do subgrupo ``mask`` (domínio, se houver desenho)."""
    if not mask.any():
        return {
            "label": label, "mean": None, "se": None,
            "ci_low": None, "ci_high": None, "ci_lower": None, "ci_upper": None, "n": 0,
        }
    if design.clusters is None:
        mean, ci_lo, ci_hi = confidence_interval_mean(prof[mask], peso[mask])
        n_eff = int(np.count_nonzero(~np.isnan(prof[mask]) & ~np.isnan(peso[mask])))
        se: Optional[float] = None
        if n_eff >= 2 and not np.isnan(ci_lo) and not np.isnan(ci_hi):
            from scipy import stats as sps
            t_crit = float(sps.t.ppf(0.975, max(n_eff - 1, 1)))
            se = (ci_hi - ci_lo) / (2.0 * t_crit) if t_crit > 0 else None
    else:
        mean, ci_lo, ci_hi = confidence_interval_mean(
            prof, peso, strata=design.strata, clusters=design.clusters, domain=mask
        )
        se = None
    lo_f, hi_f = _safe_float(ci_lo), _safe_float(ci_hi)
    return {
        "label": label,
        "mean": _safe_float(mean),
        "se": _safe_float(se),
        "ci_low": lo_f,
        "ci_high": hi_f,
        "ci_lower": lo_f,
        "ci_upper": hi_f,
        "n": int(mask.sum()),
    }


def _binary_test(
    values: np.ndarray,
    weights: np.ndarray,
    codes: np.ndarray,
    var_info: Dict[str, Any],
    design: Design = _SRS,
    domain: Optional[np.ndarray] = None,
) -> Optional[Dict[str, Any]]:
    """t-test + Cohen's d for a binary variable, oriented as presence − absence.

    ``var_info["positive_code"]`` identifies the "Sim" answer, so a positive
    gap/d always means that having the resource is associated with a
    higher mean, regardless of how the questionnaire codes the answers.
    """
    resp_codes = sorted(var_info["responses"].keys())
    if len(resp_codes) != 2:
        return None
    dom = _all_true(len(values)) if domain is None else domain
    pos = var_info.get("positive_code", resp_codes[1])
    neg = resp_codes[0] if resp_codes[1] == pos else resp_codes[1]
    m_pos = dom & (codes == pos)
    m_neg = dom & (codes == neg)
    if not (m_pos.any() and m_neg.any()):
        return None
    if design.clusters is None:
        t_stat, p_val, diff = weighted_ttest(
            values[m_pos], weights[m_pos], values[m_neg], weights[m_neg]
        )
    else:
        res = design_ttest(
            values, weights, codes, pos, neg, design.clusters, design.strata, domain=dom
        )
        t_stat, p_val, diff = res["t"], res["p"], res["diff"]
    d = cohens_d_weighted(values[m_pos], weights[m_pos], values[m_neg], weights[m_neg])
    return {
        "type": "t-test",
        "t_stat": _safe_float(t_stat),
        "p_value": _safe_float(p_val),
        "gap": _safe_float(diff),
        "cohens_d": _safe_float(d),
        "comparison": f"{var_info['responses'][pos]} − {var_info['responses'][neg]}",
    }


def _anova_test(
    values: np.ndarray, weights: np.ndarray, codes: np.ndarray,
    design: Design = _SRS, domain: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Weighted one-way ANOVA (design-based Wald F with clusters) plus eta²."""
    dom = _all_true(len(values)) if domain is None else domain
    f_stat, p_val, df_b = weighted_anova_oneway(
        values, weights, codes,
        clusters=design.clusters, strata=design.strata, domain=dom,
    )
    return {
        "type": "anova",
        "f_stat": _safe_float(f_stat),
        "p_value": _safe_float(p_val),
        "df_between": df_b,
        "eta_squared": _safe_float(weighted_eta_squared(values[dom], weights[dom], codes[dom])),
    }


def _map_codes(codes: np.ndarray, mapping: Dict[str, float]) -> np.ndarray:
    """Converte códigos de resposta em números (NaN se fora do mapeamento)."""
    out = np.full(len(codes), np.nan, dtype=np.float64)
    for code, val in mapping.items():
        out[codes == code] = val
    return out


# ---------------------------------------------------------------------------
# 1. Student technology access vs proficiency
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _student_tech_gap_cached(
    serie_key: str,
    disc_key: str,
    tech_variable: str,
    uf: int,
    stratify_inse: bool,
) -> Dict[str, Any]:
    var_info = STUDENT_TECH_VARS[tech_variable]
    _, _, path, prof_col, weight_col = validate_student_params(serie_key, disc_key)
    serie_clause, serie_params = _serie_filter_sql(serie_key)

    con = duckdb.connect()
    try:
        query = f"""
            SELECT
                {prof_col} AS prof,
                {weight_col} AS peso,
                {tech_variable} AS tech_resp,
                CASE WHEN IN_INSE = 1 THEN NU_TIPO_NIVEL_INSE END AS nivel_inse,  -- IN_INSE = 0 vem codificado como nível 1
                ID_ESCOLA AS escola,
                ESTRATO AS estrato
            FROM '{path}'
            WHERE ID_UF = ?{serie_clause}
        """
        df = con.execute(query, [uf, *serie_params]).fetchnumpy()
    finally:
        con.close()

    prof = to_float(df["prof"])
    peso = to_float(df["peso"])
    tech = to_str(df["tech_resp"])
    inse = to_float(df["nivel_inse"])
    responses = var_info["responses"]
    valid = ~np.isnan(prof) & ~np.isnan(peso) & np.isin(tech, list(responses))

    if not valid.any():
        return {
            "variable": tech_variable,
            "label": var_info["label"],
            "serie": serie_key,
            "disciplina": disc_key,
            "groups": [],
            "test": None,
            "correlation": None,
            "overall": {"groups": [], "inse_level": None, "test": None, "correlation": None},
        }

    design = _student_design(df)
    num_map = var_info.get("numeric_map", {})
    numeric_vals = _map_codes(tech, num_map) if num_map else None

    def _analyze_domain(domain: np.ndarray, inse_level: Optional[int] = None) -> Dict[str, Any]:
        # Single joint linearization per domain (reused for all group CIs + t/Wald F)
        res = linearized_group_means(
            prof, peso, tech, design.clusters, design.strata, domain=domain
        )
        level_idx = {str(lev): i for i, lev in enumerate(res["levels"])}
        total_w = float(peso[domain].sum())

        groups: List[Dict[str, Any]] = []
        for code in sorted(responses.keys()):
            grp_mask = domain & (tech == code)
            grp_w = float(peso[grp_mask].sum()) if grp_mask.any() else 0.0
            wpct = round(100.0 * grp_w / total_w, 2) if total_w > 0 else 0.0
            if code in level_idx:
                j = level_idx[code]
                mean, ci_lo, ci_hi = ci_from_group_means(res, j)
                se = _se_from_group_means(res, j)
                lo_f, hi_f = _safe_float(ci_lo), _safe_float(ci_hi)
                stats: Dict[str, Any] = {
                    "code": code,
                    "label": responses[code],
                    "mean": _safe_float(mean),
                    "se": _safe_float(se),
                    "ci_low": lo_f,
                    "ci_high": hi_f,
                    "ci_lower": lo_f,
                    "ci_upper": hi_f,
                    "n": int(res["n"][j]),
                    "weighted_pct": wpct,
                }
            else:
                stats = {
                    "code": code,
                    "label": responses[code],
                    "mean": None,
                    "se": None,
                    "ci_low": None,
                    "ci_high": None,
                    "ci_lower": None,
                    "ci_upper": None,
                    "n": 0,
                    "weighted_pct": 0.0,
                }
            groups.append(stats)

        dom_result: Dict[str, Any] = {"groups": groups, "inse_level": inse_level}

        corr_dict: Optional[Dict[str, Any]] = None
        if numeric_vals is not None:
            trend_dom = domain & ~np.isnan(numeric_vals)
            if trend_dom.sum() >= 3:
                r, p_r = pearson_weighted(
                    numeric_vals, prof, peso,
                    clusters=design.clusters, strata=design.strata, domain=trend_dom,
                )
                corr_dict = {
                    "pearson_r": _safe_float(r),
                    "p_value": _safe_float(p_r),
                    "n": int(trend_dom.sum()),
                }
        dom_result["correlation"] = corr_dict

        if var_info["type"] == "binary":
            resp_codes = sorted(responses.keys())
            if len(resp_codes) == 2:
                pos = var_info.get("positive_code", resp_codes[1])
                neg = resp_codes[0] if resp_codes[1] == pos else resp_codes[1]
                if pos in level_idx and neg in level_idx:
                    t_res = ttest_from_group_means(res, level_idx[pos], level_idx[neg])
                    m_pos = domain & (tech == pos)
                    m_neg = domain & (tech == neg)
                    d = cohens_d_weighted(prof[m_pos], peso[m_pos], prof[m_neg], peso[m_neg])
                    dom_result["test"] = {
                        "type": "t-test",
                        "t_stat": _safe_float(t_res["t"]),
                        "p_value": _safe_float(t_res["p"]),
                        "gap": _safe_float(t_res["diff"]),
                        "se": _safe_float(t_res["se"]),
                        "df": _safe_float(t_res["df"]),
                        "cohens_d": _safe_float(d),
                        "comparison": f"{responses[pos]} − {responses[neg]}",
                    }
        else:
            # Ordinal: ANOVA + linear trend
            f_stat, p_val, df_b = wald_anova_from_group_means(res)
            test_dict: Dict[str, Any] = {
                "type": "anova",
                "f_stat": _safe_float(f_stat),
                "p_value": _safe_float(p_val),
                "df_between": df_b,
                "df": int(res["df"]),
                "eta_squared": _safe_float(
                    weighted_eta_squared(prof[domain], peso[domain], tech[domain])
                ),
            }
            if corr_dict is not None:
                test_dict["trend_r"] = corr_dict["pearson_r"]
                test_dict["trend_p"] = corr_dict["p_value"]
            dom_result["test"] = test_dict

        return dom_result

    overall = _analyze_domain(valid)
    result: Dict[str, Any] = {
        "variable": tech_variable,
        "label": var_info["label"],
        "serie": serie_key,
        "disciplina": disc_key,
        "groups": copy.deepcopy(overall["groups"]),
        "test": copy.deepcopy(overall.get("test")),
        "correlation": copy.deepcopy(overall.get("correlation")),
        "overall": overall,
        "inference": DESIGN_NOTE,
    }

    # INSE-stratified analysis (níveis = domínios)
    if stratify_inse:
        by_inse: List[Dict[str, Any]] = []
        has_inse = valid & ~np.isnan(inse)
        for lvl in sorted(set(int(x) for x in inse[has_inse])):
            dom_lvl = has_inse & (inse == lvl)
            if dom_lvl.sum() < 10:
                continue
            by_inse.append(_analyze_domain(dom_lvl, inse_level=lvl))
        result["by_inse"] = by_inse

    return result


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
    All students of the UF/series form the design; answer groups and INSE
    levels are domains.
    """
    if tech_variable not in STUDENT_TECH_VARS:
        raise ValueError(
            f"Variable '{tech_variable}' not recognized. "
            f"Valid: {list(STUDENT_TECH_VARS.keys())}"
        )
    serie_key, disc_key, *_ = validate_student_params(serie, disciplina)
    return copy.deepcopy(
        _student_tech_gap_cached(serie_key, disc_key, tech_variable, int(uf), bool(stratify_inse))
    )


# ---------------------------------------------------------------------------
# 2. Director-reported school tech vs proficiency
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _director_tech_gap_cached(
    tech_variable: str,
    serie_key: str,
    disc_key: str,
    uf: int,
) -> Dict[str, Any]:
    var_info = DIRECTOR_TECH_VARS[tech_variable]
    media_col = SCHOOL_MEDIA_COLS[(serie_key, disc_key)]

    con = duckdb.connect()
    try:
        query = f"""
            WITH dir AS (
                SELECT ID_ESCOLA, MIN({tech_variable}) AS tech_resp
                FROM '{_DIRETOR_PARQUET}'
                WHERE ID_UF = ?
                  AND {tech_variable} IS NOT NULL
                  AND {tech_variable} NOT IN ('*', '.', '')
                  AND IN_PREENCHIMENTO_QUESTIONARIO = 1
                GROUP BY ID_ESCOLA
            )
            SELECT
                d.tech_resp,
                TRY_CAST(e.{media_col} AS DOUBLE) AS media_prof,
                e.IN_PUBLICA AS rede
            FROM dir d
            INNER JOIN '{_ESCOLA_PARQUET}' e ON d.ID_ESCOLA = e.ID_ESCOLA
            WHERE e.{media_col} IS NOT NULL
        """
        df = con.execute(query, [uf]).fetchnumpy()
    finally:
        con.close()

    if len(df.get("tech_resp", [])) == 0:
        return {"variable": tech_variable, "label": var_info["label"], "groups": [], "test": None}

    tech = np.asarray(df["tech_resp"], dtype=str)
    media = to_float(df["media_prof"])
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
        "serie": serie_key,
        "disciplina": disc_key,
        "groups": groups,
        "inference": "Escola como unidade de análise (médias escolares do INEP, sem pesos); "
                     "testes sob amostragem aleatória simples de escolas.",
    }

    if var_info["type"] == "binary":
        test = _binary_test(media, weights, tech, var_info)
        if test:
            result["test"] = test
    else:
        result["test"] = _anova_test(media, weights, tech)

    return result


def get_director_tech_gap(
    tech_variable: str = "TX_Q194",
    serie: str = "9EF",
    disciplina: str = "LP",
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Compare school proficiency by director-reported technology availability.

    Joins TS_DIRETOR with TS_ESCOLA via ID_ESCOLA using MEDIA_* columns.
    TS_DIRETOR has one row per school *and* assessed series (same answers
    replicated), so it is first reduced to one row per school — otherwise
    schools offering several series would be counted more than once.
    """
    if tech_variable not in DIRECTOR_TECH_VARS:
        raise ValueError(
            f"Variable '{tech_variable}' not recognized. "
            f"Valid: {list(DIRECTOR_TECH_VARS.keys())}"
        )

    serie_key = serie.strip().upper()
    disc_key = disciplina.strip().upper()
    if (serie_key, disc_key) not in SCHOOL_MEDIA_COLS:
        raise ValueError(f"No MEDIA column for serie={serie}, disciplina={disciplina}")

    return copy.deepcopy(_director_tech_gap_cached(tech_variable, serie_key, disc_key, int(uf)))


# ---------------------------------------------------------------------------
# 3. Teacher tech training vs student proficiency
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _teacher_tech_impact_cached(
    serie_key: str,
    disc_key: str,
    tech_variable: str,
    uf: int,
) -> Dict[str, Any]:
    var_info = PROFESSOR_TECH_VARS[tech_variable]
    _, _, aluno_path, prof_col, weight_col = validate_student_params(serie_key, disc_key)
    serie_clause, serie_params = _serie_filter_sql(serie_key)

    con = duckdb.connect()
    try:
        query = f"""
            WITH teacher_tech AS (
                SELECT ID_TURMA, ID_PROFESSOR, MIN({tech_variable}) AS tech_resp
                FROM '{_PROFESSOR_PARQUET}'
                WHERE ID_UF = ?
                  AND {tech_variable} IS NOT NULL
                  AND {tech_variable} NOT IN ('*', '.', '')
                  AND IN_PREENCHIMENTO_QUESTIONARIO = 1
                GROUP BY ID_TURMA, ID_PROFESSOR
            ),
            teachers_per_class AS (
                SELECT ID_TURMA, COUNT(*) AS n_prof
                FROM teacher_tech
                GROUP BY ID_TURMA
            ),
            student_prof AS (
                SELECT ID_TURMA, ID_ALUNO, ID_ESCOLA, ESTRATO,
                       {prof_col} AS prof, {weight_col} AS peso
                FROM '{aluno_path}'
                WHERE ID_UF = ?{serie_clause}
            )
            SELECT tt.tech_resp, sp.prof, sp.peso / COALESCE(k.n_prof, 1) AS peso,
                   sp.ID_ALUNO AS aluno, sp.ID_ESCOLA AS escola, sp.ESTRATO AS estrato
            FROM student_prof sp
            LEFT JOIN teacher_tech tt ON sp.ID_TURMA = tt.ID_TURMA
            LEFT JOIN teachers_per_class k ON sp.ID_TURMA = k.ID_TURMA
        """
        df = con.execute(query, [uf, uf, *serie_params]).fetchnumpy()
    finally:
        con.close()

    tech = to_str(df["tech_resp"])
    prof = to_float(df["prof"])
    peso = to_float(df["peso"])
    aluno = np.asarray(df["aluno"])
    responses = var_info["responses"]
    valid = ~np.isnan(prof) & ~np.isnan(peso) & np.isin(tech, list(responses))

    if not valid.any():
        return {"variable": tech_variable, "label": var_info["label"], "groups": [], "test": None}

    # Conglomerado = escola: os pares de um mesmo aluno (vários professores)
    # ficam no mesmo conglomerado, o que corrige a dependência entre eles.
    design = _student_design(df)
    res = linearized_group_means(
        prof, peso, tech, design.clusters, design.strata, domain=valid
    )
    level_idx = {str(lev): i for i, lev in enumerate(res["levels"])}

    groups: List[Dict[str, Any]] = []
    for code in sorted(responses.keys()):
        mask = valid & (tech == code)
        if code in level_idx:
            j = level_idx[code]
            mean, ci_lo, ci_hi = ci_from_group_means(res, j)
            se = _se_from_group_means(res, j)
            lo_f, hi_f = _safe_float(ci_lo), _safe_float(ci_hi)
            stats: Dict[str, Any] = {
                "label": responses[code],
                "mean": _safe_float(mean),
                "se": _safe_float(se),
                "ci_low": lo_f,
                "ci_high": hi_f,
                "ci_lower": lo_f,
                "ci_upper": hi_f,
                "n": int(len(np.unique(aluno[mask]))) if mask.any() else 0,
                "code": code,
            }
        else:
            stats = {
                "label": responses[code],
                "mean": None,
                "se": None,
                "ci_low": None,
                "ci_high": None,
                "ci_lower": None,
                "ci_upper": None,
                "n": 0,
                "code": code,
            }
        groups.append(stats)

    f_stat, p_val, df_b = wald_anova_from_group_means(res)
    test_result: Dict[str, Any] = {
        "type": "anova",
        "f_stat": _safe_float(f_stat),
        "p_value": _safe_float(p_val),
        "df_between": df_b,
        "df": int(res["df"]),
        "eta_squared": _safe_float(
            weighted_eta_squared(prof[valid], peso[valid], tech[valid])
        ),
    }

    return {
        "variable": tech_variable,
        "label": var_info["label"],
        "serie": serie_key,
        "disciplina": disc_key,
        "groups": groups,
        "test": test_result,
        "unit": "par aluno-professor",
        "inference": DESIGN_NOTE,
    }


def get_teacher_tech_impact(
    serie: str = "9EF",
    disciplina: str = "LP",
    tech_variable: str = "TX_Q029",
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Analyze teacher tech training/needs vs student proficiency.

    Joins TS_PROFESSOR with TS_ALUNO via ID_TURMA. TS_PROFESSOR has no
    discipline indicator, so in classes with more than one responding
    teacher (typically LP and MT in 9EF/EM) each student is paired with
    every teacher: the unit of analysis is the student–teacher pair. To keep
    each student's total influence equal to their sampling weight, the
    weight of each pair is divided by the number of responding teachers of
    the class, and group ``n`` counts distinct students. Students without a
    responding teacher stay in the design (domain estimation).
    """
    if tech_variable not in PROFESSOR_TECH_VARS:
        raise ValueError(
            f"Variable '{tech_variable}' not recognized. "
            f"Valid: {list(PROFESSOR_TECH_VARS.keys())}"
        )
    serie_key, disc_key, *_ = validate_student_params(serie, disciplina)
    return copy.deepcopy(_teacher_tech_impact_cached(serie_key, disc_key, tech_variable, int(uf)))


# ---------------------------------------------------------------------------
# 4. Composite digital access index
# ---------------------------------------------------------------------------

_INDEX_MAPS: Dict[str, Dict[str, float]] = {
    "TX_RESP_Q12b": {"A": 0, "B": 1, "C": 2, "D": 3},
    "TX_RESP_Q12g": {"A": 0, "B": 1, "C": 2, "D": 3},
    "TX_RESP_Q13a": {"A": 0, "B": 1},
    "TX_RESP_Q13b": {"A": 0, "B": 1},
}
_INDEX_BANDS = {"Baixo": (0, 2), "Médio": (3, 5), "Alto": (6, 8)}


@lru_cache(maxsize=32)
def _digital_access_index_cached(
    serie_key: str,
    disc_key: str,
    uf: int,
    stratify_inse: bool,
) -> Dict[str, Any]:
    _, _, path, prof_col, weight_col = validate_student_params(serie_key, disc_key)
    serie_clause, serie_params = _serie_filter_sql(serie_key)

    con = duckdb.connect()
    try:
        query = f"""
            SELECT
                {prof_col} AS prof,
                {weight_col} AS peso,
                TX_RESP_Q12b, TX_RESP_Q12g, TX_RESP_Q13a, TX_RESP_Q13b,
                CASE WHEN IN_INSE = 1 THEN NU_TIPO_NIVEL_INSE END AS nivel_inse,  -- IN_INSE = 0 vem codificado como nível 1
                ID_ESCOLA AS escola,
                ESTRATO AS estrato
            FROM '{path}'
            WHERE ID_UF = ?{serie_clause}
        """
        df = con.execute(query, [uf, *serie_params]).fetchnumpy()
    finally:
        con.close()

    prof = to_float(df["prof"])
    peso = to_float(df["peso"])
    inse = to_float(df["nivel_inse"])
    index = np.zeros(len(prof), dtype=np.float64)
    for col, mapping in _INDEX_MAPS.items():
        index = index + _map_codes(to_str(df[col]), mapping)
    valid = ~np.isnan(prof) & ~np.isnan(peso) & ~np.isnan(index)

    if not valid.any():
        return {
            "serie": serie_key,
            "disciplina": disc_key,
            "faixas": [],
            "by_level": [],
            "correlation": None,
            "anova": None,
            "test": None,
        }

    design = _student_design(df)
    band_codes = np.where(index <= 2, 0, np.where(index <= 5, 1, 2))
    band_items = list(_INDEX_BANDS.items())
    band_ascii_codes = {"Baixo": "Baixo", "Médio": "Medio", "Alto": "Alto"}

    def _band_stats(domain: np.ndarray, include_range: bool) -> List[Dict[str, Any]]:
        res = linearized_group_means(
            prof, peso, band_codes, design.clusters, design.strata, domain=domain
        )
        level_idx = {int(lev): i for i, lev in enumerate(res["levels"])}
        out: List[Dict[str, Any]] = []
        for b_code, (band_name, (lo, hi)) in enumerate(band_items):
            code_str = band_ascii_codes[band_name]
            if b_code in level_idx:
                j = level_idx[b_code]
                mean, ci_lo, ci_hi = ci_from_group_means(res, j)
                se = _se_from_group_means(res, j)
                lo_f, hi_f = _safe_float(ci_lo), _safe_float(ci_hi)
                entry: Dict[str, Any] = {
                    "code": code_str,
                    "label": band_name,
                    "mean": _safe_float(mean),
                    "se": _safe_float(se),
                    "ci_low": lo_f,
                    "ci_high": hi_f,
                    "ci_lower": lo_f,
                    "ci_upper": hi_f,
                    "n": int(res["n"][j]),
                }
            else:
                entry = {
                    "code": code_str,
                    "label": band_name,
                    "mean": None,
                    "se": None,
                    "ci_low": None,
                    "ci_high": None,
                    "ci_lower": None,
                    "ci_upper": None,
                    "n": 0,
                }
            if include_range:
                entry["range"] = f"{lo}-{hi}"
            out.append(entry)
        return out

    # Correlation
    r, p_r = pearson_weighted(
        index, prof, peso, clusters=design.clusters, strata=design.strata, domain=valid
    )
    correlation = {"pearson_r": _safe_float(r), "p_value": _safe_float(p_r), "n": int(valid.sum())}

    # Means by band
    faixas = _band_stats(valid, include_range=True)

    # Means, design-based SE/CI and Wald ANOVA across individual index levels 0..8
    index_int = np.where(valid, index, -1).astype(int)
    res_lvl = linearized_group_means(
        prof, peso, index_int, design.clusters, design.strata, domain=valid
    )
    lvl_idx = {int(lev): i for i, lev in enumerate(res_lvl["levels"])}
    by_level: List[Dict[str, Any]] = []
    for lvl in range(9):
        if lvl in lvl_idx:
            j = lvl_idx[lvl]
            mean, ci_lo, ci_hi = ci_from_group_means(res_lvl, j)
            se = _se_from_group_means(res_lvl, j)
            lo_f, hi_f = _safe_float(ci_lo), _safe_float(ci_hi)
            by_level.append({
                "index": lvl,
                "mean": _safe_float(mean),
                "se": _safe_float(se),
                "ci_low": lo_f,
                "ci_high": hi_f,
                "ci_lower": lo_f,
                "ci_upper": hi_f,
                "n": int(res_lvl["n"][j]),
            })

    f_stat, p_val, df_b = wald_anova_from_group_means(res_lvl)
    anova_result: Dict[str, Any] = {
        "type": "anova",
        "f_stat": _safe_float(f_stat),
        "p_value": _safe_float(p_val),
        "df_between": df_b,
        "df": int(res_lvl["df"]),
        "eta_squared": _safe_float(
            weighted_eta_squared(prof[valid], peso[valid], index_int[valid])
        ),
    }

    result: Dict[str, Any] = {
        "serie": serie_key,
        "disciplina": disc_key,
        "faixas": faixas,
        "by_level": by_level,
        "correlation": correlation,
        "anova": anova_result,
        "test": copy.deepcopy(anova_result),
        "inference": DESIGN_NOTE,
    }

    if stratify_inse:
        by_inse: List[Dict[str, Any]] = []
        has_inse = valid & ~np.isnan(inse)
        for inse_lvl in sorted(set(int(x) for x in inse[has_inse])):
            mask_inse = has_inse & (inse == inse_lvl)
            if mask_inse.sum() < 10:
                continue
            r_i, p_i = pearson_weighted(
                index, prof, peso,
                clusters=design.clusters, strata=design.strata, domain=mask_inse,
            )
            by_inse.append({
                "inse_level": inse_lvl,
                "correlation": {"pearson_r": _safe_float(r_i), "p_value": _safe_float(p_i)},
                "faixas": _band_stats(mask_inse, include_range=False),
                "n": int(mask_inse.sum()),
            })
        result["by_inse"] = by_inse

    return result


def get_digital_access_index(
    serie: str = "9EF",
    disciplina: str = "LP",
    uf: int = ID_UF_RJ,
    stratify_inse: bool = False,
) -> Dict[str, Any]:
    """Compute composite digital access index and its correlation with proficiency.

    Index = Q12b(0-3) + Q12g(0-3) + Q13a(0-1) + Q13b(0-1) = 0 to 8 (only for
    students who answered all four items). Bands: Baixo(0-2), Médio(3-5),
    Alto(6-8).
    """
    serie_key, disc_key, *_ = validate_student_params(serie, disciplina)
    return copy.deepcopy(
        _digital_access_index_cached(serie_key, disc_key, int(uf), bool(stratify_inse))
    )


# ---------------------------------------------------------------------------
# 5. Summary of all cross-analyses
# ---------------------------------------------------------------------------


def _d_equivalent(entry: Dict[str, Any]) -> float:
    """Effect magnitude on Cohen's d scale, comparable across test types.

    Binary variables use |d| directly; ANOVA results are converted from
    eta² to Cohen's f = sqrt(eta² / (1 − eta²)) and then to d ≈ 2f (the
    exact equivalence for two groups, Cohen 1988).
    """
    d = entry.get("cohens_d")
    if d is not None:
        return abs(d)
    eta2 = entry.get("eta_squared")
    if eta2 is not None and 0 <= eta2 < 1:
        return 2.0 * float(np.sqrt(eta2 / (1.0 - eta2)))
    return 0.0


def _summary_entry(
    level: str, var_name: str, var_info: Dict[str, Any],
    test: Optional[Dict[str, Any]], groups: List[Dict[str, Any]],
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "level": level,
        "variable": var_name,
        "label": var_info["label"],
        "type": var_info["type"],
    }
    if test:
        entry["p_value"] = test.get("p_value")
        entry["test_type"] = test.get("type")
        if test.get("type") == "t-test":
            entry["gap"] = test.get("gap")
            entry["cohens_d"] = test.get("cohens_d")
        else:
            entry["f_stat"] = test.get("f_stat")
            entry["eta_squared"] = test.get("eta_squared")
            if "trend_r" in test:
                entry["trend_r"] = test.get("trend_r")
        if groups:
            entry["group_means"] = {
                g["code"]: g["mean"] for g in groups if g.get("mean") is not None
            }
    entry["effect_size_d"] = _d_equivalent(entry)
    return entry


@lru_cache(maxsize=16)
def _cross_summary_cached(
    serie_key: str,
    disc_key: str,
    uf: int,
) -> Dict[str, Any]:
    analyses: List[Dict[str, Any]] = []

    # Student-level variables
    for var_name, var_info in STUDENT_TECH_VARS.items():
        result = _student_tech_gap_cached(serie_key, disc_key, var_name, uf, False)
        overall = result.get("overall", {})
        analyses.append(_summary_entry(
            "aluno", var_name, var_info, overall.get("test"), overall.get("groups", [])
        ))

    # Director-level variables (only where TS_ESCOLA has MEDIA_* columns)
    if (serie_key, disc_key) in SCHOOL_MEDIA_COLS:
        for var_name, var_info in DIRECTOR_TECH_VARS.items():
            result = _director_tech_gap_cached(var_name, serie_key, disc_key, uf)
            analyses.append(_summary_entry(
                "diretor", var_name, var_info, result.get("test"), result.get("groups", [])
            ))

    # Professor-level variables
    for var_name, var_info in PROFESSOR_TECH_VARS.items():
        result = _teacher_tech_impact_cached(serie_key, disc_key, var_name, uf)
        analyses.append(_summary_entry(
            "professor", var_name, var_info, result.get("test"), result.get("groups", [])
        ))

    analyses.sort(key=_d_equivalent, reverse=True)

    # Bonferroni: only analyses that actually produced a p-value count as tests
    n_tests = sum(1 for a in analyses if a.get("p_value") is not None)
    bonferroni_alpha = 0.05 / n_tests if n_tests > 0 else 0.05

    return {
        "serie": serie_key,
        "disciplina": disc_key,
        "analyses": analyses,
        "n_tests": n_tests,
        "bonferroni_alpha": round(bonferroni_alpha, 6),
        "note": (
            f"Correção de Bonferroni: α ajustado = {bonferroni_alpha:.4f} para {n_tests} testes. "
            "Efeitos ordenados em escala comum (|d| ou equivalente-d do η²). "
            "p-valores de aluno e professor com erros-padrão de desenho (estratos e "
            "conglomerados por escola); de escola, com cada escola como observação."
        ),
    }


def get_cross_summary(
    serie: str = "9EF",
    disciplina: str = "LP",
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return summary of all cross-analyses for one serie/disciplina.

    For each technology variable, returns the gap, effect size, significance.
    Ranked by effect magnitude on a common scale (|d|, or the d-equivalent
    of the ANOVA eta²) — never by raw F, which grows with sample size.
    """
    serie_key, disc_key, *_ = validate_student_params(serie, disciplina)
    return copy.deepcopy(_cross_summary_cached(serie_key, disc_key, int(uf)))
