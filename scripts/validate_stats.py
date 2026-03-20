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
from backend.config import DUCKDB_PATH, SAEB_PARQUET_DIR, ID_UF_RJ

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
    """1. Verificar que todas as tabelas pré-computadas existem."""
    print("\n[1] Tabelas pré-computadas")
    tables = [t[0] for t in db.execute("SHOW TABLES").fetchall()]
    expected = [
        "prof_by_uf_serie_disc", "prof_by_inse", "prof_niveis_rj",
        "prof_niveis_nacional", "quest_aluno_rj", "quest_professor_rj",
        "quest_diretor_rj", "escola_formacao_rj", "kpi_rj",
        "tic_indicadores",
        "cross_aluno_tech_rj", "cross_diretor_tech_rj",
        "cross_professor_tech_rj", "cross_digital_index_rj",
    ]
    for t in expected:
        check(f"Tabela '{t}' existe", t in tables, f"Faltando: {t}")


def validate_proficiency_ranges(db):
    """2. Proficiências devem estar em faixas plausíveis da escala SAEB."""
    print("\n[2] Faixas de proficiência (escala SAEB)")
    rows = query(db,
        "SELECT serie, disciplina, MIN(media_proficiencia) AS min_p, "
        "MAX(media_proficiencia) AS max_p, AVG(media_proficiencia) AS avg_p "
        "FROM prof_by_uf_serie_disc GROUP BY serie, disciplina"
    )
    for r in rows:
        s, d = r["serie"], r["disciplina"]
        minp, maxp = r["min_p"], r["max_p"]
        # Escala SAEB: tipicamente 100-400 para todas as séries
        check(f"{s}/{d}: min={minp:.1f}, max={maxp:.1f} dentro [100, 400]",
              100 < minp and maxp < 400,
              f"Fora da faixa esperada")


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
    refs = {
        ("5EF", "LP", 1): (195, 220, "pública 5EF LP ~206"),
        ("5EF", "LP", 0): (225, 260, "privada 5EF LP ~240"),
        ("9EF", "LP", 1): (240, 270, "pública 9EF LP ~253"),
        ("9EF", "LP", 0): (270, 300, "privada 9EF LP ~282"),
        ("5EF", "MT", 1): (195, 230, "pública 5EF MT ~215"),
        ("5EF", "MT", 0): (230, 270, "privada 5EF MT ~250"),
        ("9EF", "MT", 1): (245, 275, "pública 9EF MT ~258"),
        ("9EF", "MT", 0): (275, 310, "privada 9EF MT ~292"),
    }
    for r in rows:
        key = (r["serie"], r["disciplina"], r["rede"])
        if key in refs:
            lo, hi, desc = refs[key]
            val = r["media_proficiencia"]
            check(f"RJ {desc}: {val:.1f} ∈ [{lo}, {hi}]",
                  lo <= val <= hi,
                  f"Valor {val:.1f} fora da faixa esperada")


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
              f"Tendência decrescente inesperada")


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
                  f"Gap fora da tolerância")
            n_no = by_resp["A"]["n_alunos"]
            n_yes = by_resp["B"]["n_alunos"]
            check(f"N sem WiFi = {n_no:,} (ref: ~9.5K)",
                  5000 < n_no < 20000)
            check(f"N com WiFi = {n_yes:,} (ref: ~102K)",
                  80000 < n_yes < 130000)
        else:
            warn("Dados de WiFi A/B não encontrados")
    else:
        warn("Tabela cross_aluno_tech_rj sem dados suficientes para WiFi")


def validate_sample_sizes(db):
    """7. Tamanhos amostrais devem ser plausíveis."""
    print("\n[7] Tamanhos amostrais")
    kpi = query(db, "SELECT * FROM kpi_rj")
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
        warn("Nenhum indicador TIC encontrado")


def validate_digital_index(db):
    """9. Índice digital composto: faixas devem estar corretas."""
    print("\n[9] Índice digital composto")
    rows = query(db,
        "SELECT digital_index, faixa_digital, media_proficiencia, n_alunos "
        "FROM cross_digital_index_rj "
        "WHERE serie = '9EF' AND disciplina = 'LP' AND nivel_inse IS NULL "
        "ORDER BY digital_index"
    )
    if rows:
        # Índice vai de 0 a 8
        indices = [r["digital_index"] for r in rows]
        check(f"Índice mín = {min(indices)}, máx = {max(indices)} (esperado: 0-8)",
              min(indices) >= 0 and max(indices) <= 8)
        # Faixas
        faixas = set(r["faixa_digital"] for r in rows)
        check(f"Faixas presentes: {faixas}",
              faixas.issubset({"Baixo", "Medio", "Alto"}))
        # Gradiente: proficiência deve crescer com índice (tendência geral)
        vals = [r["media_proficiencia"] for r in rows if r["media_proficiencia"]]
        if len(vals) >= 3:
            check(f"Gradiente: índice alto ({vals[-1]:.1f}) > baixo ({vals[0]:.1f})",
                  vals[-1] > vals[0])
    else:
        warn("Tabela cross_digital_index_rj vazia")


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
