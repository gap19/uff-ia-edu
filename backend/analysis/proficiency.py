"""
Proficiency analysis module for the SAEB/TIC education dashboard.

Provides high-level functions for proficiency distribution, regional
comparisons, and public/private breakdowns using pre-computed parquet files.
"""

from typing import Any, Dict, List, Optional

import duckdb
import numpy as np

from backend.analysis.stats_utils import (
    cohens_d_weighted,
    confidence_interval_mean,
    weighted_mean,
    weighted_std,
)
from backend.config import (
    ID_REGIAO_SUDESTE,
    ID_UF_RJ,
    PROFICIENCY_COLS,
    SAEB_PARQUET_DIR,
    WEIGHT_COLS,
)

# Maps serie identifier to the parquet file suffix.
# SAEB 2023 uses TS_ALUNO_34EM for both 3EM and 4EM series.
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
            f"Serie '{serie}' not recognized. Valid options: {list(_SERIE_FILE_MAP.keys())}"
        )
    return str(SAEB_PARQUET_DIR / f"{filename}.parquet")


def _resolve_cols(disciplina: str) -> tuple[str, str]:
    """Return (proficiency_col, weight_col) for a discipline key like 'LP' or 'MT'."""
    disc = disciplina.upper()
    prof_col = PROFICIENCY_COLS.get(disc)
    weight_col = WEIGHT_COLS.get(disc)
    if prof_col is None or weight_col is None:
        raise ValueError(
            f"Disciplina '{disciplina}' not recognized. Valid options: {list(PROFICIENCY_COLS.keys())}"
        )
    return prof_col, weight_col


def get_proficiency_distribution(
    serie: str,
    disciplina: str,
    uf: int = ID_UF_RJ,
    n_bins: int = 30,
) -> Dict[str, Any]:
    """Return proficiency distribution data (histogram bins) for a UF.

    Parameters
    ----------
    serie : str
        E.g. '5EF', '9EF', 'EM'.
    disciplina : str
        'LP', 'MT', 'CH', or 'CN'.
    uf : int
        IBGE UF code (default 33 = RJ).
    n_bins : int
        Number of histogram bins.

    Returns
    -------
    dict with keys: bins_edges, counts, bin_centers, mean, std, n, median, q25, q75
    """
    path = _parquet_path(serie)
    prof_col, weight_col = _resolve_cols(disciplina)

    con = duckdb.connect()
    query = f"""
        SELECT {prof_col} AS prof, {weight_col} AS peso
        FROM '{path}'
        WHERE ID_UF = ? AND {prof_col} IS NOT NULL AND {weight_col} IS NOT NULL
    """
    df = con.execute(query, [uf]).fetchnumpy()
    con.close()

    values = np.asarray(df["prof"], dtype=np.float64)
    weights = np.asarray(df["peso"], dtype=np.float64)

    if len(values) == 0:
        return {
            "bin_edges": [],
            "counts": [],
            "bin_centers": [],
            "mean": None,
            "std": None,
            "n": 0,
            "median": None,
            "q25": None,
            "q75": None,
        }

    # Weighted histogram
    counts, bin_edges = np.histogram(values, bins=n_bins, weights=weights)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    mu = weighted_mean(values, weights)
    sd = weighted_std(values, weights)

    # Weighted percentiles via sorted cumulative weights
    order = np.argsort(values)
    sorted_vals = values[order]
    sorted_w = weights[order]
    cum_w = np.cumsum(sorted_w)
    cum_pct = (cum_w - 0.5 * sorted_w) / cum_w[-1]

    median = float(np.interp(0.5, cum_pct, sorted_vals))
    q25 = float(np.interp(0.25, cum_pct, sorted_vals))
    q75 = float(np.interp(0.75, cum_pct, sorted_vals))

    return {
        "bin_edges": bin_edges.tolist(),
        "counts": counts.tolist(),
        "bin_centers": bin_centers.tolist(),
        "mean": float(mu),
        "std": float(sd),
        "n": int(len(values)),
        "median": median,
        "q25": q25,
        "q75": q75,
    }


def get_proficiency_comparison_rj_brasil(
    serie: str,
    disciplina: str,
) -> Dict[str, Any]:
    """Compare RJ, Sudeste, and Brasil proficiency means with CIs.

    Returns
    -------
    dict with keys for each scope (rj, sudeste, brasil), each containing
    mean, ci_lower, ci_upper, n.
    """
    path = _parquet_path(serie)
    prof_col, weight_col = _resolve_cols(disciplina)

    con = duckdb.connect()
    query = f"""
        SELECT
            {prof_col} AS prof,
            {weight_col} AS peso,
            ID_UF,
            ID_REGIAO
        FROM '{path}'
        WHERE {prof_col} IS NOT NULL AND {weight_col} IS NOT NULL
    """
    df = con.execute(query).fetchnumpy()
    con.close()

    prof = np.asarray(df["prof"], dtype=np.float64)
    peso = np.asarray(df["peso"], dtype=np.float64)
    id_uf = np.asarray(df["ID_UF"])
    id_regiao = np.asarray(df["ID_REGIAO"])

    result: Dict[str, Any] = {}

    # RJ
    mask_rj = id_uf == ID_UF_RJ
    if mask_rj.any():
        mean_rj, ci_lo, ci_hi = confidence_interval_mean(prof[mask_rj], peso[mask_rj])
        result["rj"] = {
            "mean": float(mean_rj),
            "ci_lower": float(ci_lo),
            "ci_upper": float(ci_hi),
            "n": int(mask_rj.sum()),
        }
    else:
        result["rj"] = {"mean": None, "ci_lower": None, "ci_upper": None, "n": 0}

    # Sudeste
    mask_se = id_regiao == ID_REGIAO_SUDESTE
    if mask_se.any():
        mean_se, ci_lo, ci_hi = confidence_interval_mean(prof[mask_se], peso[mask_se])
        result["sudeste"] = {
            "mean": float(mean_se),
            "ci_lower": float(ci_lo),
            "ci_upper": float(ci_hi),
            "n": int(mask_se.sum()),
        }
    else:
        result["sudeste"] = {"mean": None, "ci_lower": None, "ci_upper": None, "n": 0}

    # Brasil
    if len(prof) > 0:
        mean_br, ci_lo, ci_hi = confidence_interval_mean(prof, peso)
        result["brasil"] = {
            "mean": float(mean_br),
            "ci_lower": float(ci_lo),
            "ci_upper": float(ci_hi),
            "n": int(len(prof)),
        }
    else:
        result["brasil"] = {"mean": None, "ci_lower": None, "ci_upper": None, "n": 0}

    return result


def get_proficiency_by_rede(
    serie: str,
    disciplina: str,
    uf: int = ID_UF_RJ,
) -> Dict[str, Any]:
    """Compare public vs private school proficiency with CI and Cohen's d.

    Parameters
    ----------
    serie : str
        E.g. '5EF', '9EF'.
    disciplina : str
        'LP', 'MT', 'CH', or 'CN'.
    uf : int
        IBGE UF code (default 33 = RJ).

    Returns
    -------
    dict with keys: publica, privada (each with mean, ci_lower, ci_upper, n),
    gap, cohens_d.
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
    in_publica = np.asarray(df["IN_PUBLICA"])

    mask_pub = in_publica == 1
    mask_priv = in_publica == 0

    result: Dict[str, Any] = {}

    # Publica
    if mask_pub.any():
        mean_pub, ci_lo, ci_hi = confidence_interval_mean(prof[mask_pub], peso[mask_pub])
        result["publica"] = {
            "mean": float(mean_pub),
            "ci_lower": float(ci_lo),
            "ci_upper": float(ci_hi),
            "n": int(mask_pub.sum()),
        }
    else:
        result["publica"] = {"mean": None, "ci_lower": None, "ci_upper": None, "n": 0}

    # Privada
    if mask_priv.any():
        mean_priv, ci_lo, ci_hi = confidence_interval_mean(prof[mask_priv], peso[mask_priv])
        result["privada"] = {
            "mean": float(mean_priv),
            "ci_lower": float(ci_lo),
            "ci_upper": float(ci_hi),
            "n": int(mask_priv.sum()),
        }
    else:
        result["privada"] = {"mean": None, "ci_lower": None, "ci_upper": None, "n": 0}

    # Gap and effect size
    if mask_pub.any() and mask_priv.any():
        gap = (result["privada"]["mean"] or 0) - (result["publica"]["mean"] or 0)
        d = cohens_d_weighted(
            prof[mask_priv], peso[mask_priv],
            prof[mask_pub], peso[mask_pub],
        )
        result["gap"] = float(gap)
        result["cohens_d"] = float(d) if not np.isnan(d) else None
    else:
        result["gap"] = None
        result["cohens_d"] = None

    return result
