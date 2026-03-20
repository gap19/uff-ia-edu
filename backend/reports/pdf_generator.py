"""Motor de geração de relatórios PDF com WeasyPrint e matplotlib."""

import base64
import io
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from backend.api.app import get_db
from backend.config import ID_UF_RJ, UF_MAP

# Diretório de templates
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Estilo matplotlib para publicação
sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.family": "sans-serif",
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})

COLORS = {
    "primary": "#4e79a7",
    "secondary": "#f28e2b",
    "accent": "#e15759",
    "green": "#59a14f",
    "teal": "#76b7b2",
    "purple": "#b07aa1",
}
PALETTE = list(COLORS.values())


def _fig_to_base64(fig: plt.Figure) -> str:
    """Converte figura matplotlib para string base64 PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _query(sql: str, params: list | None = None) -> list[dict]:
    """Executa query DuckDB e retorna lista de dicts."""
    db = get_db()
    rel = db.execute(sql, params or [])
    columns = [desc[0] for desc in rel.description]
    return [dict(zip(columns, row)) for row in rel.fetchall()]


# ---------------------------------------------------------------------------
# Geradores de gráficos matplotlib (vetoriais para PDF)
# ---------------------------------------------------------------------------


def chart_proficiency_bars(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico de barras: proficiência média RJ por série e disciplina."""
    rows = _query("SELECT * FROM kpi_rj ORDER BY serie")
    if not rows:
        return ""

    filtered = [r for r in rows if r["serie"] in series]
    if not filtered:
        filtered = rows

    disc_cols = {
        "LP": "media_lp",
        "MT": "media_mt",
    }

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(filtered))
    width = 0.35
    offset = 0

    for disc in disciplinas:
        col = disc_cols.get(disc)
        if not col:
            continue
        values = [r.get(col, 0) or 0 for r in filtered]
        label = "Língua Portuguesa" if disc == "LP" else "Matemática"
        ax.bar(x + offset, values, width, label=label, color=PALETTE[offset])
        for i, v in enumerate(values):
            ax.text(x[i] + offset, v + 2, f"{v:.1f}", ha="center", fontsize=9)
        offset += 1

    ax.set_xticks(x + width / 2)
    ax.set_xticklabels([r["serie"] for r in filtered])
    ax.set_ylabel("Proficiência (escala SAEB)")
    ax.set_title("Proficiência Média - Rio de Janeiro (SAEB 2023)")
    ax.legend()
    ax.set_ylim(bottom=0)

    return _fig_to_base64(fig)


def _compute_gap(series: list[str], disciplinas: list[str]) -> list[dict]:
    """Computa lacuna pública vs privada a partir de prof_by_uf_serie_disc."""
    rows = _query(
        "SELECT serie, disciplina, rede, media_proficiencia "
        "FROM prof_by_uf_serie_disc WHERE ID_UF = ? ORDER BY serie, disciplina, rede",
        [ID_UF_RJ],
    )
    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = (row["serie"], row["disciplina"])
        rede_key = "publica" if row["rede"] == 1 else "privada"
        grouped.setdefault(key, {})[rede_key] = row["media_proficiencia"]

    gaps = []
    for (s, d), redes in grouped.items():
        pub = redes.get("publica")
        priv = redes.get("privada")
        gap_value = round(priv - pub, 2) if pub is not None and priv is not None else None
        gaps.append({
            "serie": s, "disciplina": d,
            "media_publica": pub, "media_privada": priv, "gap": gap_value,
        })
    return gaps


def chart_equity_gap(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico de barras: lacuna pública vs privada."""
    all_gaps = _compute_gap(series, disciplinas)
    if not all_gaps:
        return ""

    filtered = [
        r for r in all_gaps
        if r["serie"] in series and r["disciplina"] in disciplinas
    ]
    if not filtered:
        filtered = all_gaps[:4]

    labels = [f"{r['serie']} {r['disciplina']}" for r in filtered]
    pub = [r.get("media_publica", 0) or 0 for r in filtered]
    priv = [r.get("media_privada", 0) or 0 for r in filtered]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(labels))
    width = 0.35

    ax.bar(x - width / 2, pub, width, label="Pública", color=COLORS["primary"])
    ax.bar(x + width / 2, priv, width, label="Privada", color=COLORS["secondary"])

    for i in range(len(labels)):
        gap = priv[i] - pub[i]
        ax.annotate(
            f"Δ {gap:.1f}",
            xy=(x[i], max(pub[i], priv[i]) + 3),
            ha="center", fontsize=9, color=COLORS["accent"], fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Proficiência média")
    ax.set_title("Lacuna Pública vs Privada - RJ (SAEB 2023)")
    ax.legend()
    ax.set_ylim(bottom=0)

    return _fig_to_base64(fig)


def chart_inse(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico de barras: proficiência por nível INSE."""
    rows = _query("SELECT * FROM prof_by_inse ORDER BY nivel_inse")
    if not rows:
        return ""

    # Filtrar pela primeira série/disciplina disponível
    target_serie = series[0] if series else "9EF"
    target_disc = disciplinas[0] if disciplinas else "LP"
    filtered = [
        r for r in rows
        if r.get("serie") == target_serie and r.get("disciplina") == target_disc
    ]
    if not filtered:
        filtered = rows

    fig, ax = plt.subplots(figsize=(7, 4.5))
    niveis = [f"Nível {r['nivel_inse']}" for r in filtered]
    medias = [r.get("media_proficiencia", 0) or 0 for r in filtered]

    bars = ax.bar(niveis, medias, color=PALETTE[: len(niveis)])
    for bar, v in zip(bars, medias):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 2, f"{v:.1f}",
                ha="center", fontsize=9)

    ax.set_ylabel("Proficiência média")
    ax.set_xlabel("Nível Socioeconômico (INSE)")
    ax.set_title(f"Proficiência por INSE - {target_serie} {target_disc} (RJ)")
    ax.set_ylim(bottom=0)

    return _fig_to_base64(fig)


def chart_ranking(serie: str, disciplina: str) -> str:
    """Gráfico de barras: ranking de UFs."""
    rows = _query(
        """SELECT ID_UF, serie, disciplina,
                  SUM(media_proficiencia * soma_pesos) / SUM(soma_pesos) AS media_proficiencia,
                  SUM(n_alunos) AS n_alunos
           FROM prof_by_uf_serie_disc
           WHERE serie = ? AND disciplina = ?
           GROUP BY ID_UF, serie, disciplina
           ORDER BY media_proficiencia DESC""",
        [serie, disciplina],
    )
    if not rows:
        return ""

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ufs = [UF_MAP.get(r.get("ID_UF", 0), str(r.get("ID_UF", ""))) for r in rows]
    medias = [r.get("media_proficiencia", 0) or 0 for r in rows]
    colors = [COLORS["accent"] if uf == "RJ" else COLORS["teal"] for uf in ufs]

    ax.bar(ufs, medias, color=colors)
    ax.set_ylabel("Proficiência média")
    ax.set_title(f"Ranking Nacional - {serie} {disciplina} (SAEB 2023)")
    ax.tick_params(axis="x", rotation=45)

    # Destacar posição do RJ
    if "RJ" in ufs:
        pos = ufs.index("RJ") + 1
        ax.annotate(
            f"RJ: {pos}º de {len(ufs)}",
            xy=(0.98, 0.95), xycoords="axes fraction",
            ha="right", fontsize=11, color=COLORS["accent"], fontweight="bold",
        )

    return _fig_to_base64(fig)


def chart_tic_group(group: str, title: str) -> str:
    """Gráfico de barras: indicadores TIC por grupo."""
    group_map = {
        "infrastructure": ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"),
        "ai": ("E4A", "E4B", "E5", "E6", "F6"),
        "privacy": ("H1", "H3", "H4", "H5", "H6", "H7"),
        "training": ("J1", "J2", "J3", "J4"),
    }
    indicators = group_map.get(group, ())
    if not indicators:
        return ""

    placeholders = ", ".join(["?"] * len(indicators))
    rows = _query(
        f"""SELECT indicador, valor FROM tic_indicadores
            WHERE tipo = 'proporcao' AND valor_corte = 'TOTAL'
              AND indicador IN ({placeholders})
            ORDER BY indicador""",
        list(indicators),
    )
    if not rows:
        return ""

    fig, ax = plt.subplots(figsize=(8, 4.5))
    inds = [r["indicador"] for r in rows]
    vals = [r.get("valor", 0) or 0 for r in rows]

    ax.bar(inds, vals, color=COLORS["primary"])
    for i, v in enumerate(vals):
        ax.text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=9)

    ax.set_ylabel("Proporção (%)")
    ax.set_ylim(0, 105)
    ax.set_title(f"TIC Educação 2023 (Sudeste) - {title}")

    return _fig_to_base64(fig)


# ---------------------------------------------------------------------------
# Gráficos de cruzamentos tech x desempenho
# ---------------------------------------------------------------------------


def chart_cross_student_wifi(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico: Wi-Fi em casa vs proficiência (bruto)."""
    serie = series[0] if series else "9EF"
    disc = disciplinas[0] if disciplinas else "LP"

    rows = _query(
        """SELECT tech_response, media_proficiencia, n_alunos
           FROM cross_aluno_tech_rj
           WHERE serie = ? AND disciplina = ? AND tech_variable = 'TX_RESP_Q13b'
             AND nivel_inse IS NULL AND tech_response IN ('A', 'B')
           ORDER BY tech_response""",
        [serie, disc],
    )
    if not rows:
        return ""

    labels_map = {"A": "Sem Wi-Fi", "B": "Com Wi-Fi"}
    labels = [labels_map.get(r["tech_response"], r["tech_response"]) for r in rows]
    values = [r.get("media_proficiencia", 0) or 0 for r in rows]
    ns = [r.get("n_alunos", 0) or 0 for r in rows]

    fig, ax = plt.subplots(figsize=(6, 4))
    bar_colors = [COLORS["accent"], COLORS["primary"]]
    bars = ax.bar(labels, values, color=bar_colors)
    for bar, v, n in zip(bars, values, ns):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 2,
                f"{v:.1f}\n(n={n:,})", ha="center", fontsize=9)

    if len(values) == 2:
        gap = values[1] - values[0]
        ax.annotate(
            f"Gap: {gap:.1f} pts",
            xy=(0.5, 0.95), xycoords="axes fraction",
            ha="center", fontsize=12, color=COLORS["accent"], fontweight="bold",
        )

    ax.set_ylabel("Proficiência média")
    ax.set_title(f"Wi-Fi em Casa vs Proficiência - {serie} {disc} (RJ)")
    ax.set_ylim(bottom=0)
    return _fig_to_base64(fig)


def chart_cross_digital_index(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico: índice digital composto vs proficiência."""
    serie = series[0] if series else "9EF"
    disc = disciplinas[0] if disciplinas else "LP"

    rows = _query(
        """SELECT digital_index, media_proficiencia, n_alunos
           FROM cross_digital_index_rj
           WHERE serie = ? AND disciplina = ? AND nivel_inse IS NULL
           ORDER BY digital_index""",
        [serie, disc],
    )
    if not rows:
        return ""

    fig, ax = plt.subplots(figsize=(7, 4))
    xs = [r["digital_index"] for r in rows]
    ys = [r.get("media_proficiencia", 0) or 0 for r in rows]

    ax.plot(xs, ys, "o-", color=COLORS["primary"], linewidth=2, markersize=7)
    for x, y in zip(xs, ys):
        ax.text(x, y + 2, f"{y:.1f}", ha="center", fontsize=8)

    ax.set_xlabel("Índice Digital (0-8)")
    ax.set_ylabel("Proficiência média")
    ax.set_title(f"Índice Digital Composto vs Proficiência - {serie} {disc} (RJ)")
    ax.set_xticks(range(9))
    return _fig_to_base64(fig)


def chart_cross_director_tech(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico: variáveis do diretor (Q194, Q219) vs proficiência."""
    serie = series[0] if series else "9EF"
    disc = disciplinas[0] if disciplinas else "LP"

    vars_to_plot = [
        ("TX_Q194", "Projetos C&T"),
        ("TX_Q219", "Novas Tech Educ."),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)

    for idx, (var, title) in enumerate(vars_to_plot):
        ax = axes[idx]
        rows = _query(
            """SELECT tech_response, media_proficiencia, n_escolas
               FROM cross_diretor_tech_rj
               WHERE tech_variable = ? AND serie = ? AND disciplina = ?
               ORDER BY tech_response""",
            [var, serie, disc],
        )
        if not rows:
            ax.set_title(title)
            ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", transform=ax.transAxes)
            continue

        labels_map = {"A": "Sim", "B": "Não"}
        labels = [labels_map.get(r["tech_response"], r["tech_response"]) for r in rows]
        values = [r.get("media_proficiencia", 0) or 0 for r in rows]
        bar_colors = [COLORS["green"], COLORS["accent"]][:len(labels)]
        bars = ax.bar(labels, values, color=bar_colors)
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 1, f"{v:.1f}",
                    ha="center", fontsize=9)
        ax.set_title(title)
        ax.set_ylim(bottom=0)

    axes[0].set_ylabel("Proficiência média")
    fig.suptitle(f"Infraestrutura Tecnológica vs Proficiência - {serie} {disc} (RJ)", fontsize=12)
    fig.tight_layout()
    return _fig_to_base64(fig)


def chart_cross_forest_plot(series: list[str], disciplinas: list[str]) -> str:
    """Forest plot: efeitos de todas as variáveis binárias tech."""
    try:
        from backend.analysis.cross_analysis import get_cross_summary
        serie = series[0] if series else "9EF"
        disc = disciplinas[0] if disciplinas else "LP"
        summary = get_cross_summary(serie, disc)
        analyses = [a for a in summary.get("analyses", []) if a.get("cohens_d") is not None]
    except Exception:
        return ""

    if not analyses:
        return ""

    fig, ax = plt.subplots(figsize=(8, max(3, len(analyses) * 0.6)))
    labels = [a["label"] for a in analyses]
    effects = [a["cohens_d"] for a in analyses]
    colors = [COLORS["green"] if e >= 0 else COLORS["accent"] for e in effects]

    y_pos = range(len(labels))
    ax.barh(y_pos, effects, color=colors, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.axvline(x=0, color="#999", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Cohen's d (tamanho de efeito)")
    ax.set_title("Tamanhos de Efeito — Variáveis Tecnológicas")

    for i, e in enumerate(effects):
        ax.text(e + 0.01 if e >= 0 else e - 0.01, i,
                f"{e:.3f}", va="center",
                ha="left" if e >= 0 else "right", fontsize=9)

    fig.tight_layout()
    return _fig_to_base64(fig)


# ---------------------------------------------------------------------------
# Montagem de dados do relatório
# ---------------------------------------------------------------------------


def _build_report_data(
    secoes: list[str],
    series: list[str],
    disciplinas: list[str],
    incluir_apendice: bool,
) -> dict[str, Any]:
    """Coleta dados e gráficos para o relatório."""
    data: dict[str, Any] = {
        "titulo": "Relatório de Pesquisa: IA e Educação",
        "subtitulo": "Análise de Microdados SAEB 2023 e TIC Educação 2023 — Rio de Janeiro",
        "projeto": "Ética na Tomada de Decisão por Inteligência Artificial no Ambiente Escolar",
        "instituicao": "Universidade Federal Fluminense — Faculdade de Educação",
        "data_geracao": datetime.now().strftime("%d/%m/%Y às %H:%M"),
        "series": series,
        "disciplinas": disciplinas,
        "secoes": {},
    }

    # KPIs gerais
    try:
        kpis = _query("SELECT * FROM kpi_rj ORDER BY serie")
        escolas = _query("SELECT * FROM kpi_escolas_rj")
        data["kpis"] = kpis
        data["total_escolas"] = escolas[0].get("total_escolas", 0) if escolas else 0
        data["total_alunos"] = sum(r.get("total_alunos", 0) or 0 for r in kpis)
    except Exception:
        data["kpis"] = []
        data["total_escolas"] = 0
        data["total_alunos"] = 0

    # Seção: Proficiência
    if "proficiencia" in secoes:
        data["secoes"]["proficiencia"] = {
            "chart_bars": chart_proficiency_bars(series, disciplinas),
            "chart_ranking": chart_ranking(
                series[0] if series else "9EF",
                disciplinas[0] if disciplinas else "LP",
            ),
        }

    # Seção: Equidade
    if "equidade" in secoes:
        data["secoes"]["equidade"] = {
            "chart_gap": chart_equity_gap(series, disciplinas),
            "chart_inse": chart_inse(series, disciplinas),
        }

    # Seção: Tecnologia
    if "tecnologia" in secoes:
        data["secoes"]["tecnologia"] = {
            "chart_infra": chart_tic_group("infrastructure", "Infraestrutura"),
            "chart_ai": chart_tic_group("ai", "IA e Sistemas de Dados"),
            "chart_privacy": chart_tic_group("privacy", "Privacidade"),
            "chart_training": chart_tic_group("training", "Formação Digital"),
        }

    # Seção: Cruzamentos Tech x Desempenho
    if "cruzamentos" in secoes:
        data["secoes"]["cruzamentos"] = {
            "chart_wifi": chart_cross_student_wifi(series, disciplinas),
            "chart_digital_index": chart_cross_digital_index(series, disciplinas),
            "chart_director": chart_cross_director_tech(series, disciplinas),
            "chart_forest": chart_cross_forest_plot(series, disciplinas),
        }

    # Seção: Ética
    if "etica" in secoes:
        data["secoes"]["etica"] = True

    # Apêndice estatístico
    if incluir_apendice:
        try:
            gap_rows = _compute_gap(series, disciplinas)
            inse_rows = _query("SELECT * FROM prof_by_inse ORDER BY nivel_inse")
            data["apendice"] = {
                "gap": gap_rows,
                "inse": inse_rows,
            }
        except Exception:
            data["apendice"] = None

    return data


# ---------------------------------------------------------------------------
# Geração do PDF
# ---------------------------------------------------------------------------


def generate_pdf(
    secoes: list[str] | None = None,
    series: list[str] | None = None,
    disciplinas: list[str] | None = None,
    incluir_apendice: bool = True,
) -> bytes:
    """Gera o relatório PDF completo e retorna os bytes do arquivo.

    Args:
        secoes: Seções a incluir (proficiencia, equidade, tecnologia, etica).
        series: Séries do SAEB (5EF, 9EF, 34EM).
        disciplinas: Disciplinas (LP, MT).
        incluir_apendice: Se deve incluir apêndice estatístico.

    Returns:
        Bytes do PDF gerado.
    """
    if secoes is None:
        secoes = ["proficiencia", "equidade", "tecnologia", "etica"]
    if series is None:
        series = ["5EF", "9EF"]
    if disciplinas is None:
        disciplinas = ["LP", "MT"]

    # Coletar dados
    report_data = _build_report_data(secoes, series, disciplinas, incluir_apendice)

    # Renderizar HTML via Jinja2
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("report.html")
    html_content = template.render(**report_data)

    # Converter para PDF via WeasyPrint
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
