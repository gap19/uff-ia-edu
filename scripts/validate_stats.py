#!/usr/bin/env python3
"""
Validação cruzada de estatísticas calculadas pelo dashboard.

Verifica a consistência interna dos dados e compara com valores de referência
conhecidos (médias SAEB publicadas pelo INEP, gaps validados manualmente).

Execução: python scripts/validate_stats.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
from backend.config import DUCKDB_PATH, ID_UF_RJ

# ───────────────────────────────────────────────────────────────────────
# Conexão
# ───────────────────────────────────────────────────────────────────────

def get_db():
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def query(db, sql, params=None):
    result = db.execute(sql, params or [])
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row)) for row in result.fetchall()]


# ───────────────────────────────────────────────────────────────────────
# Validações
# ───────────────────────────────────────────────────────────────────────

passed = 0
failed = 0
warnings = 0


def check(description, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✓ {description}")
        passed += 1
    else:
        print(f"  ✗ {description} — {detail}")
        failed += 1


def warn(description, detail=""):
    global warnings
    print(f"  ⚠ {description} — {detail}")
    warnings += 1


def validate_tables(db):
    """1. Verificar que todas as 14 tabelas pré-computadas existem e não estão vazias."""
    print("\n[1] Tabelas pré-computadas")
    tables = [t[0] for t in db.execute("SHOW TABLES").fetchall()]
    expected = [
        "prof_by_uf_serie_disc", "prof_by_inse", "prof_by_location_rj",
        "prof_niveis_rj", "prof_niveis_nacional", "escola_inse_rj",
        "quest_aluno_rj", "quest_professor_rj", "quest_diretor_rj",
        "kpi_rj", "kpi_escolas_rj", "tic_indicadores",
        "cross_aluno_tech_rj", "cross_digital_index_rj",
    ]
    for t in expected:
        exists = t in tables
        check(f"Tabela '{t}' existe", exists, f"Faltando: {t}")
        if exists:
            row = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            n_rows = int(row[0]) if row is not None else 0
            check(f"Tabela '{t}' não está vazia ({n_rows:,} linhas)", n_rows > 0, "Tabela vazia")


def validate_proficiency_ranges(db):
    """2. Proficiências devem estar em faixas plausíveis da escala SAEB."""
    print("\n[2] Faixas de proficiência (escala SAEB)")
    rows = query(db,
        "SELECT serie, disciplina, MIN(media_proficiencia) AS min_p, "
        "MAX(media_proficiencia) AS max_p, AVG(media_proficiencia) AS avg_p "
        "FROM prof_by_uf_serie_disc GROUP BY serie, disciplina"
    )
    check("Séries 5EF, 9EF e 34EM presentes em prof_by_uf_serie_disc",
          {"5EF", "9EF", "34EM"}.issubset({r["serie"] for r in rows}),
          f"Encontradas: {sorted({r['serie'] for r in rows})}")
    for r in rows:
        s, d = r["serie"], r["disciplina"]
        minp, maxp = r["min_p"], r["max_p"]
        # Escala SAEB: tipicamente 100-400 para todas as séries
        check(f"{s}/{d}: min={minp:.1f}, max={maxp:.1f} dentro [100, 400]",
              100 < minp and maxp < 400,
              "Fora da faixa esperada")


def validate_rj_means(db):
    """3. Médias do RJ devem ser plausíveis (referência: SAEB 2023 publicado)."""
    print("\n[3] Médias do RJ (valores de referência)")
    rows = query(db,
        "SELECT serie, disciplina, rede, media_proficiencia "
        "FROM prof_by_uf_serie_disc WHERE ID_UF = ? "
        "ORDER BY serie, disciplina, rede",
        [ID_UF_RJ]
    )
    # Referências aproximadas (SAEB 2023, publicadas pelo INEP):
    # 5EF LP: pública ~206, privada ~240
    # 9EF LP: pública ~253, privada ~282
    # 34EM LP: pública ~262, privada ~307
    refs = {
        ("5EF", "LP", 1): (195, 220, "pública 5EF LP ~206"),
        ("5EF", "LP", 0): (225, 260, "privada 5EF LP ~240"),
        ("9EF", "LP", 1): (240, 270, "pública 9EF LP ~253"),
        ("9EF", "LP", 0): (270, 300, "privada 9EF LP ~282"),
        ("34EM", "LP", 1): (250, 280, "pública 34EM LP ~262"),
        ("34EM", "LP", 0): (290, 325, "privada 34EM LP ~307"),
        ("5EF", "MT", 1): (195, 230, "pública 5EF MT ~215"),
        ("5EF", "MT", 0): (230, 270, "privada 5EF MT ~250"),
        ("9EF", "MT", 1): (245, 275, "pública 9EF MT ~258"),
        ("9EF", "MT", 0): (275, 310, "privada 9EF MT ~292"),
        ("34EM", "MT", 1): (245, 275, "pública 34EM MT ~256"),
        ("34EM", "MT", 0): (285, 320, "privada 34EM MT ~302"),
    }
    by_key = {(r["serie"], r["disciplina"], r["rede"]): r["media_proficiencia"] for r in rows}
    for key, (lo, hi, desc) in refs.items():
        val = by_key.get(key)
        check(f"RJ {desc}: {f'{val:.1f}' if val is not None else 'ausente'} ∈ [{lo}, {hi}]",
              val is not None and lo <= val <= hi,
              f"Valor {val} ausente ou fora da faixa esperada")


def validate_gap_pub_priv(db):
    """4. Gap pública/privada deve ser positivo e significativo."""
    print("\n[4] Gap pública vs privada")
    rows = query(db,
        "SELECT serie, disciplina, rede, media_proficiencia "
        "FROM prof_by_uf_serie_disc WHERE ID_UF = ?",
        [ID_UF_RJ]
    )
    by_key = {}
    for r in rows:
        by_key.setdefault((r["serie"], r["disciplina"]), {})[r["rede"]] = r["media_proficiencia"]

    for (s, d), redes in sorted(by_key.items()):
        pub = redes.get(1)
        priv = redes.get(0)
        if pub and priv:
            gap = priv - pub
            check(f"{s}/{d}: gap = {gap:.1f} pts (privada - pública > 0)",
                  gap > 0,
                  f"Gap negativo ou zero: {gap:.1f}")


def validate_inse_monotonic(db):
    """5. Proficiência deve crescer com nível INSE (tendência geral)."""
    print("\n[5] Monotonia INSE x proficiência")
    rows = query(db,
        "SELECT serie, disciplina, nivel_inse, media_proficiencia "
        "FROM prof_by_inse ORDER BY serie, disciplina, nivel_inse"
    )
    current = {}
    for r in rows:
        key = (r["serie"], r["disciplina"])
        if key not in current:
            current[key] = []
        current[key].append((r["nivel_inse"], r["media_proficiencia"]))

    for (s, d), levels in sorted(current.items()):
        if len(levels) < 3:
            continue
        vals = [v for _, v in levels if v is not None]
        if len(vals) < 3:
            continue
        # Tendência geral: último > primeiro
        trend_up = vals[-1] > vals[0]
        check(f"{s}/{d}: INSE nível mais alto ({vals[-1]:.1f}) > mais baixo ({vals[0]:.1f})",
              trend_up,
              "Tendência decrescente inesperada")


def validate_wifi_gap(db):
    """6. Gap WiFi validado: ~19 pts para 9EF LP RJ."""
    print("\n[6] Gap WiFi (9EF LP RJ) — valor de referência: ~19 pts")
    rows = query(db,
        "SELECT tech_response, media_proficiencia, n_alunos "
        "FROM cross_aluno_tech_rj "
        "WHERE serie = '9EF' AND disciplina = 'LP' AND tech_variable = 'TX_RESP_Q13b' "
        "AND nivel_inse IS NULL "
        "ORDER BY tech_response"
    )
    if len(rows) >= 2:
        by_resp = {r["tech_response"]: r for r in rows}
        no_wifi = by_resp.get("A", {}).get("media_proficiencia")
        yes_wifi = by_resp.get("B", {}).get("media_proficiencia")
        if no_wifi and yes_wifi:
            gap = yes_wifi - no_wifi
            check(f"Gap WiFi = {gap:.1f} pts (ref: ~19 pts, tolerância ±5)",
                  14 < gap < 25,
                  "Gap fora da tolerância")
            n_no = by_resp["A"]["n_alunos"]
            n_yes = by_resp["B"]["n_alunos"]
            check(f"N sem WiFi = {n_no:,} (ref: ~9.5K)",
                  5000 < n_no < 20000)
            check(f"N com WiFi = {n_yes:,} (ref: ~102K)",
                  80000 < n_yes < 130000)
        else:
            check("Dados de WiFi A/B presentes em cross_aluno_tech_rj", False,
                  "Respostas A e/ou B ausentes")
    else:
        check("Tabela cross_aluno_tech_rj tem dados de WiFi (9EF LP)", False,
              f"Apenas {len(rows)} linha(s) encontrada(s)")

    series_cross = {
        r["serie"] for r in query(db, "SELECT DISTINCT serie FROM cross_aluno_tech_rj")
    }
    check("Séries 5EF, 9EF e 34EM presentes em cross_aluno_tech_rj",
          {"5EF", "9EF", "34EM"}.issubset(series_cross),
          f"Encontradas: {sorted(series_cross)}")


def validate_sample_sizes(db):
    """7. Tamanhos amostrais devem ser plausíveis."""
    print("\n[7] Tamanhos amostrais")
    kpi = query(db, "SELECT * FROM kpi_rj")
    check("kpi_rj contém 5EF, 9EF e 34EM",
          {"5EF", "9EF", "34EM"}.issubset({r["serie"] for r in kpi}),
          f"Encontradas: {sorted({r['serie'] for r in kpi})}")
    for r in kpi:
        s = r["serie"]
        n = r["total_alunos"]
        # RJ deve ter pelo menos 50K alunos por série (5EF, 9EF) e pelo menos 30K para EM
        min_n = 30000 if "EM" in s or "34" in s else 50000
        check(f"{s}: {n:,} alunos ≥ {min_n:,}",
              n >= min_n,
              f"Amostra pequena: {n}")


def validate_tic_indicators(db):
    """8. Indicadores TIC devem estar em [0, 100]."""
    print("\n[8] Indicadores TIC (proporções em [0, 100])")
    rows = query(db,
        "SELECT indicador, MIN(valor) AS min_v, MAX(valor) AS max_v "
        "FROM tic_indicadores WHERE tipo = 'proporcao' "
        "GROUP BY indicador ORDER BY indicador"
    )
    all_ok = True
    for r in rows:
        if r["min_v"] is not None and (r["min_v"] < 0 or r["max_v"] > 100):
            check(f"{r['indicador']}: [{r['min_v']:.1f}, {r['max_v']:.1f}] ⊂ [0, 100]",
                  False, "Valor fora da faixa")
            all_ok = False
    if all_ok and rows:
        check(f"Todos os {len(rows)} indicadores TIC em [0, 100]", True)
    elif not rows:
        check("Indicadores TIC encontrados em tic_indicadores", False, "Tabela vazia")
        return

    # Estrutura: as respostas de cada indicador/subitem somam ~100% (TOTAL e Sudeste)
    bad = query(db,
        "SELECT indicador, item, valor_corte, SUM(valor) AS s FROM tic_indicadores "
        "WHERE tipo = 'proporcao' AND valor_corte IN ('TOTAL', 'Sudeste') "
        "GROUP BY ALL HAVING abs(SUM(valor) - 100) > 0.6"
    )
    check("Respostas TIC somam 100% por indicador/subitem (Brasil e Sudeste)",
          not bad, f"{len(bad)} grupos fora: {bad[:3]}")

    # Valores de referência das tabelas oficiais do Cetic.br
    a1 = query(db,
        "SELECT valor_corte, valor FROM tic_indicadores WHERE indicador = 'A1' "
        "AND tipo = 'proporcao' AND resposta = 'Sim' AND valor_corte IN ('TOTAL', 'Sudeste')"
    )
    a1 = {r["valor_corte"]: r["valor"] for r in a1}
    check(f"A1 (acesso à internet) Brasil = {a1.get('TOTAL')}% (ref.: 92,4%)",
          abs((a1.get("TOTAL") or 0) - 92.409) < 0.01)
    check(f"A1 (acesso à internet) Sudeste = {a1.get('Sudeste')}% (ref.: 98,0%)",
          abs((a1.get("Sudeste") or 0) - 97.9657) < 0.01)

    # Catálogo do dashboard: todo indicador curado precisa existir
    from backend.analysis.tic import TIC_GROUPS, _match
    rows_sim = query(db,
        "SELECT indicador, item, resposta FROM tic_indicadores "
        "WHERE tipo = 'proporcao' AND valor_corte = 'TOTAL'"
    )
    missing = [
        f"{spec['code']}:{spec.get('item', '')}"
        for cfg in TIC_GROUPS.values() for spec in cfg["indicators"]
        if not any(_match(spec, r) for r in rows_sim)
    ]
    check("Catálogo TIC do dashboard encontrado nas tabelas", not missing, f"Faltando: {missing}")


def validate_digital_index(db):
    """9. Índice digital composto: faixas devem estar corretas."""
    print("\n[9] Índice digital composto")
    series_di = {
        r["serie"] for r in query(db, "SELECT DISTINCT serie FROM cross_digital_index_rj")
    }
    check("Séries 5EF, 9EF e 34EM presentes em cross_digital_index_rj",
          {"5EF", "9EF", "34EM"}.issubset(series_di),
          f"Encontradas: {sorted(series_di)}")

    for serie in ("5EF", "9EF", "34EM"):
        rows = query(db,
            "SELECT digital_index, faixa_digital, media_proficiencia, n_alunos "
            "FROM cross_digital_index_rj "
            "WHERE serie = ? AND disciplina = 'LP' AND nivel_inse IS NULL "
            "ORDER BY digital_index",
            [serie],
        )
        if not rows:
            check(f"cross_digital_index_rj possui linhas para {serie}/LP", False, "Tabela vazia")
            continue
        indices = [r["digital_index"] for r in rows]
        check(f"{serie}/LP: índice mín = {min(indices)}, máx = {max(indices)} (esperado: 0-8)",
              min(indices) >= 0 and max(indices) <= 8)
        faixas = set(r["faixa_digital"] for r in rows)
        check(f"{serie}/LP: faixas presentes = {sorted(faixas)}",
              faixas == {"Baixo", "Medio", "Alto"},
              f"Esperado Baixo/Medio/Alto, obtido {sorted(faixas)}")
        vals = [r["media_proficiencia"] for r in rows if r["media_proficiencia"]]
        check(f"{serie}/LP: gradiente índice alto ({vals[-1]:.1f}) > baixo ({vals[0]:.1f})",
              len(vals) >= 3 and vals[-1] > vals[0])


def validate_proficiency_levels_and_escola_inse(db):
    """10. Níveis de proficiência (incluindo 34EM) e escola_inse_rj."""
    print("\n[10] Níveis de proficiência (5EF, 9EF, 34EM) e INSE escolar")
    for tbl in ("prof_niveis_rj", "prof_niveis_nacional"):
        rows = query(db, f"SELECT * FROM {tbl}")
        check(f"{tbl} possui linhas", len(rows) > 0)
        if not rows:
            continue
        row = next((r for r in rows if r.get("rede") == 1), rows[0])
        for prefix, max_n in [
            ("lp5", 9),
            ("mt5", 10),
            ("lp9", 8),
            ("mt9", 9),
            ("lp34em", 8),
            ("mt34em", 10),
        ]:
            cols = [f"nivel_{n}_{prefix}" for n in range(max_n + 1)]
            present = all(c in row and row[c] is not None for c in cols)
            total_pct = sum(float(row[c] or 0.0) for c in cols if c in row)
            check(
                f"{tbl} ({prefix}): níveis 0..{max_n} presentes e somam ~100% ({total_pct:.1f}%)",
                present and 98.0 <= total_pct <= 102.0,
                f"present={present}, soma={total_pct:.2f}%",
            )

    inse_rows = query(db, "SELECT * FROM escola_inse_rj ORDER BY NIVEL_SOCIO_ECONOMICO")
    check("escola_inse_rj possui níveis socioeconômicos do RJ", len(inse_rows) >= 5)
    if inse_rows:
        cols_ok = all(
            col in inse_rows[0]
            for col in ("media_5ef_lp", "media_5ef_mt", "media_9ef_lp", "media_9ef_mt", "media_em_lp", "media_em_mt")
        )
        total_esc = sum(int(r["n_escolas"]) for r in inse_rows)
        check(
            f"escola_inse_rj tem colunas 5EF/9EF/EM e total de escolas plausível ({total_esc:,})",
            cols_ok and 2000 <= total_esc <= 4215,
        )


def validate_questionnaire_deduplication(db):
    """11. Deduplicação descritiva R-01 e exclusão de colunas abertas F-02."""
    print("\n[11] Questionários descritivos deduplicados (R-01 / F-02)")
    from backend.config import SAEB_PARQUET_DIR

    pq_con = duckdb.connect()
    try:
        dir_row = pq_con.execute(
            f"SELECT COUNT(DISTINCT ID_ESCOLA) FROM '{SAEB_PARQUET_DIR / 'TS_DIRETOR.parquet'}' "
            f"WHERE ID_UF = {ID_UF_RJ} AND COALESCE(IN_PREENCHIMENTO_QUESTIONARIO, 1) = 1"
        ).fetchone()
        n_unique_schools = int(dir_row[0]) if dir_row else 0

        prof_row = pq_con.execute(
            f"SELECT COUNT(DISTINCT ID_PROFESSOR) FROM '{SAEB_PARQUET_DIR / 'TS_PROFESSOR.parquet'}' "
            f"WHERE ID_UF = {ID_UF_RJ} AND COALESCE(IN_PREENCHIMENTO_QUESTIONARIO, 1) = 1"
        ).fetchone()
        n_unique_teachers = int(prof_row[0]) if prof_row else 0
    finally:
        pq_con.close()

    max_dir = query(
        db,
        "SELECT MAX(tot) AS m FROM (SELECT questao, SUM(contagem) AS tot FROM quest_diretor_rj GROUP BY questao)",
    )[0]["m"]
    check(
        f"quest_diretor_rj deduplicado por ID_ESCOLA: máx respostas/questão ({max_dir:,}) ≤ {n_unique_schools:,} escolas únicas",
        max_dir is not None and 0 < max_dir <= n_unique_schools,
        f"max={max_dir}, unique_schools={n_unique_schools}",
    )

    max_prof = query(
        db,
        "SELECT MAX(tot) AS m FROM (SELECT questao, SUM(contagem) AS tot FROM quest_professor_rj GROUP BY questao)",
    )[0]["m"]
    check(
        f"quest_professor_rj deduplicado por ID_PROFESSOR: máx respostas/questão ({max_prof:,}) ≤ {n_unique_teachers:,} docentes únicos",
        max_prof is not None and 0 < max_prof <= n_unique_teachers,
        f"max={max_prof}, unique_teachers={n_unique_teachers}",
    )

    open_found = query(
        db,
        "SELECT questao FROM quest_professor_rj WHERE questao = 'TX_Q148' "
        "UNION ALL "
        "SELECT questao FROM quest_diretor_rj WHERE questao IN ('TX_Q089', 'TX_Q168', 'TX_Q211', 'TX_Q224')",
    )
    check("Nenhuma coluna dissertativa aberta nas tabelas de questionário", len(open_found) == 0)


# ───────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Validação Cruzada de Estatísticas — Dashboard UFF")
    print("=" * 60)

    if not DUCKDB_PATH.exists():
        print(f"\n✗ Banco DuckDB não encontrado em {DUCKDB_PATH}")
        print("  Execute primeiro: python scripts/init_db.py")
        sys.exit(1)

    db = get_db()

    validate_tables(db)
    validate_proficiency_ranges(db)
    validate_rj_means(db)
    validate_gap_pub_priv(db)
    validate_inse_monotonic(db)
    validate_wifi_gap(db)
    validate_sample_sizes(db)
    validate_tic_indicators(db)
    validate_digital_index(db)
    validate_proficiency_levels_and_escola_inse(db)
    validate_questionnaire_deduplication(db)

    db.close()

    print("\n" + "=" * 60)
    print(f"  Resultado: {passed} ✓  |  {failed} ✗  |  {warnings} ⚠")
    print("=" * 60)

    if failed > 0:
        print(f"\n⚠ {failed} validação(ões) falharam. Revise os dados.")
        sys.exit(1)
    else:
        print("\n✓ Todas as validações passaram.")


if __name__ == "__main__":
    main()
