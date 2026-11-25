"""Testes unitários do módulo de estatística ponderada."""

import numpy as np
import pytest

from backend.analysis.stats_utils import (
    weighted_mean,
    weighted_variance,
    weighted_percentile,
    confidence_interval_mean,
    weighted_ttest,
    cohens_d_weighted,
)


class TestWeightedMean:
    def test_equal_weights(self):
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        weights = np.ones(5)
        result = weighted_mean(values, weights)
        assert result == pytest.approx(3.0)

    def test_unequal_weights(self):
        values = np.array([10.0, 20.0])
        weights = np.array([3.0, 1.0])
        result = weighted_mean(values, weights)
        assert result == pytest.approx(12.5)

    def test_single_value(self):
        values = np.array([42.0])
        weights = np.array([1.0])
        result = weighted_mean(values, weights)
        assert result == pytest.approx(42.0)


class TestWeightedVariance:
    def test_equal_weights(self):
        values = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        weights = np.ones(8)
        result = weighted_variance(values, weights)
        # Variância amostral com pesos iguais = variância clássica
        expected = np.var(values, ddof=1)
        assert result == pytest.approx(expected, rel=0.1)

    def test_zero_variance(self):
        values = np.array([5.0, 5.0, 5.0])
        weights = np.array([1.0, 2.0, 3.0])
        result = weighted_variance(values, weights)
        assert result == pytest.approx(0.0, abs=1e-10)


class TestWeightedPercentile:
    def test_median_equal_weights(self):
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        weights = np.ones(5)
        result = weighted_percentile(values, weights, 50)
        assert 2.5 <= result <= 3.5  # mediana entre 2 e 4


class TestConfidenceInterval:
    def test_basic_ci(self):
        np.random.seed(42)
        values = np.random.normal(100, 15, 200)
        weights = np.ones(200)
        strata = np.ones(200)
        ci = confidence_interval_mean(values, weights, strata)
        # Retorna tupla (mean, ci_lower, ci_upper)
        mean, ci_lower, ci_upper = ci
        assert ci_lower < mean < ci_upper
        # Média deve estar próxima de 100
        assert 95 < mean < 105


class TestWeightedTtest:
    def test_different_groups(self):
        np.random.seed(42)
        g1 = np.random.normal(250, 30, 100)
        g2 = np.random.normal(270, 30, 100)
        w1 = np.ones(100)
        w2 = np.ones(100)
        result = weighted_ttest(g1, w1, g2, w2)
        # Retorna tupla (t_stat, p_value, gap)
        t_stat, p_value, gap = result
        assert p_value < 0.05  # diferença deve ser significativa
        assert gap == pytest.approx(-20, abs=10)


class TestCohensD:
    def test_medium_effect(self):
        np.random.seed(42)
        g1 = np.random.normal(250, 40, 200)
        g2 = np.random.normal(270, 40, 200)
        w1 = np.ones(200)
        w2 = np.ones(200)
        d = cohens_d_weighted(g1, w1, g2, w2)
        # d de Cohen esperado ≈ 0.5 (efeito médio)
        assert 0.2 < abs(d) < 0.8

    def test_no_effect(self):
        np.random.seed(42)
        g1 = np.random.normal(260, 40, 200)
        g2 = np.random.normal(260, 40, 200)
        w1 = np.ones(200)
        w2 = np.ones(200)
        d = cohens_d_weighted(g1, w1, g2, w2)
        assert abs(d) < 0.3


class TestEtaSquared:
    def test_perfect_separation(self):
        from backend.analysis.stats_utils import weighted_eta_squared

        values = np.array([1.0, 1.0, 5.0, 5.0])
        groups = np.array(["a", "a", "b", "b"])
        assert weighted_eta_squared(values, np.ones(4), groups) == pytest.approx(1.0)

    def test_no_group_effect(self):
        from backend.analysis.stats_utils import weighted_eta_squared

        values = np.array([1.0, 5.0, 1.0, 5.0])
        groups = np.array(["a", "a", "b", "b"])
        assert weighted_eta_squared(values, np.ones(4), groups) == pytest.approx(0.0)


class TestConfidenceIntervalDeffFloor:
    def test_floor_bounds_shrinkage(self):
        """Com estratos perfeitamente homogêneos, o DEFF é limitado a 0,1."""
        values = np.array([10.0] * 50 + [20.0] * 50)
        weights = np.ones(100)
        strata = np.array([0] * 50 + [1] * 50)
        mean, lo, hi = confidence_interval_mean(values, weights, strata)
        assert mean == pytest.approx(15.0)
        assert hi - lo > 0  # sem o piso, a variância estratificada seria 0


class TestCohensDDegenerate:
    def test_tiny_weights_return_nan(self):
        d = cohens_d_weighted(
            np.array([1.0, 2.0]), np.array([0.1, 0.1]),
            np.array([3.0, 4.0]), np.array([0.1, 0.1]),
        )
        assert np.isnan(d)


class TestDesignBasedInference:
    """Linearização de Taylor com conglomerados/estratos (ver stats_utils)."""

    def _data(self):
        rng = np.random.default_rng(7)
        clusters = np.repeat(np.arange(40), 25)
        school_effect = rng.normal(0, 8, 40)[clusters]
        values = 250 + school_effect + rng.normal(0, 20, len(clusters))
        weights = rng.uniform(0.5, 2.0, len(clusters))
        return values, weights, clusters

    def test_cluster_se_matches_manual_formula(self):
        from backend.analysis.stats_utils import linearized_group_means

        v, w, cl = self._data()
        res = linearized_group_means(v, w, np.zeros(len(v)), cl)
        mu = np.sum(w * v) / w.sum()
        totals = np.bincount(cl, weights=w * (v - mu) / w.sum())
        g = len(totals)
        expected = g / (g - 1) * np.sum((totals - totals.mean()) ** 2)
        assert res["cov"][0, 0] == pytest.approx(expected)
        assert res["df"] == g - 1

    def test_clustering_widens_ci(self):
        v, w, cl = self._data()
        _, lo_srs, hi_srs = confidence_interval_mean(v, w)
        _, lo_cl, hi_cl = confidence_interval_mean(v, w, clusters=cl)
        assert (hi_cl - lo_cl) > 1.5 * (hi_srs - lo_srs)

    def test_single_cluster_group_has_no_test(self):
        from backend.analysis.stats_utils import design_ttest

        v, w, cl = self._data()
        labels = np.where(cl == 0, "a", "b")  # grupo "a" inteiro numa única escola
        res = design_ttest(v, w, labels, "a", "b", cl)
        assert np.isnan(res["p"]) and not np.isnan(res["diff"])

    def test_domain_keeps_full_design(self):
        """Subgrupo como domínio: escolas sem membros entram com total zero."""
        from backend.analysis.stats_utils import linearized_group_means

        v, w, cl = self._data()
        dom = (np.arange(len(v)) % 3 == 0) & (cl < 30)  # escolas 30–39 sem membros
        res = linearized_group_means(v, w, np.zeros(len(v)), cl, domain=dom)
        mu = np.sum(w[dom] * v[dom]) / w[dom].sum()
        z = np.where(dom, w * (v - mu) / w[dom].sum(), 0.0)
        totals = np.bincount(cl, weights=z)          # inclui as 10 escolas com total 0
        g = len(totals)
        expected = g / (g - 1) * np.sum((totals - totals.mean()) ** 2)
        assert res["cov"][0, 0] == pytest.approx(expected)
        assert res["df"] == g - 1
        # Recortar o desenho (descartar escolas sem membros) daria outra variância
        cut = linearized_group_means(v[dom], w[dom], np.zeros(dom.sum()), cl[dom])
        assert cut["cov"][0, 0] != pytest.approx(expected)

    def test_to_float_keeps_nulls_as_nan(self):
        import duckdb
        from backend.analysis.stats_utils import to_float

        col = duckdb.sql("SELECT * FROM (VALUES (1.5), (NULL)) t(x)").fetchnumpy()["x"]
        out = to_float(col)
        assert out[0] == 1.5 and np.isnan(out[1])
