"""Indicadores TIC Educação 2023 (CETIC.br) usados no dashboard.

Cada grupo temático é uma lista curada de indicadores das tabelas oficiais
(``tic_educacao_2023_escolas_tabela_*_v1.0.xlsx``), sempre na resposta
indicada (em geral "Sim"). Para indicadores com subitens (ex.: E6, F6, J2),
``item`` identifica o subitem pelo início do texto do cabeçalho oficial.

Os valores são apresentados para a região **Sudeste** (proxy para o Rio de
Janeiro — a pesquisa não divulga dados por UF) e para o **Brasil** (linha
TOTAL), com as margens de erro publicadas pelo CETIC.br.
"""

from __future__ import annotations

from typing import Any

from backend.db import db_query

TIC_SOURCE = "CGI.br/NIC.br, Cetic.br — Pesquisa TIC Educação 2023 (escolas)"
REGION_PRIMARY = "Sudeste"
REGION_REFERENCE = "Brasil"

# Universos diferentes do "Total de escolas de Ensino Fundamental e Médio"
# recebem uma nota no rótulo (¹).
_DEFAULT_UNIVERSE = "Total de escolas de Ensino Fundamental e Médio"

TIC_GROUPS: dict[str, dict[str, Any]] = {
    "infrastructure": {
        "label": "Infraestrutura e conectividade",
        "indicators": [
            {"code": "B1", "label": "Possui computador"},
            {"code": "A1", "label": "Acesso à internet"},
            {"code": "A6", "label": "Computador e internet"},
            {"code": "B1B", "label": "Computador para uso dos alunos"},
            {"code": "A7", "label": "Internet para uso dos alunos"},
            {"code": "A8", "label": "Computador e internet para os alunos"},
            {"code": "A4", "label": "Rede sem fio¹"},
            {"code": "A2", "resposta": "Conexão via fibra ótica", "label": "Conexão por fibra ótica¹"},
        ],
    },
    "ai": {
        "label": "Dados, vigilância e inteligência artificial",
        "indicators": [
            {"code": "E3", "label": "Câmeras de vídeo internas"},
            {"code": "E4A", "label": "Biometria (digital/palma)"},
            {"code": "E4B", "label": "Reconhecimento facial"},
            {"code": "E6", "item": "Relatórios, estatísticas e gráficos gerados por sistemas de Business Intelligence",
             "label": "Business Intelligence na gestão"},
            {"code": "E6", "item": "Sistemas de Inteligência Artificial",
             "label": "Sistemas de IA na gestão"},
            {"code": "F6", "item": "Monitoramento das atividades dos alunos por meio de acesso às câmeras",
             "label": "Câmeras acessíveis pelo app"},
            {"code": "F6", "item": "Atendimento automatizado",
             "label": "Chatbot no app da escola"},
        ],
    },
    "privacy": {
        "label": "Privacidade e proteção de dados",
        "indicators": [
            {"code": "H1", "label": "Política de proteção de dados"},
            {"code": "H3", "label": "Debates sobre privacidade"},
            {"code": "H5", "label": "Dúvidas de pais sobre privacidade"},
            {"code": "H6", "label": "Deixou de adotar recurso por privacidade"},
        ],
    },
    "teacher-training": {
        "label": "Formação docente em tecnologias",
        "indicators": [
            {"code": "J1", "label": "Ofertou formação em tecnologias"},
            {"code": "J3", "label": "Participa de programa de formação"},
            {"code": "J2", "item": "Linguagem de programação e robótica",
             "label": "Tema: programação e robótica"},
            {"code": "J2", "item": "Criação de conteúdos educacionais digitais",
             "label": "Tema: conteúdos digitais"},
            {"code": "J2", "item": "Fake news", "label": "Tema: fake news"},
            {"code": "J2", "item": "Uso de tecnologias na avaliação",
             "label": "Tema: tecnologia na avaliação"},
        ],
    },
    "digital-literacy": {
        "label": "Uso seguro, responsável e crítico da internet",
        "indicators": [
            {"code": "I1", "label": "Promoveu formação sobre uso seguro"},
            {"code": "I3", "item": "Alunos", "label": "Público: alunos"},
            {"code": "I3", "item": "Professores", "label": "Público: professores"},
            {"code": "I3", "item": "Pais e responsáveis", "label": "Público: pais e responsáveis"},
        ],
    },
}


def _match(spec: dict[str, Any], row: dict[str, Any]) -> bool:
    if row["indicador"] != spec["code"]:
        return False
    if row["resposta"] != spec.get("resposta", "Sim"):
        return False
    item = spec.get("item")
    if item is None:
        return row["item"] is None
    return (row["item"] or "").lower().startswith(item.lower())


def get_tic_group(group: str) -> dict[str, Any]:
    """Valores (Sudeste e Brasil) dos indicadores curados de um grupo."""
    if group not in TIC_GROUPS:
        raise KeyError(group)
    cfg = TIC_GROUPS[group]
    codes = sorted({spec["code"] for spec in cfg["indicators"]})
    placeholders = ", ".join("?" for _ in codes)
    rows = db_query(
        f"""
        SELECT indicador, titulo, universo, tipo, valor_corte, item, resposta, valor
        FROM tic_indicadores
        WHERE indicador IN ({placeholders})
          AND tipo IN ('proporcao', 'margem_erro')
          AND (valor_corte = 'TOTAL' OR (variavel_corte = 'REGIÃO' AND valor_corte = ?))
        """,
        [*codes, REGION_PRIMARY],
    )

    data: list[dict[str, Any]] = []
    for spec in cfg["indicators"]:
        matched = [r for r in rows if _match(spec, r)]
        if not matched:
            continue

        def pick(tipo: str, corte: str) -> float | None:
            for r in matched:
                if r["tipo"] == tipo and r["valor_corte"] == corte:
                    return r["valor"]
            return None

        first = matched[0]
        universo = first["universo"]
        data.append({
            "indicador": spec["code"],
            "label": spec["label"],
            "titulo": first["titulo"],
            "item": first["item"],
            "resposta": first["resposta"],
            "universo": universo,
            "universo_especifico": bool(universo and universo != _DEFAULT_UNIVERSE),
            "sudeste": pick("proporcao", REGION_PRIMARY),
            "brasil": pick("proporcao", "TOTAL"),
            "me_sudeste": pick("margem_erro", REGION_PRIMARY),
            "me_brasil": pick("margem_erro", "TOTAL"),
        })

    note = (
        "Percentual de escolas (resposta indicada) na região Sudeste — proxy para o "
        "Rio de Janeiro, pois a pesquisa não divulga dados por UF — e no Brasil."
    )
    if any(d["universo_especifico"] for d in data):
        note += " ¹ Universo: escolas com acesso à internet."
    return {
        "group": cfg["label"],
        "source": TIC_SOURCE,
        "regions": {"primary": REGION_PRIMARY, "reference": REGION_REFERENCE},
        "note": note,
        "count": len(data),
        "data": data,
    }
