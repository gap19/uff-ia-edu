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
