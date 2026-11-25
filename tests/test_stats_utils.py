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


class TestCohensDScaleInvarianceAndGuards:
    def test_scale_invariance_positive_rescaling(self):
        """Multiplicar pesos por qualquer c > 0 preserva exatamente Cohen's d (R-03)."""
        g1 = np.array([210.0, 230.0, 250.0, 270.0, 290.0])
        g2 = np.array([180.0, 200.0, 215.0, 235.0, 255.0])
        w1 = np.array([1.2, 2.5, 0.8, 3.1, 1.4])
        w2 = np.array([2.0, 1.1, 1.9, 0.7, 2.3])

        d_base = cohens_d_weighted(g1, w1, g2, w2)
        assert np.isfinite(d_base) and d_base > 0

        for scale in (1e-6, 1e-3, 0.1, 10.0, 1e3, 1e6):
            d_scaled = cohens_d_weighted(g1, w1 * scale, g2, w2 * scale)
            assert d_scaled == pytest.approx(d_base, rel=1e-12, abs=1e-12)

    def test_fewer_than_two_positive_weights_or_invalid_returns_nan(self):
        """Exige pelo menos 2 observações válidas com peso positivo em cada grupo (R-03)."""
        # n < 2 em um dos grupos
        assert np.isnan(cohens_d_weighted([10.0], [1.0], [20.0, 30.0], [1.0, 1.0]))
        assert np.isnan(cohens_d_weighted([10.0, 20.0], [1.0, 1.0], [30.0], [1.0]))
        # 2 observações, mas apenas 1 com peso positivo
        assert np.isnan(cohens_d_weighted([10.0, 20.0], [5.0, 0.0], [30.0, 40.0], [1.0, 1.0]))
        # Pesos zero ou negativos
        assert np.isnan(cohens_d_weighted([10.0, 20.0], [0.0, 0.0], [30.0, 40.0], [1.0, 1.0]))
        assert np.isnan(cohens_d_weighted([10.0, 20.0], [-1.0, 2.0], [30.0, 40.0], [1.0, 1.0]))

    def test_saeb_real_data_scale_invariance_and_close_to_legacy(self):
        """Nos microdados SAEB RJ 9EF LP, d é invariante à escala e difere < 1e-4 do legado."""
        import duckdb
        from backend.analysis.stats_utils import to_float, weighted_variance
        from backend.config import ID_UF_RJ, SAEB_PARQUET_DIR

        pq = SAEB_PARQUET_DIR / "TS_ALUNO_9EF.parquet"
        con = duckdb.connect()
        try:
            df = con.execute(
                f"SELECT PROFICIENCIA_LP_SAEB AS p, PESO_ALUNO_LP AS w, IN_PUBLICA AS pub "
                f"FROM '{pq}' WHERE ID_UF = ? AND PROFICIENCIA_LP_SAEB IS NOT NULL "
                f"AND PESO_ALUNO_LP IS NOT NULL",
                [ID_UF_RJ],
            ).fetchnumpy()
        finally:
            con.close()

        p = to_float(df["p"])
        w = to_float(df["w"])
        pub = to_float(df["pub"])
        m_priv, m_pub = pub == 0, pub == 1

        d_orig = cohens_d_weighted(p[m_priv], w[m_priv], p[m_pub], w[m_pub])
        d_micro = cohens_d_weighted(p[m_priv], w[m_priv] * 1e-6, p[m_pub], w[m_pub] * 1e-6)
        d_mega = cohens_d_weighted(p[m_priv], w[m_priv] * 1e6, p[m_pub], w[m_pub] * 1e6)
        assert d_micro == pytest.approx(d_orig, rel=1e-12, abs=1e-12)
        assert d_mega == pytest.approx(d_orig, rel=1e-12, abs=1e-12)

        sw1, sw2 = float(w[m_priv].sum()), float(w[m_pub].sum())
        v1 = weighted_variance(p[m_priv], w[m_priv])
        v2 = weighted_variance(p[m_pub], w[m_pub])
        mu1 = float(np.average(p[m_priv], weights=w[m_priv]))
        mu2 = float(np.average(p[m_pub], weights=w[m_pub]))
        d_legacy = (mu1 - mu2) / np.sqrt(((sw1 - 1) * v1 + (sw2 - 1) * v2) / (sw1 + sw2 - 2))
        assert abs(d_orig - d_legacy) < 1e-4


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

    def test_to_str_keeps_nulls_as_empty_string(self):
        import duckdb
        from backend.analysis.stats_utils import to_str

        col = duckdb.sql("SELECT * FROM (VALUES ('A'), (NULL), ('B')) t(x)").fetchnumpy()["x"]
        out = to_str(col)
        assert list(out) == ["A", "", "B"]

    def test_nested_strata_permutation_invariance_multi_stratum_school(self):
        """Escola presente em 2 estratos: cov e df devem ser invariantes à ordem das linhas (F-01)."""
        from backend.analysis.stats_utils import linearized_covariance, linearized_group_means

        rng = np.random.default_rng(123)
        # Escola 100 aparece no estrato 1 (3ª EM) e no estrato 2 (4ª EM)
        strata = np.array([1] * 20 + [1] * 20 + [2] * 20 + [2] * 20)
        clusters = np.array([100] * 20 + [101] * 20 + [100] * 20 + [201] * 20)
        values = rng.normal(250, 25, len(strata))
        weights = rng.uniform(0.5, 3.0, len(strata))
        groups = np.where(np.arange(len(strata)) % 2 == 0, "A", "B")

        res_base = linearized_group_means(values, weights, groups, clusters=clusters, strata=strata)
        # 4 PSUs aninhados (1,100), (1,101), (2,100), (2,201) em 2 estratos -> df = 4 - 2 = 2
        assert res_base["df"] == 2

        Z_base = rng.normal(0, 1, (len(strata), 2))
        cov_base, df_base = linearized_covariance(Z_base, clusters=clusters, strata=strata)
        assert df_base == 2

        for seed in (1, 7, 42):
            perm = np.random.default_rng(seed).permutation(len(strata))
            res_p = linearized_group_means(
                values[perm], weights[perm], groups[perm],
                clusters=clusters[perm], strata=strata[perm],
            )
            assert res_p["df"] == res_base["df"]
            assert np.allclose(res_p["means"], res_base["means"], rtol=1e-12, atol=1e-12)
            assert np.allclose(res_p["cov"], res_base["cov"], rtol=1e-12, atol=1e-12)

            cov_p, df_p = linearized_covariance(
                Z_base[perm], clusters=clusters[perm], strata=strata[perm]
            )
            assert df_p == df_base
            assert np.allclose(cov_p, cov_base, rtol=1e-12, atol=1e-12)

    def test_lonely_psu_adjust_formula(self):
        """Estrato com 1 único conglomerado é centrado na média geral (survey.lonely.psu='adjust')."""
        from backend.analysis.stats_utils import linearized_covariance

        # Estrato 0: 2 PSUs (totais 1.0 e 3.0); Estrato 1: 1 lonely PSU (total 5.0)
        strata = np.array([0, 0, 1])
        clusters = np.array([10, 11, 20])
        Z = np.array([[1.0], [3.0], [5.0]])
        cov, df = linearized_covariance(Z, clusters=clusters, strata=strata)
        grand = float(np.mean([1.0, 3.0, 5.0]))  # 3.0
        # Estrato 0: n_h=2, mean=2.0 -> 2/1 * ((1-2)^2 + (3-2)^2) = 4.0
        # Estrato 1 (lonely): scale=1.0, centred on grand -> 1.0 * (5-grand)^2 = 4.0
        expected = 2.0 * ((1.0 - 2.0) ** 2 + (3.0 - 2.0) ** 2) + (5.0 - grand) ** 2
        assert cov[0, 0] == pytest.approx(expected)
        assert df == 1  # 3 PSUs - 2 strata = 1

    def test_34em_real_data_permutation_invariance(self):
        """Em TS_ALUNO_34EM (12 escolas multi-estrato no RJ), IC independe da ordem das linhas."""
        import duckdb
        from backend.config import ID_UF_RJ, SAEB_PARQUET_DIR

        pq = SAEB_PARQUET_DIR / "TS_ALUNO_34EM.parquet"
        con = duckdb.connect()
        try:
            df = con.execute(
                f"SELECT PROFICIENCIA_LP_SAEB AS prof, PESO_ALUNO_LP AS peso, "
                f"ID_ESCOLA AS escola, ESTRATO AS estrato FROM '{pq}' WHERE ID_UF = ?",
                [ID_UF_RJ],
            ).fetchnumpy()
        finally:
            con.close()

        from backend.analysis.stats_utils import to_float

        prof = to_float(df["prof"])
        peso = to_float(df["peso"])
        escola = np.asarray(df["escola"])
        estrato = np.asarray(df["estrato"])

        ci_orig = confidence_interval_mean(prof, peso, strata=estrato, clusters=escola)
        ci_rev = confidence_interval_mean(
            prof[::-1], peso[::-1], strata=estrato[::-1], clusters=escola[::-1]
        )
        assert ci_orig == pytest.approx(ci_rev, rel=1e-12, abs=1e-12)

    def test_wald_anova_design_based(self):
        """Wald ANOVA com correção Korn-Graubard detecta diferença entre grupos e exclui PSU único."""
        from backend.analysis.stats_utils import weighted_anova_oneway

        rng = np.random.default_rng(19)
        clusters = np.repeat(np.arange(30), 20)
        strata = clusters // 5
        groups = np.tile(["A", "B", "C"], len(clusters) // 3)
        shift = np.where(groups == "A", 0.0, np.where(groups == "B", 15.0, 30.0))
        values = 250.0 + shift + rng.normal(0, 10, len(clusters))
        weights = rng.uniform(0.8, 1.5, len(clusters))

        f_stat, p_val, df_b = weighted_anova_oneway(
            values, weights, groups, clusters=clusters, strata=strata
        )
        assert df_b == 2
        assert f_stat > 10.0 and p_val < 1e-4

        # Grupo 'D' concentrado em 1 única escola fica fora do teste (df_b continua 2)
        groups_with_singleton = groups.copy()
        groups_with_singleton[:5] = "D"
        f_stat2, p_val2, df_b2 = weighted_anova_oneway(
            values, weights, groups_with_singleton, clusters=clusters, strata=strata
        )
        assert df_b2 == 2
        assert np.isfinite(f_stat2) and p_val2 < 1e-3

    def test_pearson_weighted_srs_and_design(self):
        """Correlação de Pearson ponderada (SRS e desenho com domínios)."""
        from backend.analysis.stats_utils import pearson_weighted

        rng = np.random.default_rng(99)
        clusters = np.repeat(np.arange(40), 20)
        strata = clusters // 8
        x = rng.normal(0, 1, len(clusters))
        y = 2.0 * x + rng.normal(0, 0.5, len(clusters))
        w = rng.uniform(0.5, 2.5, len(clusters))

        r_srs, p_srs = pearson_weighted(x, y, w)
        r_des, p_des = pearson_weighted(x, y, w, clusters=clusters, strata=strata)
        assert r_srs == pytest.approx(r_des, abs=1e-12)
        assert r_des > 0.9 and p_des < 1e-6 and p_srs < 1e-6


class TestZeroAndInvalidWeightGuards:
    """Pesos todos zero ou negativos retornam NaN sem lançar ZeroDivisionError (F-01)."""

    def test_srs_functions_zero_weights(self):
        from backend.analysis.stats_utils import (
            pearson_weighted,
            weighted_anova_oneway,
            weighted_eta_squared,
            weighted_std,
        )

        v = np.array([10.0, 20.0, 30.0, 40.0])
        z = np.zeros(4)
        g = np.array(["a", "a", "b", "b"])
        s = np.array([0, 0, 1, 1])

        assert np.isnan(weighted_mean(v, z))
        assert np.isnan(weighted_variance(v, z))
        assert np.isnan(weighted_std(v, z))
        assert np.isnan(weighted_percentile(v, z, 50))
        assert all(np.isnan(x) for x in confidence_interval_mean(v, z))
        assert all(np.isnan(x) for x in confidence_interval_mean(v, z, strata=s))
        assert all(np.isnan(x) for x in weighted_ttest(v[:2], z[:2], v[2:], z[2:]))
        f_stat, p_val, df_b = weighted_anova_oneway(v, z, g)
        assert np.isnan(f_stat) and np.isnan(p_val) and df_b == 0
        assert np.isnan(weighted_eta_squared(v, z, g))
        r, p = pearson_weighted(v, v * 2, z)
        assert np.isnan(r) and np.isnan(p)

    def test_srs_functions_negative_weights(self):
        from backend.analysis.stats_utils import (
            pearson_weighted,
            weighted_anova_oneway,
            weighted_eta_squared,
        )

        v = np.array([10.0, 20.0, 30.0, 40.0])
        neg = np.array([1.0, -2.0, 3.0, 1.0])
        g = np.array(["a", "a", "b", "b"])

        assert np.isnan(weighted_mean(v, neg))
        assert np.isnan(weighted_variance(v, neg))
        assert np.isnan(weighted_percentile(v, neg, 50))
        assert all(np.isnan(x) for x in confidence_interval_mean(v, neg))
        assert all(np.isnan(x) for x in weighted_ttest(v[:2], neg[:2], v[2:], np.ones(2)))
        f_stat, p_val, _ = weighted_anova_oneway(v, neg, g)
        assert np.isnan(f_stat) and np.isnan(p_val)
        assert np.isnan(weighted_eta_squared(v, neg, g))
        r, p = pearson_weighted(v, v * 2, neg)
        assert np.isnan(r) and np.isnan(p)

    def test_chi_squared_and_weighted_frequency(self):
        from backend.analysis.stats_utils import chi_squared_test, weighted_frequency

        chi2, p, dof = chi_squared_test([[50, 10], [10, 50]])
        assert chi2 > 40 and p < 1e-6 and dof == 1
        chi2_bad, p_bad, dof_bad = chi_squared_test([[10]])
        assert np.isnan(chi2_bad) and np.isnan(p_bad) and dof_bad == 0

        freq = weighted_frequency([1.0, 2.0, 1.0], [2.0, 3.0, 5.0])
        assert freq[1.0][0] == pytest.approx(7.0) and freq[1.0][1] == pytest.approx(0.7)
        assert freq[2.0][0] == pytest.approx(3.0) and freq[2.0][1] == pytest.approx(0.3)
        assert weighted_frequency([1.0, 2.0], [-1.0, 2.0]) == {}
