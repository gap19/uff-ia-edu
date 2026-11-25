"""
Equity analysis module for the SAEB/TIC education dashboard.

Provides gap analyses across school networks (public/private),
socioeconomic levels (INSE), and geographic locations (urban/rural,
capital/interior).

Inference uses the SAEB design (strata ``ESTRATO`` and school clusters
``ID_ESCOLA``) for all students of the UF/series; each subgroup is a domain
(see ``backend.analysis.stats_utils``).
"""

from typing import Any, Dict, List, Optional

import duckdb
import numpy as np
from scipy import stats as sps

from backend.analysis.stats_utils import (
    cohens_d_weighted,
    confidence_interval_mean,
    design_ttest,
    pearson_weighted,
    to_float,
    weighted_std,
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


def _sf(value: Any) -> Optional[float]:
    """float JSON-seguro: NaN/None -> None."""
    if value is None:
        return None
    value = float(value)
    return None if np.isnan(value) else value


def _load(serie: str, disciplina: str, uf: int, extra_cols: str) -> Dict[str, np.ndarray]:
    """Todos os alunos da UF/série (o desenho completo), com colunas extras."""
    path = _parquet_path(serie)
    prof_col, weight_col = _resolve_cols(disciplina)
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT
            {prof_col} AS prof,
            {weight_col} AS peso,
            {extra_cols},
            ID_ESCOLA AS escola,
            ESTRATO AS estrato
        FROM '{path}'
        WHERE ID_UF = ?
    """, [uf]).fetchnumpy()
    con.close()
    return df


class _Design:
    """Valores, pesos e desenho (clusters/strata) de todos os alunos."""

    def __init__(self, df: Dict[str, np.ndarray]):
        self.prof = to_float(df["prof"])
        self.peso = to_float(df["peso"])
        self.clusters = np.asarray(df["escola"])
        self.strata = np.asarray(df["estrato"])
        self.valid = ~np.isnan(self.prof) & ~np.isnan(self.peso)

    def group_stats(self, mask: np.ndarray, label: str) -> Dict[str, Any]:
        """Média, IC 95% de desenho (domínio) e DP de um subgrupo."""
        mask = mask & self.valid
        if not mask.any():
            return {"label": label, "mean": None, "ci_lower": None, "ci_upper": None,
                    "std": None, "n": 0}
        mean, ci_lo, ci_hi = confidence_interval_mean(
            self.prof, self.peso, strata=self.strata, clusters=self.clusters, domain=mask
        )
        return {
            "label": label,
            "mean": _sf(mean),
            "ci_lower": _sf(ci_lo),
            "ci_upper": _sf(ci_hi),
            "std": _sf(weighted_std(self.prof[mask], self.peso[mask])),
            "n": int(mask.sum()),
        }

    def gap_test(self, m1: np.ndarray, m2: np.ndarray, alpha: float = 0.05) -> Dict[str, Any]:
        """Diferença m1 − m2 com t de desenho, IC (t com gl de desenho) e d de Cohen."""
        m1, m2 = m1 & self.valid, m2 & self.valid
        if not (m1.any() and m2.any()):
            return {"gap": None, "ci_gap_lower": None, "ci_gap_upper": None,
                    "t_stat": None, "p_value": None, "df": None, "cohens_d": None}
        labels = np.where(m1, 1, np.where(m2, 2, 0))
        res = design_ttest(self.prof, self.peso, labels, 1, 2, self.clusters, self.strata,
                           domain=m1 | m2)
        ci_lo = ci_hi = None
        if not np.isnan(res["se"]) and res["df"] >= 1:
            half = sps.t.ppf(1 - alpha / 2, res["df"]) * res["se"]
            ci_lo, ci_hi = res["diff"] - half, res["diff"] + half
        d = cohens_d_weighted(self.prof[m1], self.peso[m1], self.prof[m2], self.peso[m2])
        return {
            "gap": _sf(res["diff"]),
            "ci_gap_lower": _sf(ci_lo),
            "ci_gap_upper": _sf(ci_hi),
            "t_stat": _sf(res["t"]),
            "p_value": _sf(res["p"]),
            "df": _sf(res["df"]),
            "cohens_d": _sf(d),
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
    dict with keys: publica, privada (stats dicts), gap (privada − pública),
    ci_gap_lower, ci_gap_upper, t_stat, p_value, df, cohens_d.
    """
    df = _load(serie, disciplina, uf, "IN_PUBLICA")
    d = _Design(df)
    in_pub = to_float(df["IN_PUBLICA"])
    mask_pub, mask_priv = in_pub == 1, in_pub == 0

    result: Dict[str, Any] = {
        "publica": d.group_stats(mask_pub, "publica"),
        "privada": d.group_stats(mask_priv, "privada"),
    }
    result.update(d.gap_test(mask_priv, mask_pub))
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
    (categorical 1-8) for group means — only for students with IN_INSE = 1
    (students without INSE come coded as level 1 in the microdata).

    Returns
    -------
    dict with keys: pearson_r, p_value, n, means_by_level (list of dicts).
    """
    df = _load(serie, disciplina, uf, """
        CASE WHEN IN_INSE = 1 THEN INSE_ALUNO END AS inse,
        CASE WHEN IN_INSE = 1 THEN NU_TIPO_NIVEL_INSE END AS nivel_inse
    """)
    d = _Design(df)
    inse = to_float(df["inse"])
    nivel = to_float(df["nivel_inse"])

    result: Dict[str, Any] = {}
    has_inse = d.valid & ~np.isnan(inse)
    if has_inse.sum() >= 3:
        r, p = pearson_weighted(
            inse, d.prof, d.peso, clusters=d.clusters, strata=d.strata, domain=has_inse
        )
        result.update(pearson_r=_sf(r), p_value=_sf(p), n=int(has_inse.sum()))
    else:
        result.update(pearson_r=None, p_value=None, n=0)

    means_by_level: List[Dict[str, Any]] = []
    has_level = d.valid & ~np.isnan(nivel)
    for lvl in sorted(set(int(x) for x in nivel[has_level])):
        stats = d.group_stats(nivel == lvl, f"nivel_{lvl}")
        means_by_level.append({
            "nivel_inse": lvl,
            "mean": stats["mean"],
            "ci_lower": stats["ci_lower"],
            "ci_upper": stats["ci_upper"],
            "n": stats["n"],
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
      urban_rural: {urbana, rural, gap, ci_gap_*, t_stat, p_value, df, cohens_d}
      capital_interior: {capital, interior, gap, ci_gap_*, t_stat, p_value, df, cohens_d}
    """
    df = _load(serie, disciplina, uf, "ID_LOCALIZACAO, ID_AREA")
    d = _Design(df)
    loc = to_float(df["ID_LOCALIZACAO"])
    area = to_float(df["ID_AREA"])

    mask_urban, mask_rural = loc == 1, loc == 2
    ur: Dict[str, Any] = {
        "urbana": d.group_stats(mask_urban, "urbana"),
        "rural": d.group_stats(mask_rural, "rural"),
    }
    ur.update(d.gap_test(mask_urban, mask_rural))

    mask_cap, mask_int = area == 1, area == 2
    ci: Dict[str, Any] = {
        "capital": d.group_stats(mask_cap, "capital"),
        "interior": d.group_stats(mask_int, "interior"),
    }
    ci.update(d.gap_test(mask_cap, mask_int))

    return {"urban_rural": ur, "capital_interior": ci}
