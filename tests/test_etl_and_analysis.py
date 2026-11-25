"""Testes unitários e de regressão para módulos ETL, análise e conexão DB (F-02, F-04, F-08, F-09)."""

from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path

import duckdb
import openpyxl
import pytest

from backend.analysis import equity, proficiency, teacher
from backend.db import db_query
from backend.etl import codebook, precompute, tic_loader


# ---------------------------------------------------------------------------
# F-08: tic_loader._parse_numeric & parse_tic_sheet
# ---------------------------------------------------------------------------


class TestTicLoader:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (42, 42.0),
            (3.14, 3.14),
            ("92,4", 92.4),
            ("97.9657", 97.9657),
            ("1.234,5", 1234.5),
            ("1.234.567,89", 1234567.89),
            ("  0  ", 0.0),
        ],
    )
    def test_parse_numeric_valid(self, raw, expected):
        assert tic_loader._parse_numeric(raw) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            True,
            False,
            float("nan"),
            float("inf"),
            float("-inf"),
            "nan",
            "NaN",
            "inf",
            "-inf",
            "",
            "-",
            "*",
            "..",
            "…",
            "0*",
            "abc",
        ],
    )
    def test_parse_numeric_invalid_returns_none(self, raw):
        assert tic_loader._parse_numeric(raw) is None

    def test_parse_tic_sheet_simple_and_subitems(self):
        wb = openpyxl.Workbook()

        # Aba simples (A1): respostas na linha 3 mescladas com a linha 4
        ws = wb.active
        assert ws is not None
        ws.title = "A1"
        ws["A1"] = "A1 - ESCOLAS COM ACESSO À INTERNET"
        ws["A2"] = "Total de escolas de Ensino Fundamental e Médio"
        ws["C3"] = "Sim"
        ws["D3"] = "Não"
        ws.merge_cells("C3:C4")
        ws.merge_cells("D3:D4")
        ws["A5"] = "TOTAL"
        ws["B5"] = "TOTAL"
        ws["C5"] = "92,4"
        ws["D5"] = "7,6"
        ws["A6"] = "REGIÃO"
        ws["B6"] = "Sudeste"
        ws["C6"] = "98,0"
        ws["D6"] = "2,0"
        ws["A7"] = "REGIÃO"
        ws["B7"] = "Norte"
        ws["C7"] = "1.234,5"
        ws["D7"] = "-"
        ws["A8"] = "Fonte: Cetic.br"
        ws["C8"] = 999  # após 'Fonte:', não deve ser lido

        rows = tic_loader.parse_tic_sheet(ws, "A1", "proporcao")
        assert len(rows) == 5
        assert all(r["indicador"] == "A1" for r in rows)
        assert rows[0]["titulo"] == "ESCOLAS COM ACESSO À INTERNET"
        norte_sim = next(r for r in rows if r["valor_corte"] == "Norte" and r["resposta"] == "Sim")
        assert norte_sim["valor"] == pytest.approx(1234.5)
        assert all(r["valor"] != 999 for r in rows)

        # Aba com subitens (E6): linha 3 mesclada horizontalmente + linha 4 com respostas
        ws2 = wb.create_sheet("E6")
        ws2["A1"] = "E6 - USO DE IA NA GESTÃO"
        ws2["A2"] = "Total de escolas"
        ws2["C3"] = "Sistemas de IA"
        ws2.merge_cells("C3:D3")
        ws2["C4"] = "Sim"
        ws2["D4"] = "Não"
        ws2["A5"] = "TOTAL"
        ws2["B5"] = "TOTAL"
        ws2["C5"] = 19.5
        ws2["D5"] = 80.5

        rows2 = tic_loader.parse_tic_sheet(ws2, "E6", "proporcao")
        assert len(rows2) == 2
        assert rows2[0]["item"] == "Sistemas de IA"
        assert rows2[0]["resposta"] == "Sim"
        assert rows2[0]["valor"] == pytest.approx(19.5)
        wb.close()


# ---------------------------------------------------------------------------
# F-08: codebook._parse_r_values
# ---------------------------------------------------------------------------


class TestCodebook:
    def test_parse_r_values_preserves_empty_string(self):
        parsed = codebook._parse_r_values("'', \"\", 'A', \"B\", 1, 2")
        assert parsed == ["", "", "A", "B", "1", "2"]

    def test_extract_factor_definitions_with_empty_level(self):
        script = (
            "# TS$COL <- factor(TS$COL,\n"
            "#   levels = c('', 'A', 'B'),\n"
            "#   labels = c('Branco', 'Sim', 'Não'))\n"
        )
        defs = codebook._extract_factor_definitions(script, "TS")
        assert defs["COL"]["levels"] == ["", "A", "B"]
        assert defs["COL"]["labels"] == ["Branco", "Sim", "Não"]

    def test_extract_factor_definitions_with_parentheses_inside_quotes(self):
        """R-04d: labels entre aspas com ')' interno não podem ser truncadas."""
        script = (
            "# TS_ESCOLA$TP_ETAPA <- factor(TS_ESCOLA$TP_ETAPA,\n"
            "#   levels = c('1', '2', '3'),\n"
            "#   labels = c('Ensino Fundamental (anos iniciais)', "
            "\"Ensino Médio (1ª a 3ª série)\", 'EJA (presencial)'))\n"
        )
        defs = codebook._extract_factor_definitions(script, "TS_ESCOLA")
        assert defs["TP_ETAPA"]["levels"] == ["1", "2", "3"]
        assert defs["TP_ETAPA"]["labels"] == [
            "Ensino Fundamental (anos iniciais)",
            "Ensino Médio (1ª a 3ª série)",
            "EJA (presencial)",
        ]


# ---------------------------------------------------------------------------
# F-02: precompute restringe colunas de questionário às chaves do dicionário
# ---------------------------------------------------------------------------


def test_precompute_questionnaire_excludes_open_columns_and_supports_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pq_dir = tmp_path / "saeb"
    pq_dir.mkdir()
    prof_pq = pq_dir / "TS_PROFESSOR.parquet"
    dir_pq = pq_dir / "TS_DIRETOR.parquet"

    setup_con = duckdb.connect()
    try:
        setup_con.execute(f"""
            COPY (
                SELECT 33 AS ID_UF, 'A' AS TX_Q001, 'texto livre aberto 1' AS TX_Q148
                UNION ALL
                SELECT 33 AS ID_UF, 'B' AS TX_Q001, 'texto livre aberto 2' AS TX_Q148
            ) TO '{prof_pq}' (FORMAT PARQUET)
        """)
        setup_con.execute(f"""
            COPY (
                SELECT 33 AS ID_UF, 'B' AS TX_Q194, 'comentario livre' AS TX_Q089
            ) TO '{dir_pq}' (FORMAT PARQUET)
        """)
    finally:
        setup_con.close()

    dict_dir = tmp_path / "processed"
    dict_dir.mkdir()
    (dict_dir / "saeb_questionnaire_dict.json").write_text(
        json.dumps({
            "TS_PROFESSOR": {"TX_Q001": {"text": "Sexo", "options": {"A": "M", "B": "F"}}},
            "TS_DIRETOR": {"TX_Q194": {"text": "C&T", "options": {"A": "Não", "B": "Sim"}}},
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(precompute, "SAEB_PARQUET_DIR", pq_dir)
    monkeypatch.setattr(precompute, "PROCESSED_DIR", dict_dir)

    con = duckdb.connect()
    try:
        precompute._precompute_questionnaire_professor_rj(con)
        precompute._precompute_questionnaire_diretor_rj(con)

        prof_qs = {r[0] for r in con.execute("SELECT DISTINCT questao FROM quest_professor_rj").fetchall()}
        dir_qs = {r[0] for r in con.execute("SELECT DISTINCT questao FROM quest_diretor_rj").fetchall()}
        assert prof_qs == {"TX_Q001"}
        assert dir_qs == {"TX_Q194"}

        # Fallback seguro quando o JSON não existe: inclui todas as colunas VARCHAR TX_Q*
        (dict_dir / "saeb_questionnaire_dict.json").unlink()
        precompute._precompute_questionnaire_professor_rj(con)
        prof_qs_fallback = {
            r[0] for r in con.execute("SELECT DISTINCT questao FROM quest_professor_rj").fetchall()
        }
        assert prof_qs_fallback == {"TX_Q001", "TX_Q148"}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# F-04 & F-09: equity, proficiency, teacher e thread-safety do db
# ---------------------------------------------------------------------------


class TestAnalysisModules:
    def test_equity_inse_correlation_and_location_gap(self):
        inse = equity.get_inse_correlation("9EF", "LP")
        assert inse["pearson_r"] is not None and inse["pearson_r"] > 0.2
        assert inse["p_value"] is not None and inse["p_value"] < 1e-4
        assert inse["n"] > 50000
        levels = inse["means_by_level"]
        assert len(levels) == 8
        assert levels[-1]["mean"] > levels[0]["mean"]

        loc = equity.get_location_gap("9EF", "LP")
        assert loc["urban_rural"]["urbana"]["n"] > 0
        assert loc["urban_rural"]["rural"]["n"] > 0
        assert loc["urban_rural"]["gap"] is not None
        assert loc["capital_interior"]["capital"]["n"] > 0
        assert loc["capital_interior"]["interior"]["n"] > 0

    @pytest.mark.parametrize(("serie", "disciplina"), [("2EF", "LP"), ("34EM", "CH"), ("INVALID", "LP")])
    def test_equity_rejects_invalid_serie_disciplina(self, serie, disciplina):
        with pytest.raises(ValueError):
            equity.get_public_private_gap(serie, disciplina)

    def test_proficiency_distribution_and_rede(self):
        dist = proficiency.get_proficiency_distribution("9EF", "LP")
        assert dist["n"] > 50000
        assert len(dist["counts"]) == 30
        assert 200 < dist["mean"] < 320
        assert dist["q25"] < dist["median"] < dist["q75"]

        rede = proficiency.get_proficiency_by_rede("9EF", "LP")
        assert rede["gap"] > 0 and rede["cohens_d"] > 0

        with pytest.raises(ValueError):
            proficiency.get_proficiency_distribution("34EM", "CH")
        with pytest.raises(ValueError):
            proficiency.get_proficiency_distribution("2EF", "CN")

    def test_teacher_profile_training_and_formation_json_serializable(self):
        profile = teacher.get_teacher_profile_rj()
        assert profile["total_teachers"] > 0
        assert len(profile["gender"]) >= 2
        assert len(profile["education"]) >= 3

        training = teacher.get_teacher_tech_training_rj()
        assert training["total_respondents"] == profile["total_teachers"]
        assert len(training["tech_training"]) >= 4
        assert len(training["tech_training_need"]) >= 4

        formation = teacher.get_formation_vs_proficiency_rj("9EF", "LP")
        assert len(formation["by_formation"]) >= 3
        for item in formation["by_formation"]:
            assert type(item["formation_code"]) is str
            assert type(item["formation_label"]) is str
            assert item["mean_proficiency"] is not None
            assert item["n_pairs"] > 0
        # Deve ser 100% serializável em JSON (sem np.str_ ou NaN)
        dumped = json.dumps(formation, allow_nan=False)
        assert math.isfinite(json.loads(dumped)["by_formation"][0]["mean_proficiency"])

        with pytest.raises(ValueError):
            teacher.get_formation_vs_proficiency_rj("2EF", "LP")
        with pytest.raises(ValueError):
            teacher.get_formation_vs_proficiency_rj("34EM", "CH")

    def test_db_query_thread_safe(self):
        def _run(_):
            rows = db_query("SELECT COUNT(*) AS c FROM kpi_rj")
            return rows[0]["c"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            counts = list(pool.map(_run, range(12)))
        assert counts == [3] * 12

    def test_teacher_deduplicates_turma_professor_pairs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Pares duplicados (ID_TURMA, ID_PROFESSOR) devem contar apenas uma vez (F-04)."""
        from backend.analysis import cross_analysis

        pq_dir = tmp_path / "saeb"
        pq_dir.mkdir()
        prof_pq = pq_dir / "TS_PROFESSOR.parquet"
        aluno_pq = pq_dir / "TS_ALUNO_9EF.parquet"

        con = duckdb.connect()
        try:
            # Turma 10: professor 1 aparece DUPLICADO (TX_Q029='D', TX_Q020='C') + prof 2 ('A', 'B')
            # Turma 20: professor 3 aparece uma vez ('A', 'B')
            con.execute(f"""
                COPY (
                    SELECT 33 AS ID_UF, 10 AS ID_TURMA, 1 AS ID_PROFESSOR, 1 AS IN_PREENCHIMENTO_QUESTIONARIO, 'D' AS TX_Q029, 'C' AS TX_Q020
                    UNION ALL
                    SELECT 33, 10, 1, 1, 'D', 'C'
                    UNION ALL
                    SELECT 33, 10, 2, 1, 'A', 'B'
                    UNION ALL
                    SELECT 33, 20, 3, 1, 'A', 'B'
                ) TO '{prof_pq}' (FORMAT PARQUET)
            """)
            con.execute(f"""
                COPY (
                    SELECT 33 AS ID_UF, 10 AS ID_TURMA, 1001 AS ID_ALUNO, 100 AS ID_ESCOLA, 1 AS ESTRATO, 300.0 AS PROFICIENCIA_LP_SAEB, 2.0 AS PESO_ALUNO_LP
                    UNION ALL
                    SELECT 33, 10, 1002, 100, 1, 300.0, 2.0
                    UNION ALL
                    SELECT 33, 20, 2001, 200, 1, 200.0, 2.0
                    UNION ALL
                    SELECT 33, 20, 2002, 200, 1, 200.0, 2.0
                ) TO '{aluno_pq}' (FORMAT PARQUET)
            """)
        finally:
            con.close()

        monkeypatch.setattr(cross_analysis, "_PROFESSOR_PARQUET", str(prof_pq))
        monkeypatch.setattr(cross_analysis, "SAEB_PARQUET_DIR", pq_dir)
        cross_analysis._teacher_tech_impact_cached.cache_clear()
        monkeypatch.setattr(teacher, "_PROFESSOR_PARQUET", str(prof_pq))
        monkeypatch.setattr(teacher, "SAEB_PARQUET_DIR", pq_dir)

        try:
            # Sem deduplicar, turma 10 teria n_prof=3 (peso 2/3 para 'A' e 4/3 para 'D'),
            # dando média de 'A' = (2*(2/3)*300 + 2*2*200) / (4/3 + 4) = 225.0.
            # Com deduplicação, turma 10 tem n_prof=2 (peso 1.0 para 'A' e 1.0 para 'D'),
            # dando média de 'A' = (2*1*300 + 2*2*200) / (2 + 4) = 233.333...
            tech_res = cross_analysis.get_teacher_tech_impact("9EF", "LP", "TX_Q029", uf=33)
            grp_a = next(g for g in tech_res["groups"] if g["code"] == "A")
            assert grp_a["mean"] == pytest.approx(1400.0 / 6.0, rel=1e-9)

            form_res = teacher.get_formation_vs_proficiency_rj("9EF", "LP", uf=33)
            form_c = next(x for x in form_res["by_formation"] if x["formation_code"] == "C")
            # Apenas 2 pares aluno-professor (não 4!) para professor 1 na turma 10
            assert form_c["n_pairs"] == 2
            form_b = next(x for x in form_res["by_formation"] if x["formation_code"] == "B")
            assert form_b["mean_proficiency"] == pytest.approx(1400.0 / 6.0, rel=1e-9)
        finally:
            cross_analysis._teacher_tech_impact_cached.cache_clear()

    def test_questionnaire_deduplicates_unique_professor_and_school_r01(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """R-01: questionários descritivos deduplicam por ID_PROFESSOR (turma principal) e ID_ESCOLA."""
        pq_dir = tmp_path / "saeb"
        pq_dir.mkdir()
        prof_pq = pq_dir / "TS_PROFESSOR.parquet"
        dir_pq = pq_dir / "TS_DIRETOR.parquet"

        con = duckdb.connect()
        try:
            # Docente 10 leciona em 2 turmas: outra_turma=1 ('A') e outra_turma=0 ('B' -> principal!).
            # Docente 20 tem IN_PREENCHIMENTO_QUESTIONARIO=0 (excluído).
            # Docente 30 tem 1 turma preenchida ('A').
            con.execute(f"""
                COPY (
                    SELECT 33 AS ID_UF, 10 AS ID_PROFESSOR, 100 AS ID_ESCOLA, 2 AS ID_TURMA,
                           1 AS IN_PREENCHIMENTO_QUESTIONARIO, 1 AS IN_PREENCHIMENTO_OUTRA_TURMA,
                           'A' AS TX_Q001, 'B' AS TX_Q020, 'C' AS TX_Q029, 'D' AS TX_Q037
                    UNION ALL
                    SELECT 33, 10, 100, 1, 1, 0, 'B', 'C', 'D', 'A'
                    UNION ALL
                    SELECT 33, 20, 100, 3, 0, 0, 'A', 'A', 'A', 'A'
                    UNION ALL
                    SELECT 33, 30, 200, 4, 1, 0, 'A', 'B', 'A', 'B'
                ) TO '{prof_pq}' (FORMAT PARQUET)
            """)
            # Escola 500 repetida nas séries 5 e 9; Escola 600 não preencheu (IN_PREENCHIMENTO=0).
            con.execute(f"""
                COPY (
                    SELECT 33 AS ID_UF, 500 AS ID_ESCOLA, 9 AS ID_SERIE,
                           1 AS IN_PREENCHIMENTO_QUESTIONARIO, 'A' AS TX_Q194
                    UNION ALL
                    SELECT 33, 500, 5, 1, 'B'
                    UNION ALL
                    SELECT 33, 600, 5, 0, 'A'
                ) TO '{dir_pq}' (FORMAT PARQUET)
            """)
        finally:
            con.close()

        dict_dir = tmp_path / "processed"
        dict_dir.mkdir()
        (dict_dir / "saeb_questionnaire_dict.json").write_text(
            json.dumps({
                "TS_PROFESSOR": {"TX_Q001": {"text": "Sexo", "options": {"A": "M", "B": "F"}}},
                "TS_DIRETOR": {"TX_Q194": {"text": "C&T", "options": {"A": "Não", "B": "Sim"}}},
            }),
            encoding="utf-8",
        )

        monkeypatch.setattr(precompute, "SAEB_PARQUET_DIR", pq_dir)
        monkeypatch.setattr(precompute, "PROCESSED_DIR", dict_dir)
        monkeypatch.setattr(teacher, "_PROFESSOR_PARQUET", str(prof_pq))

        mem = duckdb.connect()
        try:
            precompute._precompute_questionnaire_professor_rj(mem)
            precompute._precompute_questionnaire_diretor_rj(mem)

            prof_counts = dict(
                mem.execute("SELECT resposta, contagem FROM quest_professor_rj WHERE questao = 'TX_Q001'").fetchall()
            )
            # Docente 10 entra com a turma principal ('B') e Docente 30 com ('A') -> 1 e 1
            assert prof_counts == {"A": 1, "B": 1}

            dir_counts = dict(
                mem.execute("SELECT resposta, contagem FROM quest_diretor_rj WHERE questao = 'TX_Q194'").fetchall()
            )
            # Escola 500 entra 1 única vez pela menor ID_SERIE=5 ('B')
            assert dir_counts == {"B": 1}
        finally:
            mem.close()

        prof_desc = teacher.get_teacher_profile_rj(uf=33)
        assert prof_desc["total_teachers"] == 2
        assert {g["code"]: g["count"] for g in prof_desc["gender"]} == {"A": 1, "B": 1}
        usage_desc = teacher.get_teacher_tech_usage_rj(uf=33)
        assert usage_desc["total_respondents"] == 2
        assert {g["code"]: g["count"] for g in usage_desc["tech_training"]} == {"A": 1, "D": 1}

    def test_real_teacher_profile_counts_unique_teachers_r01(self):
        """Nos dados reais do RJ, get_teacher_profile_rj retorna os 10.239 docentes únicos."""
        profile = teacher.get_teacher_profile_rj()
        assert profile["total_teachers"] == 10239
        assert teacher.get_teacher_tech_usage_rj()["total_respondents"] == 10239

    def test_3em_vs_4em_filters_id_serie_12_and_13_r04a(self):
        """R-04a: 3EM filtra ID_SERIE=12 e 4EM filtra ID_SERIE=13 em todos os 4 módulos analíticos."""
        from backend.analysis import cross_analysis

        dist_3 = proficiency.get_proficiency_distribution("3EM", "LP")
        dist_4 = proficiency.get_proficiency_distribution("4EM", "LP")
        dist_34 = proficiency.get_proficiency_distribution("34EM", "LP")
        assert dist_3["n"] > 50000
        assert 1000 < dist_4["n"] < 15000
        assert dist_3["n"] + dist_4["n"] == dist_34["n"]

        eq_3 = equity.get_public_private_gap("3EM", "LP")
        eq_4 = equity.get_public_private_gap("4EM", "LP")
        eq_34 = equity.get_public_private_gap("34EM", "LP")
        n_eq3 = eq_3["publica"]["n"] + eq_3["privada"]["n"]
        n_eq4 = eq_4["publica"]["n"] + eq_4["privada"]["n"]
        n_eq34 = eq_34["publica"]["n"] + eq_34["privada"]["n"]
        assert n_eq3 + n_eq4 == n_eq34

        form_3 = teacher.get_formation_vs_proficiency_rj("3EM", "LP")
        form_4 = teacher.get_formation_vs_proficiency_rj("4EM", "LP")
        form_34 = teacher.get_formation_vs_proficiency_rj("34EM", "LP")
        pairs_3 = sum(x["n_pairs"] for x in form_3["by_formation"])
        pairs_4 = sum(x["n_pairs"] for x in form_4["by_formation"])
        pairs_34 = sum(x["n_pairs"] for x in form_34["by_formation"])
        assert pairs_3 > 0 and pairs_4 > 0
        assert pairs_3 + pairs_4 == pairs_34

        cross_3 = cross_analysis.get_student_tech_gap("3EM", "LP", "TX_RESP_Q13b")
        cross_4 = cross_analysis.get_student_tech_gap("4EM", "LP", "TX_RESP_Q13b")
        cross_34 = cross_analysis.get_student_tech_gap("34EM", "LP", "TX_RESP_Q13b")
        nc_3 = sum(g["n"] for g in cross_3["groups"])
        nc_4 = sum(g["n"] for g in cross_4["groups"])
        nc_34 = sum(g["n"] for g in cross_34["groups"])
        assert nc_3 + nc_4 == nc_34
