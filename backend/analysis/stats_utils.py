"""
Weighted statistical functions for analyzing SAEB 2023 survey data.

Provides numerically stable implementations of common statistics
that account for survey weights, stratification, and design effects.

Design-based inference
----------------------
When ``clusters`` (primary sampling units — schools, ``ID_ESCOLA``) and
optionally ``strata`` (``ESTRATO``) are given, standard errors are computed
by Taylor linearization with the with-replacement ("ultimate cluster")
variance estimator used by Stata ``svy`` and R ``survey``::

    Var(θ) = Σ_h n_h/(n_h − 1) · Σ_{g∈h} (T_hg − T̄_h)²

where T_hg is the cluster total of the influence values of θ. Degrees of
freedom are (#clusters − #strata). Strata with a single cluster are centred
on the grand mean (R ``survey.lonely.psu = "adjust"``, conservative).

Subgroups (Wi-Fi yes/no, an INSE level, public/private...) are estimated as
**domains**: the design arrays always cover the whole sample (e.g. every
student of the UF and series) and observations outside the domain — or with
missing values — enter with zero influence instead of being dropped. Cutting
the sample down to the subgroup would drop clusters with no members and
understate the variance. Without ``clusters`` the functions keep their
simple-random-sampling formulas.
"""

from typing import Dict, List, Optional, Tuple, TypedDict, Union

import numpy as np
from numpy.typing import ArrayLike
from scipy import stats


class GroupMeansResult(TypedDict):
    """Typed return structure of :func:`linearized_group_means`."""

    levels: np.ndarray
    means: np.ndarray
    cov: np.ndarray
    df: int
    n: np.ndarray
    n_clusters: np.ndarray


def to_float(column: ArrayLike) -> np.ndarray:
    """Converte uma coluna (ex.: de ``DuckDB.fetchnumpy``) em float64 com NaN.

    ``fetchnumpy`` devolve colunas com NULL como ``numpy.ma.MaskedArray``;
    ``np.asarray`` descartaria a máscara e trocaria os NULL por 0.0.
    """
    return np.ma.filled(np.ma.asarray(column, dtype=np.float64), np.nan)


def to_str(column: ArrayLike) -> np.ndarray:
    """Converte uma coluna de texto (ex.: de ``fetchnumpy``) em ``str``; NULL vira ''."""
    return np.asarray(np.ma.filled(np.ma.asarray(column, dtype=object), ""), dtype=str)


def _clean(
    *arrays: ArrayLike,
) -> Tuple[np.ndarray, ...]:
    """Convert inputs to float64 arrays and drop rows where any array has NaN."""
    arrs = [np.asarray(a, dtype=np.float64) for a in arrays]
    mask = np.ones(len(arrs[0]), dtype=bool)
    for a in arrs:
        mask &= ~np.isnan(a)
    return tuple(a[mask] for a in arrs)


def _valid_weights(weights: np.ndarray) -> bool:
    """Return True when *weights* is non-empty, non-negative and has finite sum > 0."""
    if len(weights) == 0 or np.any(weights < 0):
        return False
    total = float(weights.sum())
    return bool(np.isfinite(total) and total > 0.0)


# ---------- Design-based (Taylor linearization) variance ----------


def _design_masks(*arrays: ArrayLike) -> np.ndarray:
    """Boolean mask of rows where every float-convertible array is non-NaN."""
    arrs = [np.asarray(a, dtype=np.float64) for a in arrays]
    mask = np.ones(len(arrs[0]), dtype=bool)
    for a in arrs:
        mask &= ~np.isnan(a)
    return mask


def _nested_psu_inverse(
    clusters: np.ndarray,
    strata: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """Nest PSUs inside strata as ``(stratum, cluster)`` pairs (R ``nest=TRUE``).

    Returns ``(psu_inv, psu_strata, n_psus)`` using a single ``np.unique`` pass
    over length-n pairs (for non-object arrays), eliminating row-order
    dependence when a school spans multiple strata (e.g. 3ª/4ª EM in SAEB).
    """
    n = len(clusters)
    if strata.dtype == object or clusters.dtype == object:
        _, st_codes = np.unique(strata, return_inverse=True)
        _, cl_codes = np.unique(clusters, return_inverse=True)
        pairs = np.empty(n, dtype=[("s", np.intp), ("c", np.intp)])
        pairs["s"] = st_codes
        pairs["c"] = cl_codes
    else:
        pairs = np.empty(n, dtype=[("s", strata.dtype), ("c", clusters.dtype)])
        pairs["s"] = strata
        pairs["c"] = clusters
    uniq_pairs, psu_inv = np.unique(pairs, return_inverse=True)
    return psu_inv, uniq_pairs["s"], len(uniq_pairs)


def _covariance_from_psus(
    Z: np.ndarray,
    psu_inv: Optional[np.ndarray],
    n_cl: int,
    psu_strata: Optional[np.ndarray],
) -> Tuple[np.ndarray, int]:
    """Compute ultimate-cluster covariance from influence matrix *Z* and PSU codes."""
    n, k = Z.shape
    if n < 2 or n_cl < 2:
        # Com um único conglomerado a variância não é estimável
        return np.full((k, k), np.nan), 0

    if psu_inv is None:
        totals = Z
    else:
        totals = np.zeros((n_cl, k))
        np.add.at(totals, psu_inv, Z)
    grand = totals.mean(axis=0)

    if psu_strata is None:
        centred = totals - grand
        cov = n_cl / (n_cl - 1) * centred.T @ centred
        return cov, n_cl - 1

    _, st_inv = np.unique(psu_strata, return_inverse=True)
    n_st = int(st_inv.max()) + 1
    n_h = np.bincount(st_inv, minlength=n_st).astype(np.float64)
    sums = np.zeros((n_st, k))
    np.add.at(sums, st_inv, totals)
    means = sums / n_h[:, None]

    single = n_h[st_inv] < 2
    centred = totals - means[st_inv]
    centred[single] = totals[single] - grand  # "adjust" for lonely PSUs
    scale = np.where(single, 1.0, n_h[st_inv] / np.maximum(n_h[st_inv] - 1, 1))
    cov = (centred * scale[:, None]).T @ centred
    return cov, max(n_cl - n_st, 1)


def linearized_covariance(
    influence: np.ndarray,
    clusters: Optional[ArrayLike] = None,
    strata: Optional[ArrayLike] = None,
) -> Tuple[np.ndarray, int]:
    """Covariance of estimators from their influence values.

    Parameters
    ----------
    influence : (n, K) array
        Linearized (influence) values of K estimators for n observations.
    clusters, strata : optional arrays of length n
        PSU and stratum identifiers. When both are provided, PSUs are nested
        inside strata as ``(stratum, cluster)`` pairs (equivalent to R
        ``survey(..., nest=TRUE)`` and Stata ``svy``).

    Returns
    -------
    (cov, df) : (K, K) covariance matrix and design degrees of freedom.
    """
    Z = np.atleast_2d(np.asarray(influence, dtype=np.float64))
    if Z.shape[0] == 1 and np.asarray(influence).ndim == 1:
        Z = Z.T
    n, k = Z.shape
    if n < 2:
        return np.full((k, k), np.nan), 0

    if clusters is None:
        st_arr = None if strata is None else np.asarray(strata)
        return _covariance_from_psus(Z, None, n, st_arr)

    cl = np.asarray(clusters)
    if strata is None:
        cl_codes, cl_inv = np.unique(cl, return_inverse=True)
        return _covariance_from_psus(Z, cl_inv, len(cl_codes), None)

    st = np.asarray(strata)
    psu_inv, psu_strata, n_cl = _nested_psu_inverse(cl, st)
    return _covariance_from_psus(Z, psu_inv, n_cl, psu_strata)


def linearized_group_means(
    values: ArrayLike,
    weights: ArrayLike,
    groups: ArrayLike,
    clusters: Optional[ArrayLike] = None,
    strata: Optional[ArrayLike] = None,
    domain: Optional[ArrayLike] = None,
) -> GroupMeansResult:
    """Weighted means of each group with their design-based covariance.

    ``domain`` (boolean) marks the observations that belong to the analysis;
    with ``clusters``, the other observations (and those with missing value
    or weight) stay in the design with zero influence — domain estimation.
    Without ``clusters`` they are simply dropped (SRS).

    Returns a dict with ``levels``, ``means`` (K,), ``cov`` (K, K), ``df``,
    ``n`` (observations per group) and ``n_clusters`` (distinct nested PSUs per
    group — a group in a single PSU has no estimable variance). Groups
    are estimated jointly, so the covariance between groups sharing
    clusters (e.g. students with and without Wi-Fi in the same school) is
    taken into account.
    """
    v = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    g = np.asarray(groups)
    in_dom = _design_masks(v, w)
    if domain is not None:
        in_dom &= np.asarray(domain, dtype=bool)

    psu_inv: Optional[np.ndarray] = None
    psu_strata: Optional[np.ndarray] = None
    n_cl = 0

    if clusters is None:
        # SRS: each observation is its own cluster; out-of-domain rows dropped
        v, w, g = v[in_dom], w[in_dom], g[in_dom]
        psu_strata = None if strata is None else np.asarray(strata)[in_dom]
        n_cl = len(v)
        in_dom = np.ones(len(v), dtype=bool)
    else:
        cl = np.asarray(clusters)
        if strata is None:
            cl_codes, psu_inv = np.unique(cl, return_inverse=True)
            n_cl = len(cl_codes)
        else:
            psu_inv, psu_strata, n_cl = _nested_psu_inverse(cl, np.asarray(strata))

    levels = np.unique(g[in_dom])
    k = len(levels)
    means = np.full(k, np.nan)
    n_obs = np.zeros(k, dtype=int)
    n_clu = np.zeros(k, dtype=int)
    Z = np.zeros((len(v), k))
    for j, lev in enumerate(levels):
        idx = in_dom & (g == lev)
        n_obs[j] = int(idx.sum())
        if psu_inv is None:
            n_clu[j] = n_obs[j]
        elif n_obs[j] > 0:
            n_clu[j] = int(np.count_nonzero(np.bincount(psu_inv[idx], minlength=n_cl)))
        wj = w[idx]
        if not _valid_weights(wj):
            continue
        w_sum = wj.sum()
        means[j] = np.sum(wj * v[idx]) / w_sum
        Z[idx, j] = wj * (v[idx] - means[j]) / w_sum
    cov, df = _covariance_from_psus(Z, psu_inv, n_cl, psu_strata)
    return {
        "levels": levels,
        "means": means,
        "cov": cov,
        "df": df,
        "n": n_obs,
        "n_clusters": n_clu,
    }


def ci_from_group_means(
    res: GroupMeansResult,
    index: int,
    alpha: float = 0.05,
) -> Tuple[float, float, float]:
    """Compute ``(mean, lower, upper)`` for group *index* in *res*."""
    mu = float(res["means"][index])
    var = float(res["cov"][index, index])
    df = res["df"]
    if np.isnan(mu) or df < 1 or np.isnan(var) or res["n_clusters"][index] < 2:
        return (mu, np.nan, np.nan)
    half = float(stats.t.ppf(1 - alpha / 2, df) * np.sqrt(max(var, 0.0)))
    return (mu, mu - half, mu + half)


def ttest_from_group_means(
    res: GroupMeansResult,
    idx_1: int,
    idx_2: int,
) -> Dict[str, float]:
    """Compute design-based t-test for ``means[idx_1] - means[idx_2]`` from *res*."""
    out: Dict[str, float] = {
        "diff": np.nan,
        "se": np.nan,
        "t": np.nan,
        "p": np.nan,
        "df": float(res["df"]),
    }
    m1, m2 = float(res["means"][idx_1]), float(res["means"][idx_2])
    if np.isnan(m1) or np.isnan(m2):
        return out
    out["diff"] = m1 - m2
    if min(int(res["n_clusters"][idx_1]), int(res["n_clusters"][idx_2])) < 2 or res["df"] < 1:
        return out  # grupo concentrado numa única escola: variância não estimável
    cov = res["cov"]
    var = float(cov[idx_1, idx_1] + cov[idx_2, idx_2] - 2 * cov[idx_1, idx_2])
    if not var > 0:
        return out
    se = float(np.sqrt(var))
    t_stat = out["diff"] / se
    out.update(se=se, t=float(t_stat), p=float(2 * stats.t.sf(abs(t_stat), res["df"])))
    return out


def wald_anova_from_group_means(res: GroupMeansResult) -> Tuple[float, float, int]:
    """Compute Korn–Graubard adjusted Wald F-test from *res*."""
    # Grupos concentrados numa única escola não têm variância estimável:
    # ficam fora do teste (continuam nas estatísticas descritivas).
    keep = (res["n_clusters"] >= 2) & ~np.isnan(res["means"])
    means = res["means"][keep]
    cov = res["cov"][np.ix_(keep, keep)]
    d = res["df"]
    k = len(means)
    if k < 2 or d < 1:
        return (np.nan, np.nan, max(k - 1, 0))
    q = k - 1
    C = np.hstack([np.ones((q, 1)), -np.eye(q)])  # mean_1 − mean_j
    diff = C @ means
    V = C @ cov @ C.T
    try:
        wald = float(diff @ np.linalg.solve(V, diff))
    except np.linalg.LinAlgError:
        wald = float(diff @ np.linalg.pinv(V) @ diff)
    df2 = d - q + 1
    if df2 < 1:
        return (np.nan, np.nan, q)
    f_stat = (d - q + 1) / (d * q) * wald
    p_value = float(stats.f.sf(f_stat, q, df2))
    return (float(f_stat), p_value, q)


def design_ttest(
    values: ArrayLike,
    weights: ArrayLike,
    labels: ArrayLike,
    level_1: object,
    level_2: object,
    clusters: ArrayLike,
    strata: Optional[ArrayLike] = None,
    domain: Optional[ArrayLike] = None,
) -> Dict[str, float]:
    """Design-based test of mean(level_1) − mean(level_2), as domains.

    Both groups are estimated jointly over the full design (``clusters`` /
    ``strata`` for all observations); observations outside ``domain`` or with
    another label enter with zero influence.

    Returns a dict with ``diff``, ``se``, ``t``, ``p`` and ``df``. ``se``,
    ``t`` and ``p`` are NaN when a group lies in a single cluster.
    """
    lab = np.asarray(labels, dtype=object)
    dom = np.ones(len(lab), dtype=bool) if domain is None else np.asarray(domain, dtype=bool)
    in_pair = dom & ((lab == level_1) | (lab == level_2))
    codes = np.where(lab == level_1, 0, 1)
    res = linearized_group_means(values, weights, codes, clusters, strata, domain=in_pair)
    if list(res["levels"]) != [0, 1]:
        return {"diff": np.nan, "se": np.nan, "t": np.nan, "p": np.nan, "df": float(res["df"])}
    return ttest_from_group_means(res, 0, 1)


# ---------- Descriptive statistics ----------


def weighted_mean(values: ArrayLike, weights: ArrayLike) -> float:
    """Weighted arithmetic mean, ignoring NaN values."""
    v, w = _clean(values, weights)
    if not _valid_weights(w):
        return np.nan
    return float(np.average(v, weights=w))


def weighted_variance(
    values: ArrayLike, weights: ArrayLike, ddof: int = 1
) -> float:
    """Weighted variance with Bessel-like correction.

    Uses reliability weights: Var = (sum w_i (x_i - xbar)^2) / (V1 - V2/V1)
    where V1 = sum(w), V2 = sum(w^2).  When ddof=0 the denominator is V1.
    """
    v, w = _clean(values, weights)
    if not _valid_weights(w):
        return np.nan
    mu = np.average(v, weights=w)
    v1 = w.sum()
    numerator = np.sum(w * (v - mu) ** 2)
    if ddof == 0:
        return float(numerator / v1)
    v2 = np.sum(w ** 2)
    denom = v1 - v2 / v1
    if denom <= 0:
        return np.nan
    return float(numerator / denom)


def weighted_std(
    values: ArrayLike, weights: ArrayLike, ddof: int = 1
) -> float:
    """Weighted standard deviation."""
    var = weighted_variance(values, weights, ddof=ddof)
    if np.isnan(var):
        return np.nan
    return float(np.sqrt(var))


def weighted_percentile(
    values: ArrayLike, weights: ArrayLike, q: float
) -> float:
    """Weighted percentile using cumulative-weight interpolation.

    Parameters
    ----------
    q : float
        Desired percentile in the range 0-100.
    """
    v, w = _clean(values, weights)
    if not _valid_weights(w):
        return np.nan
    order = np.argsort(v)
    v = v[order]
    w = w[order]
    cum = np.cumsum(w)
    # Normalise cumulative weights to 0-100 scale, centred on each obs.
    cum_pct = (cum - 0.5 * w) / cum[-1] * 100.0
    return float(np.interp(q, cum_pct, v))


# ---------- Inference ----------


def confidence_interval_mean(
    values: ArrayLike,
    weights: ArrayLike,
    strata: Optional[ArrayLike] = None,
    alpha: float = 0.05,
    clusters: Optional[ArrayLike] = None,
    domain: Optional[ArrayLike] = None,
) -> Tuple[float, float, float]:
    """Confidence interval for a weighted mean.

    With *clusters* (and optional *strata*) the standard error is the
    design-based Taylor-linearization SE with (#clusters − #strata) degrees
    of freedom; *domain* (boolean) restricts the estimate to a subgroup
    while keeping the full design (domain estimation). Otherwise, if
    *strata* alone is provided, a stratified SRS variance (bounded design
    effect) is used; with neither, plain SRS.

    Returns
    -------
    (mean, lower, upper)
    """
    if clusters is not None:
        valid = _design_masks(values, weights)
        if domain is not None:
            valid &= np.asarray(domain, dtype=bool)
        if not valid.any():
            return (np.nan, np.nan, np.nan)
        res = linearized_group_means(
            values, weights, np.zeros(len(np.asarray(values))), clusters, strata, domain=valid
        )
        return ci_from_group_means(res, 0, alpha=alpha)

    if domain is not None:
        dom = np.asarray(domain, dtype=bool)
        values = np.asarray(values, dtype=np.float64)[dom]
        weights = np.asarray(weights, dtype=np.float64)[dom]
        if strata is not None:
            strata = np.asarray(strata)[dom]
    v, w = _clean(values, weights)
    if not _valid_weights(w):
        return (np.nan, np.nan, np.nan)

    mu = np.average(v, weights=w)
    n = len(v)
    v1 = w.sum()
    v2 = np.sum(w ** 2)
    # Weighted variance (ddof=1)
    s2 = np.sum(w * (v - mu) ** 2) / (v1 - v2 / v1) if (v1 - v2 / v1) > 0 else 0.0
    # Variance of the weighted mean under SRS
    se2 = s2 * v2 / (v1 ** 2)

    deff = 1.0
    if strata is not None:
        strata_arr = np.asarray(strata)
        # Keep same mask as _clean applied to values/weights
        mask = ~np.isnan(np.asarray(values, dtype=np.float64)) & ~np.isnan(
            np.asarray(weights, dtype=np.float64)
        )
        strata_arr = strata_arr[mask]
        unique_strata = np.unique(strata_arr)
        if len(unique_strata) > 1:
            # Estimate DEFF = Var_stratified / Var_SRS
            var_strat = 0.0
            for s in unique_strata:
                idx = strata_arr == s
                vs, ws = v[idx], w[idx]
                if len(vs) < 2:
                    continue
                ws_sum = ws.sum()
                if ws_sum <= 0:
                    continue
                mu_s = np.average(vs, weights=ws)
                ws2 = np.sum(ws ** 2)
                denom = ws_sum - ws2 / ws_sum
                if denom > 0:
                    s2_s = np.sum(ws * (vs - mu_s) ** 2) / denom
                else:
                    s2_s = 0.0
                var_strat += (ws_sum / v1) ** 2 * s2_s * ws2 / (ws_sum ** 2)
            if se2 > 0:
                deff = var_strat / se2
                deff = max(deff, 0.1)  # floor to avoid nonsensical shrinkage
                se2 = deff * se2

    se = np.sqrt(se2)
    df = max(n - 1, 1)
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    lower = mu - t_crit * se
    upper = mu + t_crit * se
    return (float(mu), float(lower), float(upper))


def weighted_ttest(
    vals1: ArrayLike,
    w1: ArrayLike,
    vals2: ArrayLike,
    w2: ArrayLike,
) -> Tuple[float, float, float]:
    """Two-sample t-test for weighted data (Welch-like, SRS).

    For design-based inference with clusters/strata use :func:`design_ttest`.

    Returns
    -------
    (t_statistic, p_value, mean_difference)
    """
    v1, wt1 = _clean(vals1, w1)
    v2, wt2 = _clean(vals2, w2)
    if not _valid_weights(wt1) or not _valid_weights(wt2):
        return (np.nan, np.nan, np.nan)

    mu1 = np.average(v1, weights=wt1)
    mu2 = np.average(v2, weights=wt2)
    diff = mu1 - mu2

    def _weighted_se(v: np.ndarray, w: np.ndarray) -> Tuple[float, float]:
        n = len(v)
        mu = np.average(v, weights=w)
        sw = w.sum()
        sw2 = np.sum(w ** 2)
        denom = sw - sw2 / sw
        s2 = np.sum(w * (v - mu) ** 2) / denom if denom > 0 else 0.0
        se2 = s2 * sw2 / (sw ** 2)
        return se2, n

    se2_1, n1 = _weighted_se(v1, wt1)
    se2_2, n2 = _weighted_se(v2, wt2)
    se = np.sqrt(se2_1 + se2_2)

    if se == 0:
        return (0.0, 1.0, float(diff))

    t_stat = diff / se

    # Welch-Satterthwaite degrees of freedom
    num = (se2_1 + se2_2) ** 2
    denom = (se2_1 ** 2 / max(n1 - 1, 1)) + (se2_2 ** 2 / max(n2 - 1, 1))
    df = num / denom if denom > 0 else 1.0
    df = max(df, 1.0)

    p_value = 2 * stats.t.sf(np.abs(t_stat), df)
    return (float(t_stat), float(p_value), float(diff))


def cohens_d_weighted(
    vals1: ArrayLike,
    w1: ArrayLike,
    vals2: ArrayLike,
    w2: ArrayLike,
) -> float:
    """Weighted Cohen's d effect size (scale-invariant pooled standard deviation).

    Invariant to positive rescaling ``c * w`` for any ``c > 0``: within-group
    variances use Bessel reliability-weight correction ``V1^2 / (V1^2 - V2)``,
    and the pooled variance weights each group by its population weight share
    ``s_pooled^2 = (sw1 * var1 + sw2 * var2) / (sw1 + sw2)``. Requires at least
    2 valid observations with positive weight in each group.
    """
    v1, wt1 = _clean(vals1, w1)
    v2, wt2 = _clean(vals2, w2)
    if not _valid_weights(wt1) or not _valid_weights(wt2):
        return np.nan
    if int(np.count_nonzero(wt1 > 0)) < 2 or int(np.count_nonzero(wt2 > 0)) < 2:
        return np.nan

    # Normalize both groups by a shared positive constant to avoid float
    # overflow/underflow on extreme weight scales while preserving sw1/sw2.
    scale = max(float(wt1.max()), float(wt2.max()))
    u1 = wt1 / scale
    u2 = wt2 / scale

    mu1 = float(np.average(v1, weights=u1))
    mu2 = float(np.average(v2, weights=u2))

    var1 = weighted_variance(v1, u1, ddof=1)
    var2 = weighted_variance(v2, u2, ddof=1)
    if np.isnan(var1) or np.isnan(var2):
        return np.nan

    sw1 = float(u1.sum())
    sw2 = float(u2.sum())
    denom = sw1 + sw2
    if denom <= 0:
        return np.nan
    pooled_var = (sw1 * var1 + sw2 * var2) / denom
    if not np.isfinite(pooled_var) or pooled_var <= 0:
        return np.nan
    return float((mu1 - mu2) / np.sqrt(pooled_var))


# ---------- Categorical / association tests ----------


def weighted_anova_oneway(
    values: ArrayLike,
    weights: ArrayLike,
    groups: ArrayLike,
    clusters: Optional[ArrayLike] = None,
    strata: Optional[ArrayLike] = None,
    domain: Optional[ArrayLike] = None,
) -> Tuple[float, float, int]:
    """Weighted one-way ANOVA F-test.

    Without *clusters*: classical weighted sums of squares (SRS) on the
    observations in *domain*.

    With *clusters* (and optional *strata*): design-based Wald test of the
    equality of all group means (estimated as domains, see module notes),
    using the linearized covariance of the means and the Korn–Graubard
    adjusted F,
    ``F = (d − q + 1) / (d·q) · W`` with ``q = k − 1`` and ``d`` the design
    degrees of freedom, referred to F(q, d − q + 1) — as in Stata ``svy``.

    Returns
    -------
    (F_statistic, p_value, degrees_of_freedom_between)
    """
    if clusters is not None:
        res = linearized_group_means(values, weights, groups, clusters, strata, domain=domain)
        return wald_anova_from_group_means(res)

    if domain is not None:
        dom = np.asarray(domain, dtype=bool)
        values = np.asarray(values, dtype=np.float64)[dom]
        weights = np.asarray(weights, dtype=np.float64)[dom]
        groups = np.asarray(groups)[dom]
    v, w = _clean(values, weights)
    g = np.asarray(groups)
    # Apply same NaN mask
    mask = ~np.isnan(np.asarray(values, dtype=np.float64)) & ~np.isnan(
        np.asarray(weights, dtype=np.float64)
    )
    g = g[mask]

    if not _valid_weights(w):
        return (np.nan, np.nan, 0)

    unique_groups = np.unique(g)
    if len(unique_groups) < 2:
        return (np.nan, np.nan, 0)

    grand_mean = np.average(v, weights=w)

    ss_between = 0.0
    ss_within = 0.0
    df_within = 0
    valid_groups = 0

    for grp in unique_groups:
        idx = g == grp
        vg, wg = v[idx], w[idx]
        if len(vg) == 0:
            continue
        wg_sum = wg.sum()
        if wg_sum <= 0:
            continue
        valid_groups += 1
        ng = len(vg)
        mu_g = np.average(vg, weights=wg)
        ss_between += wg_sum * (mu_g - grand_mean) ** 2
        ss_within += np.sum(wg * (vg - mu_g) ** 2)
        df_within += ng - 1

    if valid_groups < 2:
        return (np.nan, np.nan, 0)

    df_between = valid_groups - 1
    if df_within <= 0 or ss_within == 0:
        return (np.nan, np.nan, df_between)

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    f_stat = ms_between / ms_within

    p_value = float(stats.f.sf(f_stat, df_between, df_within))
    return (float(f_stat), p_value, df_between)


def weighted_eta_squared(
    values: ArrayLike,
    weights: ArrayLike,
    groups: ArrayLike,
) -> float:
    """Weighted eta-squared (SS_between / SS_total) for a one-way design.

    Effect-size companion of :func:`weighted_anova_oneway`: the share of
    the (weighted) variance of *values* explained by group membership.
    """
    v, w = _clean(values, weights)
    mask = ~np.isnan(np.asarray(values, dtype=np.float64)) & ~np.isnan(
        np.asarray(weights, dtype=np.float64)
    )
    g = np.asarray(groups)[mask]
    if not _valid_weights(w) or len(np.unique(g)) < 2:
        return np.nan

    grand_mean = np.average(v, weights=w)
    ss_total = float(np.sum(w * (v - grand_mean) ** 2))
    if ss_total <= 0:
        return np.nan
    ss_between = 0.0
    for grp in np.unique(g):
        idx = g == grp
        wg = w[idx]
        wg_sum = wg.sum()
        if wg_sum <= 0:
            continue
        ss_between += wg_sum * (np.average(v[idx], weights=wg) - grand_mean) ** 2
    return float(ss_between / ss_total)


def chi_squared_test(
    observed: Union[ArrayLike, List[List[float]]],
) -> Tuple[float, float, int]:
    """Chi-squared test of independence on a 2-D contingency table.

    Returns
    -------
    (chi2, p_value, degrees_of_freedom)
    """
    obs = np.asarray(observed, dtype=np.float64)
    if obs.ndim != 2 or obs.shape[0] < 2 or obs.shape[1] < 2:
        return (np.nan, np.nan, 0)
    chi2, p, dof, _ = stats.chi2_contingency(obs)
    return (float(chi2), float(p), int(dof))


def pearson_weighted(
    x: ArrayLike,
    y: ArrayLike,
    weights: ArrayLike,
    clusters: Optional[ArrayLike] = None,
    strata: Optional[ArrayLike] = None,
    domain: Optional[ArrayLike] = None,
) -> Tuple[float, float]:
    """Weighted Pearson correlation coefficient (within *domain*, if given).

    Returns
    -------
    (r, p_value)
        Without *clusters*, the p-value uses the t-distribution with n−2 df.
        With *clusters* (and optional *strata*), it is the design-based test
        of the weighted regression slope of y on x (equivalent null
        hypothesis r = 0), with linearized SE and design df.
    """
    mask = _design_masks(x, y, weights)
    if domain is not None:
        mask &= np.asarray(domain, dtype=bool)
    if clusters is not None:
        xa = np.asarray(x, dtype=np.float64)
        ya = np.asarray(y, dtype=np.float64)
        wa = np.asarray(weights, dtype=np.float64)
        xc, yc, wc = xa[mask], ya[mask], wa[mask]
        r, _ = pearson_weighted(xc, yc, wc)
        if np.isnan(r):
            return (r, np.nan)
        dx = xc - np.average(xc, weights=wc)
        dy = yc - np.average(yc, weights=wc)
        sxx = np.sum(wc * dx ** 2)
        slope = np.sum(wc * dx * dy) / sxx
        # Influência da inclinação: zero fora do domínio (desenho completo)
        influence = np.zeros(len(xa))
        influence[mask] = wc * dx * (dy - slope * dx) / sxx
        cov, df = linearized_covariance(
            influence, np.asarray(clusters), None if strata is None else np.asarray(strata)
        )
        se = np.sqrt(cov[0, 0]) if cov[0, 0] > 0 else np.nan
        if np.isnan(se) or df < 1:
            return (r, np.nan)
        p_value = 2 * stats.t.sf(abs(slope / se), df)
        return (r, float(p_value))

    if domain is not None:
        x = np.asarray(x, dtype=np.float64)[mask]
        y = np.asarray(y, dtype=np.float64)[mask]
        weights = np.asarray(weights, dtype=np.float64)[mask]

    xc, yc, wc = _clean(x, y, weights)
    n = len(xc)
    if n < 3 or not _valid_weights(wc):
        return (np.nan, np.nan)

    mu_x = np.average(xc, weights=wc)
    mu_y = np.average(yc, weights=wc)
    dx = xc - mu_x
    dy = yc - mu_y

    w_sum = wc.sum()
    cov_xy = np.sum(wc * dx * dy) / w_sum
    var_x = np.sum(wc * dx ** 2) / w_sum
    var_y = np.sum(wc * dy ** 2) / w_sum

    denom = np.sqrt(var_x * var_y)
    if not (denom > 0):
        return (np.nan, np.nan)

    r = cov_xy / denom
    # Clamp to [-1, 1] to guard against floating-point overshoot
    r = float(np.clip(r, -1.0, 1.0))

    # Two-tailed p-value via t-distribution
    t_stat = r * np.sqrt((n - 2) / (1 - r ** 2)) if abs(r) < 1 else np.inf
    p_value = 2 * stats.t.sf(np.abs(t_stat), n - 2)
    return (r, float(p_value))


# ---------- Frequency ----------


def weighted_frequency(
    values: ArrayLike, weights: ArrayLike
) -> Dict[float, Tuple[float, float]]:
    """Weighted frequency table.

    Returns
    -------
    dict mapping each unique value to (weighted_count, proportion).
    NaN values in *values* are dropped.
    """
    v, w = _clean(values, weights)
    if len(v) == 0 or np.any(w < 0):
        return {}
    total = w.sum()
    unique_vals = np.unique(v)
    result: Dict[float, Tuple[float, float]] = {}
    for uv in unique_vals:
        mask = v == uv
        wc = float(w[mask].sum())
        result[float(uv)] = (wc, wc / total if total > 0 else 0.0)
    return result
