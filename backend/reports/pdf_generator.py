"""Motor de geração de relatórios PDF com WeasyPrint e matplotlib."""

import base64
from functools import lru_cache
import io
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from backend.db import db_query
from backend.config import ID_UF_RJ, UF_MAP

# Diretório de templates
TEMPLATES_DIR = Path(__file__).parent / "templates"

# pyplot mantém estado global e não é thread-safe; o lock protege
# exclusivamente a criação e o salvamento de figuras matplotlib.
_PDF_LOCK = threading.Lock()

ALL_SECTIONS = ["proficiencia", "equidade", "tecnologia", "cruzamentos", "etica"]
ALLOWED_SERIES = ("5EF", "9EF", "34EM")
ALLOWED_DISCIPLINAS = ("LP", "MT")
_SERIE_ORDER_SQL = "CASE serie WHEN '5EF' THEN 1 WHEN '9EF' THEN 2 ELSE 3 END"

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
    "brown": "#9c755f",
    "yellow": "#edc948",
}
PALETTE = list(COLORS.values())


def _normalize_report_params(
    secoes: list[str] | None,
    series: list[str] | None,
    disciplinas: list[str] | None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Normaliza caixa, deduplica e valida parâmetros de relatório contra whitelists."""
    if secoes is None:
        norm_secoes: tuple[str, ...] = tuple(ALL_SECTIONS)
    else:
        dedup_sec = list(dict.fromkeys(s.strip().lower() for s in secoes))
        invalid_sec = [s for s in dedup_sec if s not in ALL_SECTIONS]
        if invalid_sec or not dedup_sec:
            raise ValueError(
                f"Seções inválidas: {invalid_sec or secoes}. Opções válidas: {ALL_SECTIONS}"
            )
        norm_secoes = tuple(s for s in ALL_SECTIONS if s in dedup_sec)

    if series is None:
        norm_series: tuple[str, ...] = ("5EF", "9EF")
    else:
        dedup_ser = list(dict.fromkeys(s.strip().upper() for s in series))
        invalid_ser = [s for s in dedup_ser if s not in ALLOWED_SERIES]
        if invalid_ser or not dedup_ser:
            raise ValueError(
                f"Séries inválidas: {invalid_ser or series}. Opções válidas: {list(ALLOWED_SERIES)}"
            )
        norm_series = tuple(dedup_ser)

    if disciplinas is None:
        norm_discs: tuple[str, ...] = ("LP", "MT")
    else:
        dedup_disc = list(dict.fromkeys(d.strip().upper() for d in disciplinas))
        invalid_disc = [d for d in dedup_disc if d not in ALLOWED_DISCIPLINAS]
        if invalid_disc or not dedup_disc:
            raise ValueError(
                f"Disciplinas inválidas: {invalid_disc or disciplinas}. "
                f"Opções válidas: {list(ALLOWED_DISCIPLINAS)}"
            )
        norm_discs = tuple(dedup_disc)

    return norm_secoes, norm_series, norm_discs


def _fig_to_base64(fig: plt.Figure) -> str:
    """Converte figura matplotlib para string base64 PNG."""
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    finally:
        plt.close(fig)


_query = db_query


# ---------------------------------------------------------------------------
# Geradores de gráficos matplotlib (vetoriais para PDF)
# ---------------------------------------------------------------------------


def chart_proficiency_bars(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico de barras: proficiência média RJ por série e disciplina."""
    rows = _query(f"SELECT * FROM kpi_rj ORDER BY {_SERIE_ORDER_SQL}")
    if not rows:
        return ""

    filtered = [r for r in rows if r["serie"] in series]
    if not filtered:
        filtered = rows

    disc_cols = {
        "LP": "media_lp",
        "MT": "media_mt",
    }
    discs = [d for d in disciplinas if d in disc_cols] or ["LP", "MT"]
    top = max((r.get(disc_cols[d]) or 0) for r in filtered for d in discs)

    with _PDF_LOCK:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        try:
            x = np.arange(len(filtered))
            width = 0.8 / len(discs)

            for i_disc, disc in enumerate(discs):
                col = disc_cols[disc]
                values = [r.get(col, 0) or 0 for r in filtered]
                label = "Língua Portuguesa" if disc == "LP" else "Matemática"
                pos = x + i_disc * width
                ax.bar(pos, values, width, label=label, color=PALETTE[i_disc % len(PALETTE)])
                for xi, v in zip(pos, values):
                    ax.text(xi, v + 2, f"{v:.1f}", ha="center", fontsize=9)

            ax.set_xticks(x + width * (len(discs) - 1) / 2)
            ax.set_xticklabels([r["serie"] for r in filtered])
            ax.set_ylabel("Proficiência (escala SAEB)")
            ax.set_title("Proficiência Média - Rio de Janeiro (SAEB 2023)")
            ax.set_ylim(0, top * 1.22)
            ax.legend(loc="upper left", ncol=len(discs))

            return _fig_to_base64(fig)
        finally:
            plt.close(fig)


def _compute_gap(series: list[str], disciplinas: list[str]) -> list[dict]:
    """Computa lacuna pública vs privada a partir de prof_by_uf_serie_disc.

    Retorna todas as combinações série/disciplina (o filtro é feito por quem
    chama).
    """
    rows = _query(
        "SELECT serie, disciplina, rede, media_proficiencia "
        f"FROM prof_by_uf_serie_disc WHERE ID_UF = ? ORDER BY {_SERIE_ORDER_SQL}, disciplina, rede",
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


def _compute_gap_with_stats(series: list[str], disciplinas: list[str]) -> list[dict]:
    """Lacunas das séries/disciplinas pedidas, com d de Cohen e IC 95% da lacuna.

    Tudo (médias, lacuna, d e IC) vem da mesma análise dos microdados
    ponderados (backend.analysis.equity), de modo que o IC é centrado na
    lacuna exibida; o IC usa a distribuição t com os graus de liberdade do
    desenho amostral (escolas − estratos). As médias coincidem com as da
    tabela pré-computada ``prof_by_uf_serie_disc``.
    """
    from backend.analysis.equity import get_public_private_gap

    rows = []
    for r in _compute_gap(series, disciplinas):
        if r["serie"] not in series or r["disciplina"] not in disciplinas:
            continue
        row = dict(r, cohens_d=None, ci_lower=None, ci_upper=None)
        if r["gap"] is not None:
            try:
                res = get_public_private_gap(r["serie"], r["disciplina"], ID_UF_RJ)
            except Exception:
                res = None
            if res and res.get("gap") is not None:
                row.update(
                    media_publica=res["publica"]["mean"],
                    media_privada=res["privada"]["mean"],
                    gap=res["gap"],
                    cohens_d=res.get("cohens_d"),
                    ci_lower=res.get("ci_gap_lower"),
                    ci_upper=res.get("ci_gap_upper"),
                )
        rows.append(row)
    return rows


def chart_equity_gap(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico de barras: lacuna pública vs privada."""
    all_gaps = _compute_gap(series, disciplinas)
    # Só faz sentido comparar onde existem as duas redes
    all_gaps = [
        r for r in all_gaps
        if r["media_publica"] is not None and r["media_privada"] is not None
    ]
    if not all_gaps:
        return ""

    filtered = [
        r for r in all_gaps
        if r["serie"] in series and r["disciplina"] in disciplinas
    ]
    if not filtered:
        filtered = all_gaps[:4]

    labels = [f"{r['serie']} {r['disciplina']}" for r in filtered]
    pub = [r["media_publica"] for r in filtered]
    priv = [r["media_privada"] for r in filtered]

    with _PDF_LOCK:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        try:
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
            ax.set_ylim(0, max(priv + pub) * 1.3)
            ax.legend(loc="upper left", ncol=2)

            return _fig_to_base64(fig)
        finally:
            plt.close(fig)


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
        return ""

    niveis = [f"Nível {r['nivel_inse']}" for r in filtered]
    medias = [r.get("media_proficiencia", 0) or 0 for r in filtered]
    bar_colors = [PALETTE[i % len(PALETTE)] for i in range(len(niveis))]

    with _PDF_LOCK:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        try:
            bars = ax.bar(niveis, medias, color=bar_colors)
            for bar, v in zip(bars, medias):
                ax.text(bar.get_x() + bar.get_width() / 2, v + 2, f"{v:.1f}",
                        ha="center", fontsize=9)

            ax.set_ylabel("Proficiência média")
            ax.set_xlabel("Nível Socioeconômico (INSE)")
            ax.set_title(f"Proficiência por INSE - {target_serie} {target_disc} (RJ)")
            ax.set_ylim(bottom=0)

            return _fig_to_base64(fig)
        finally:
            plt.close(fig)


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

    ufs = [UF_MAP.get(r.get("ID_UF", 0), str(r.get("ID_UF", ""))) for r in rows]
    medias = [r.get("media_proficiencia", 0) or 0 for r in rows]
    colors = [COLORS["accent"] if uf == "RJ" else COLORS["teal"] for uf in ufs]

    with _PDF_LOCK:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        try:
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
        finally:
            plt.close(fig)


def chart_tic_group(group: str, title: str) -> str:
    """Barras agrupadas: indicadores TIC (% de escolas) no Sudeste e no Brasil."""
    import textwrap

    from backend.analysis.tic import REGION_PRIMARY, REGION_REFERENCE, get_tic_group

    try:
        items = get_tic_group(group)["data"]
    except Exception:
        return ""
    if not items:
        return ""

    se = [d["sudeste"] or 0 for d in items]
    br = [d["brasil"] or 0 for d in items]
    xlabels = [textwrap.fill(d["label"], 16) for d in items]
    has_univ_note = any(d.get("universo_especifico") for d in items)

    with _PDF_LOCK:
        fig, ax = plt.subplots(figsize=(9, 4.8))
        try:
            x = np.arange(len(items))
            width = 0.38
            ax.bar(x - width / 2, se, width, label=REGION_PRIMARY, color=COLORS["primary"])
            ax.bar(x + width / 2, br, width, label=REGION_REFERENCE, color="#b8c2cc")
            for xi, v in zip(x - width / 2, se):
                ax.text(xi, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8)
            for xi, v in zip(x + width / 2, br):
                ax.text(xi, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8, color="#555")
            ax.set_xticks(x)
            ax.set_xticklabels(xlabels, fontsize=8)

            ax.set_ylabel("% de escolas")
            ax.set_ylim(0, 112)
            ax.set_yticks(range(0, 101, 20))
            ax.legend(loc="upper right", ncol=2, fontsize=9)
            ax.set_title(f"TIC Educação 2023 — {title}")
            if has_univ_note:
                fig.text(
                    0.01, -0.02, "¹ Universo: escolas com acesso à internet.",
                    fontsize=8, color="#555",
                )
            fig.tight_layout()

            return _fig_to_base64(fig)
        finally:
            plt.close(fig)


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

    with _PDF_LOCK:
        fig, ax = plt.subplots(figsize=(6, 4))
        try:
            bar_colors = [COLORS["accent"], COLORS["primary"]]
            bars = ax.bar(labels, values, color=bar_colors)
            for bar, v, n in zip(bars, values, ns):
                ax.text(bar.get_x() + bar.get_width() / 2, v + 2,
                        f"{v:.1f}\n(n={n:,})", ha="center", fontsize=9)

            if len(values) == 2:
                gap = values[1] - values[0]
                ax.annotate(
                    f"Gap: {gap:.1f} pts",
                    xy=(0.5, 0.94), xycoords="axes fraction",
                    ha="center", fontsize=12, color=COLORS["accent"], fontweight="bold",
                )

            ax.set_ylabel("Proficiência média")
            ax.set_title(f"Wi-Fi em Casa vs Proficiência - {serie} {disc} (RJ)")
            ax.set_ylim(0, max(values) * 1.35)
            return _fig_to_base64(fig)
        finally:
            plt.close(fig)


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

    xs = [r["digital_index"] for r in rows]
    ys = [r.get("media_proficiencia", 0) or 0 for r in rows]

    with _PDF_LOCK:
        fig, ax = plt.subplots(figsize=(7, 4))
        try:
            ax.plot(xs, ys, "o-", color=COLORS["primary"], linewidth=2, markersize=7)
            for x, y in zip(xs, ys):
                ax.text(x, y + 2, f"{y:.1f}", ha="center", fontsize=8)

            ax.set_xlabel("Índice Digital (0-8)")
            ax.set_ylabel("Proficiência média")
            ax.set_title(f"Índice Digital Composto vs Proficiência - {serie} {disc} (RJ)")
            ax.set_xticks(range(9))
            return _fig_to_base64(fig)
        finally:
            plt.close(fig)


def chart_cross_director_tech(series: list[str], disciplinas: list[str]) -> str:
    """Gráfico: variáveis do diretor (Q194, Q219) vs proficiência."""
    serie = series[0] if series else "9EF"
    disc = disciplinas[0] if disciplinas else "LP"

    vars_to_plot = [
        ("TX_Q194", "Projetos C&T"),
        ("TX_Q219", "Formação em novas tecnologias"),
    ]

    from backend.analysis.cross_analysis import get_director_tech_gap

    # Ler Parquets fora do lock do matplotlib
    panels: list[tuple[str, list[dict[str, Any]]]] = []
    for var, title in vars_to_plot:
        try:
            result = get_director_tech_gap(var, serie, disc)
        except Exception:
            result = {}
        groups = [g for g in result.get("groups", []) if g.get("mean") is not None]
        panels.append((title, groups))

    with _PDF_LOCK:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
        try:
            for idx, (title, groups) in enumerate(panels):
                ax = axes[idx]
                if not groups:
                    ax.set_title(title)
                    ax.text(
                        0.5, 0.5, "Sem dados",
                        ha="center", va="center", transform=ax.transAxes,
                    )
                    continue

                # Rótulos oficiais do dicionário SAEB (A = Não, B = Sim)
                labels = [
                    f"{g['label']}\n(n={g['n']:,} escolas)".replace(",", ".")
                    for g in groups
                ]
                values = [g["mean"] for g in groups]
                color_by_label = {"Sim": COLORS["green"], "Não": COLORS["accent"]}
                bar_colors = [
                    color_by_label.get(g["label"], COLORS["primary"]) for g in groups
                ]
                bars = ax.bar(labels, values, color=bar_colors)
                for bar, v in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width() / 2, v + 1, f"{v:.1f}",
                            ha="center", fontsize=9)
                ax.set_title(title)
                ax.set_ylim(bottom=0)

            axes[0].set_ylabel("Proficiência média")
            fig.suptitle(
                f"Infraestrutura Tecnológica vs Proficiência - {serie} {disc} (RJ)",
                fontsize=12,
            )
            fig.tight_layout()
            return _fig_to_base64(fig)
        finally:
            plt.close(fig)


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

    labels = [a["label"] for a in analyses]
    effects = [a["cohens_d"] for a in analyses]
    colors = [COLORS["green"] if e >= 0 else COLORS["accent"] for e in effects]

    with _PDF_LOCK:
        fig, ax = plt.subplots(figsize=(8, max(3, len(analyses) * 0.6)))
        try:
            y_pos = range(len(labels))
            ax.barh(y_pos, effects, color=colors, height=0.6)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels)
            ax.axvline(x=0, color="#999", linestyle="--", linewidth=0.8)
            ax.set_xlabel("Cohen's d (tamanho de efeito)")
            ax.set_title("Tamanhos de Efeito — Variáveis Tecnológicas")

            span = max(abs(e) for e in effects) or 1.0
            for i, e in enumerate(effects):
                ax.text(
                    max(e, 0) + 0.02 * span, i, f"{e:.3f}",
                    va="center", ha="left", fontsize=9,
                )
            lo = min(min(effects), 0)
            ax.set_xlim(lo - 0.05 * span, max(max(effects), 0) + 0.25 * span)

            fig.tight_layout()
            return _fig_to_base64(fig)
        finally:
            plt.close(fig)


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
    norm_secoes, norm_series, norm_discs = _normalize_report_params(
        secoes, series, disciplinas
    )
    secoes_list = list(norm_secoes)
    series_list = list(norm_series)
    discs_list = list(norm_discs)

    data: dict[str, Any] = {
        "titulo": "Relatório de Pesquisa: IA e Educação",
        "subtitulo": "Análise de Microdados SAEB 2023 e TIC Educação 2023 — Rio de Janeiro",
        "projeto": "Ética na Tomada de Decisão por Inteligência Artificial no Ambiente Escolar",
        "instituicao": "Universidade Federal Fluminense — Faculdade de Educação",
        "data_geracao": datetime.now().strftime("%d/%m/%Y às %H:%M"),
        "series": series_list,
        "disciplinas": discs_list,
        "secoes": {},
    }

    # KPIs gerais (restritos às séries solicitadas no relatório, preservando ordem pedagógica)
    try:
        kpis_all = _query(f"SELECT * FROM kpi_rj ORDER BY {_SERIE_ORDER_SQL}")
        kpis = [r for r in kpis_all if r.get("serie") in series_list]
        escolas = _query("SELECT * FROM kpi_escolas_rj")
        data["kpis"] = kpis
        data["total_escolas"] = escolas[0].get("total_escolas", 0) if escolas else 0
        # Alunos efetivamente avaliados (presentes na prova de LP), não o
        # total de registros (que inclui ausentes)
        data["total_alunos"] = sum(r.get("presentes_lp", 0) or 0 for r in kpis)
    except Exception:
        data["kpis"] = []
        data["total_escolas"] = 0
        data["total_alunos"] = 0

    # Seção: Proficiência
    if "proficiencia" in secoes_list:
        data["secoes"]["proficiencia"] = {
            "chart_bars": chart_proficiency_bars(series_list, discs_list),
            "chart_ranking": chart_ranking(
                series_list[0],
                discs_list[0],
            ),
        }

    # Seção: Equidade
    if "equidade" in secoes_list:
        data["secoes"]["equidade"] = {
            "chart_gap": chart_equity_gap(series_list, discs_list),
            "chart_inse": chart_inse(series_list, discs_list),
        }

    # Seção: Tecnologia
    if "tecnologia" in secoes_list:
        data["secoes"]["tecnologia"] = {
            "chart_infra": chart_tic_group("infrastructure", "Infraestrutura e conectividade"),
            "chart_ai": chart_tic_group("ai", "Dados, vigilância e IA"),
            "chart_privacy": chart_tic_group("privacy", "Privacidade e proteção de dados"),
            "chart_training": chart_tic_group("teacher-training", "Formação docente em tecnologias"),
        }

    # Seção: Cruzamentos Tech x Desempenho
    if "cruzamentos" in secoes_list:
        data["secoes"]["cruzamentos"] = {
            "chart_wifi": chart_cross_student_wifi(series_list, discs_list),
            "chart_digital_index": chart_cross_digital_index(series_list, discs_list),
            "chart_director": chart_cross_director_tech(series_list, discs_list),
            "chart_forest": chart_cross_forest_plot(series_list, discs_list),
        }

    # Seção: Ética
    if "etica" in secoes_list:
        data["secoes"]["etica"] = True

    # Apêndice estatístico
    if incluir_apendice:
        try:
            gap_rows = _compute_gap_with_stats(series_list, discs_list)
            inse_rows = [
                r for r in _query(
                    f"SELECT * FROM prof_by_inse ORDER BY {_SERIE_ORDER_SQL}, disciplina, nivel_inse"
                )
                if r["serie"] in series_list and r["disciplina"] in discs_list
            ]
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


@lru_cache(maxsize=32)
def _generate_pdf_cached(
    secoes: tuple[str, ...],
    series: tuple[str, ...],
    disciplinas: tuple[str, ...],
    incluir_apendice: bool,
) -> bytes:
    """Renderiza e armazena em cache os bytes PDF para uma combinação canônica."""
    report_data = _build_report_data(
        list(secoes), list(series), list(disciplinas), incluir_apendice
    )

    # Renderizar HTML via Jinja2 (autoescape: os textos vêm de dados)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html")
    html_content = template.render(**report_data)

    # Converter para PDF via WeasyPrint (fora do lock do matplotlib)
    return HTML(string=html_content).write_pdf()


def generate_pdf(
    secoes: list[str] | None = None,
    series: list[str] | None = None,
    disciplinas: list[str] | None = None,
    incluir_apendice: bool = True,
) -> bytes:
    """Gera o relatório PDF completo e retorna os bytes do arquivo.

    Args:
        secoes: Seções a incluir (proficiencia, equidade, tecnologia,
            cruzamentos, etica). Padrão: todas.
        series: Séries do SAEB (5EF, 9EF, 34EM).
        disciplinas: Disciplinas (LP, MT).
        incluir_apendice: Se deve incluir apêndice estatístico.

    Returns:
        Bytes do PDF gerado.
    """
    norm_secoes, norm_series, norm_discs = _normalize_report_params(
        secoes, series, disciplinas
    )
    return _generate_pdf_cached(
        norm_secoes, norm_series, norm_discs, bool(incluir_apendice)
    )
