"""
Equity analysis module for the SAEB/TIC education dashboard.

Provides gap analyses across school networks (public/private),
socioeconomic levels (INSE), and geographic locations (urban/rural,
capital/interior).
"""

from typing import Any, Dict, List, Optional

import duckdb
import numpy as np

from backend.analysis.stats_utils import (
    cohens_d_weighted,
    confidence_interval_mean,
    pearson_weighted,
    weighted_mean,
    weighted_std,
    weighted_ttest,
)
from backend.config import (
    ID_UF_RJ,
    PROFICIENCY_COLS,
    SAEB_PARQUET_DIR,
    WEIGHT_COLS,
)

# Maps serie identifier to the parquet file suffix.
_SERIE_FILE_MAP: Dict[str, str] = {
    "2EF": "TS_ALUNO_2EF",
    "5EF": "TS_ALUNO_5EF",
    "9EF": "TS_ALUNO_9EF",
    "EM": "TS_ALUNO_34EM",
    "3EM": "TS_ALUNO_34EM",
    "4EM": "TS_ALUNO_34EM",
    "34EM": "TS_ALUNO_34EM",
}


def _parquet_path(serie: str) -> str:
    """Return the full parquet file path for a given serie."""
    key = serie.upper()
    filename = _SERIE_FILE_MAP.get(key)
    if filename is None:
        raise ValueError(
            f"Serie '{serie}' not recognized. Valid: {list(_SERIE_FILE_MAP.keys())}"
        )
    return str(SAEB_PARQUET_DIR / f"{filename}.parquet")


def _resolve_cols(disciplina: str) -> tuple[str, str]:
    """Return (proficiency_col, weight_col) for a discipline key."""
    disc = disciplina.upper()
    prof_col = PROFICIENCY_COLS.get(disc)
    weight_col = WEIGHT_COLS.get(disc)
    if prof_col is None or weight_col is None:
        raise ValueError(
            f"Disciplina '{disciplina}' not recognized. Valid: {list(PROFICIENCY_COLS.keys())}"
        )
    return prof_col, weight_col


def _group_stats(
    values: np.ndarray,
    weights: np.ndarray,
    mask: np.ndarray,
    label: str,
) -> Dict[str, Any]:
    """Compute summary statistics for a boolean-masked subgroup."""
    if not mask.any():
        return {
            "label": label,
            "mean": None,
            "ci_lower": None,
            "ci_upper": None,
            "std": None,
            "n": 0,
        }
    v, w = values[mask], weights[mask]
    mean, ci_lo, ci_hi = confidence_interval_mean(v, w)
    sd = weighted_std(v, w)
    return {
        "label": label,
        "mean": float(mean),
        "ci_lower": float(ci_lo),
        "ci_upper": float(ci_hi),
        "std": float(sd) if not np.isnan(sd) else None,
        "n": int(mask.sum()),
    }


# ------------------------------------------------------------------ #
#  Public / Private gap
# ------------------------------------------------------------------ #


def get_public_private_gap(
    serie: str,
    disciplina: str,
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return gap analysis between public and private schools.

    Returns
    -------
    dict with keys: publica, privada (stats dicts), gap, ci_gap_lower,
    ci_gap_upper, t_stat, p_value, cohens_d.
    """
    path = _parquet_path(serie)
    prof_col, weight_col = _resolve_cols(disciplina)

    con = duckdb.connect()
    query = f"""
        SELECT
            {prof_col} AS prof,
            {weight_col} AS peso,
            IN_PUBLICA
        FROM '{path}'
        WHERE ID_UF = ?
          AND {prof_col} IS NOT NULL
          AND {weight_col} IS NOT NULL
          AND IN_PUBLICA IS NOT NULL
    """
    df = con.execute(query, [uf]).fetchnumpy()
    con.close()

    prof = np.asarray(df["prof"], dtype=np.float64)
    peso = np.asarray(df["peso"], dtype=np.float64)
    in_pub = np.asarray(df["IN_PUBLICA"])

    mask_pub = in_pub == 1
    mask_priv = in_pub == 0

    pub_stats = _group_stats(prof, peso, mask_pub, "publica")
    priv_stats = _group_stats(prof, peso, mask_priv, "privada")

    result: Dict[str, Any] = {
        "publica": pub_stats,
        "privada": priv_stats,
    }

    if mask_pub.any() and mask_priv.any():
        t_stat, p_value, diff = weighted_ttest(
            prof[mask_priv], peso[mask_priv],
            prof[mask_pub], peso[mask_pub],
        )
        d = cohens_d_weighted(
            prof[mask_priv], peso[mask_priv],
            prof[mask_pub], peso[mask_pub],
        )
        result["gap"] = float(diff) if not np.isnan(diff) else None
        result["t_stat"] = float(t_stat) if not np.isnan(t_stat) else None
        result["p_value"] = float(p_value) if not np.isnan(p_value) else None
        result["cohens_d"] = float(d) if not np.isnan(d) else None
    else:
        result["gap"] = None
        result["t_stat"] = None
        result["p_value"] = None
        result["cohens_d"] = None

    return result


# ------------------------------------------------------------------ #
#  INSE correlation
# ------------------------------------------------------------------ #


def get_inse_correlation(
    serie: str,
    disciplina: str,
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return INSE vs proficiency analysis: Pearson r, p-value, means by INSE level.

    Uses INSE_ALUNO (continuous) for correlation and NU_TIPO_NIVEL_INSE
    (categorical 1-8) for group means.

    Returns
    -------
    dict with keys: pearson_r, p_value, n, means_by_level (list of dicts).
    """
    path = _parquet_path(serie)
    prof_col, weight_col = _resolve_cols(disciplina)

    con = duckdb.connect()
    # Use PESO_ALUNO_INSE for INSE-related analyses when available;
    # fall back to the discipline weight for proficiency stats.
    query = f"""
        SELECT
            {prof_col} AS prof,
            {weight_col} AS peso,
            INSE_ALUNO,
            NU_TIPO_NIVEL_INSE AS nivel_inse,
            PESO_ALUNO_INSE AS peso_inse
        FROM '{path}'
        WHERE ID_UF = ?
          AND {prof_col} IS NOT NULL
          AND {weight_col} IS NOT NULL
    """
    df = con.execute(query, [uf]).fetchnumpy()
    con.close()

    prof = np.asarray(df["prof"], dtype=np.float64)
    peso = np.asarray(df["peso"], dtype=np.float64)
    inse = np.asarray(df["INSE_ALUNO"], dtype=np.float64)
    nivel = np.asarray(df["nivel_inse"], dtype=np.float64)

    result: Dict[str, Any] = {}

    # Pearson correlation on continuous INSE
    valid = ~np.isnan(inse) & ~np.isnan(prof) & ~np.isnan(peso)
    if valid.sum() >= 3:
        r, p = pearson_weighted(inse[valid], prof[valid], peso[valid])
        result["pearson_r"] = float(r) if not np.isnan(r) else None
        result["p_value"] = float(p) if not np.isnan(p) else None
        result["n"] = int(valid.sum())
    else:
        result["pearson_r"] = None
        result["p_value"] = None
        result["n"] = 0

    # Means by INSE level (1-8)
    means_by_level: List[Dict[str, Any]] = []
    valid_nivel = ~np.isnan(nivel)
    if valid_nivel.any():
        levels = sorted(set(int(x) for x in nivel[valid_nivel] if not np.isnan(x)))
        for lvl in levels:
            mask = (nivel == lvl) & ~np.isnan(prof) & ~np.isnan(peso)
            if mask.any():
                mean_val, ci_lo, ci_hi = confidence_interval_mean(
                    prof[mask], peso[mask]
                )
                means_by_level.append({
                    "nivel_inse": lvl,
                    "mean": float(mean_val),
                    "ci_lower": float(ci_lo),
                    "ci_upper": float(ci_hi),
                    "n": int(mask.sum()),
                })
            else:
                means_by_level.append({
                    "nivel_inse": lvl,
                    "mean": None,
                    "ci_lower": None,
                    "ci_upper": None,
                    "n": 0,
                })

    result["means_by_level"] = means_by_level
    return result


# ------------------------------------------------------------------ #
#  Urban / Rural  and  Capital / Interior gaps
# ------------------------------------------------------------------ #


def get_location_gap(
    serie: str,
    disciplina: str,
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Return urban/rural and capital/interior proficiency gaps.

    SAEB coding:
    - ID_LOCALIZACAO: 1 = Urbana, 2 = Rural
    - ID_AREA: 1 = Capital, 2 = Interior

    Returns
    -------
    dict with keys:
      urban_rural: {urbana, rural, gap, t_stat, p_value, cohens_d}
      capital_interior: {capital, interior, gap, t_stat, p_value, cohens_d}
    """
    path = _parquet_path(serie)
    prof_col, weight_col = _resolve_cols(disciplina)

    con = duckdb.connect()
    query = f"""
        SELECT
            {prof_col} AS prof,
            {weight_col} AS peso,
            ID_LOCALIZACAO,
            ID_AREA
        FROM '{path}'
        WHERE ID_UF = ?
          AND {prof_col} IS NOT NULL
          AND {weight_col} IS NOT NULL
    """
    df = con.execute(query, [uf]).fetchnumpy()
    con.close()

    prof = np.asarray(df["prof"], dtype=np.float64)
    peso = np.asarray(df["peso"], dtype=np.float64)
    loc = np.asarray(df["ID_LOCALIZACAO"])
    area = np.asarray(df["ID_AREA"])

    result: Dict[str, Any] = {}

    # --- Urban vs Rural ---
    mask_urban = loc == 1
    mask_rural = loc == 2

    urban_stats = _group_stats(prof, peso, mask_urban, "urbana")
    rural_stats = _group_stats(prof, peso, mask_rural, "rural")

    ur: Dict[str, Any] = {"urbana": urban_stats, "rural": rural_stats}

    if mask_urban.any() and mask_rural.any():
        t_stat, p_value, diff = weighted_ttest(
            prof[mask_urban], peso[mask_urban],
            prof[mask_rural], peso[mask_rural],
        )
        d = cohens_d_weighted(
            prof[mask_urban], peso[mask_urban],
            prof[mask_rural], peso[mask_rural],
        )
        ur["gap"] = float(diff) if not np.isnan(diff) else None
        ur["t_stat"] = float(t_stat) if not np.isnan(t_stat) else None
        ur["p_value"] = float(p_value) if not np.isnan(p_value) else None
        ur["cohens_d"] = float(d) if not np.isnan(d) else None
    else:
        ur["gap"] = None
        ur["t_stat"] = None
        ur["p_value"] = None
        ur["cohens_d"] = None

    result["urban_rural"] = ur

    # --- Capital vs Interior ---
    mask_cap = area == 1
    mask_int = area == 2

    cap_stats = _group_stats(prof, peso, mask_cap, "capital")
    int_stats = _group_stats(prof, peso, mask_int, "interior")

    ci: Dict[str, Any] = {"capital": cap_stats, "interior": int_stats}

    if mask_cap.any() and mask_int.any():
        t_stat, p_value, diff = weighted_ttest(
            prof[mask_cap], peso[mask_cap],
            prof[mask_int], peso[mask_int],
        )
        d = cohens_d_weighted(
            prof[mask_cap], peso[mask_cap],
            prof[mask_int], peso[mask_int],
        )
        ci["gap"] = float(diff) if not np.isnan(diff) else None
        ci["t_stat"] = float(t_stat) if not np.isnan(t_stat) else None
        ci["p_value"] = float(p_value) if not np.isnan(p_value) else None
        ci["cohens_d"] = float(d) if not np.isnan(d) else None
    else:
        ci["gap"] = None
        ci["t_stat"] = None
        ci["p_value"] = None
        ci["cohens_d"] = None

    result["capital_interior"] = ci

    return result
