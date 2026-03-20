"""
Weighted statistical functions for analyzing SAEB 2023 survey data.

Provides numerically stable implementations of common statistics
that account for survey weights, stratification, and design effects.
"""

from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from numpy.typing import ArrayLike
from scipy import stats


def _clean(
    *arrays: ArrayLike,
) -> Tuple[np.ndarray, ...]:
    """Convert inputs to float64 arrays and drop rows where any array has NaN."""
    arrs = [np.asarray(a, dtype=np.float64) for a in arrays]
    mask = np.ones(len(arrs[0]), dtype=bool)
    for a in arrs:
        mask &= ~np.isnan(a)
    return tuple(a[mask] for a in arrs)


# ---------- Descriptive statistics ----------


def weighted_mean(values: ArrayLike, weights: ArrayLike) -> float:
    """Weighted arithmetic mean, ignoring NaN values."""
    v, w = _clean(values, weights)
    if len(v) == 0:
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
    if len(v) == 0:
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
    if len(v) == 0:
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
) -> Tuple[float, float, float]:
    """Confidence interval for a weighted mean.

    If *strata* is provided the design effect (DEFF) is estimated and
    used to inflate the standard error.

    Returns
    -------
    (mean, lower, upper)
    """
    v, w = _clean(values, weights)
    if len(v) == 0:
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
                se2 = var_strat

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
    """Two-sample t-test for weighted data (Welch-like).

    Returns
    -------
    (t_statistic, p_value, mean_difference)
    """
    v1, wt1 = _clean(vals1, w1)
    v2, wt2 = _clean(vals2, w2)
    if len(v1) == 0 or len(v2) == 0:
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
    """Weighted Cohen's d effect size (pooled standard deviation)."""
    v1, wt1 = _clean(vals1, w1)
    v2, wt2 = _clean(vals2, w2)
    if len(v1) == 0 or len(v2) == 0:
        return np.nan

    mu1 = np.average(v1, weights=wt1)
    mu2 = np.average(v2, weights=wt2)

    var1 = weighted_variance(v1, wt1, ddof=1)
    var2 = weighted_variance(v2, wt2, ddof=1)

    sw1 = wt1.sum()
    sw2 = wt2.sum()
    # Pooled variance weighted by effective sample sizes
    pooled_var = ((sw1 - 1) * var1 + (sw2 - 1) * var2) / (sw1 + sw2 - 2)
    if pooled_var <= 0:
        return np.nan
    return float((mu1 - mu2) / np.sqrt(pooled_var))


# ---------- Categorical / association tests ----------


def weighted_anova_oneway(
    values: ArrayLike,
    weights: ArrayLike,
    groups: ArrayLike,
) -> Tuple[float, float, int]:
    """Weighted one-way ANOVA F-test.

    Computes between-group and within-group weighted sums of squares
    to test whether group means differ significantly.

    Returns
    -------
    (F_statistic, p_value, degrees_of_freedom_between)
    """
    v, w = _clean(values, weights)
    g = np.asarray(groups)
    # Apply same NaN mask
    mask = ~np.isnan(np.asarray(values, dtype=np.float64)) & ~np.isnan(
        np.asarray(weights, dtype=np.float64)
    )
    g = g[mask]

    if len(v) == 0:
        return (np.nan, np.nan, 0)

    unique_groups = np.unique(g)
    k = len(unique_groups)
    if k < 2:
        return (np.nan, np.nan, 0)

    grand_mean = np.average(v, weights=w)
    total_w = w.sum()

    ss_between = 0.0
    ss_within = 0.0
    df_within = 0

    for grp in unique_groups:
        idx = g == grp
        vg, wg = v[idx], w[idx]
        if len(vg) == 0:
            continue
        ng = len(vg)
        wg_sum = wg.sum()
        mu_g = np.average(vg, weights=wg)
        ss_between += wg_sum * (mu_g - grand_mean) ** 2
        ss_within += np.sum(wg * (vg - mu_g) ** 2)
        df_within += ng - 1

    df_between = k - 1
    if df_within <= 0 or ss_within == 0:
        return (np.nan, np.nan, df_between)

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    f_stat = ms_between / ms_within

    p_value = float(stats.f.sf(f_stat, df_between, df_within))
    return (float(f_stat), p_value, df_between)


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
    x: ArrayLike, y: ArrayLike, weights: ArrayLike
) -> Tuple[float, float]:
    """Weighted Pearson correlation coefficient.

    Returns
    -------
    (r, p_value)
        p-value is computed using the t-distribution with n-2 df.
    """
    xc, yc, wc = _clean(x, y, weights)
    n = len(xc)
    if n < 3:
        return (np.nan, np.nan)

    mu_x = np.average(xc, weights=wc)
    mu_y = np.average(yc, weights=wc)
    dx = xc - mu_x
    dy = yc - mu_y

    cov_xy = np.sum(wc * dx * dy) / np.sum(wc)
    var_x = np.sum(wc * dx ** 2) / np.sum(wc)
    var_y = np.sum(wc * dy ** 2) / np.sum(wc)

    denom = np.sqrt(var_x * var_y)
    if denom == 0:
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
    if len(v) == 0:
        return {}
    total = w.sum()
    unique_vals = np.unique(v)
    result: Dict[float, Tuple[float, float]] = {}
    for uv in unique_vals:
        mask = v == uv
        wc = float(w[mask].sum())
        result[float(uv)] = (wc, wc / total if total > 0 else 0.0)
    return result
