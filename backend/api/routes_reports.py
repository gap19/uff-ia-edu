"""Rotas da API para geração de relatórios PDF."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.reports.pdf_generator import generate_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


def _render_pdf_response(
    secoes: Optional[list[str]],
    series: Optional[list[str]],
    disciplinas: Optional[list[str]],
    incluir_apendice: bool,
) -> Response:
    try:
        pdf_bytes = generate_pdf(
            secoes=secoes,
            series=series,
            disciplinas=disciplinas,
            incluir_apendice=incluir_apendice,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Erro ao gerar relatório PDF")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao gerar o relatório PDF.",
        )

    filename = "relatorio_ia_educacao_uff.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate")
def generate_report(
    secoes: Optional[list[str]] = Query(
        None, description="Seções: proficiencia, equidade, tecnologia, cruzamentos, etica"
    ),
    series: Optional[list[str]] = Query(
        None, description="Séries: 5EF, 9EF, 34EM"
    ),
    disciplinas: Optional[list[str]] = Query(
        None, description="Disciplinas: LP, MT"
    ),
    incluir_apendice: bool = Query(True, description="Incluir apêndice estatístico"),
):
    """Gera relatório PDF com as seções e filtros solicitados."""
    return _render_pdf_response(secoes, series, disciplinas, incluir_apendice)


@router.get("/generate")
def generate_report_get(
    secoes: Optional[list[str]] = Query(
        None, description="Seções: proficiencia, equidade, tecnologia, cruzamentos, etica"
    ),
    series: Optional[list[str]] = Query(
        None, description="Séries: 5EF, 9EF, 34EM"
    ),
    disciplinas: Optional[list[str]] = Query(
        None, description="Disciplinas: LP, MT"
    ),
    incluir_apendice: bool = Query(True, description="Incluir apêndice estatístico"),
):
    """Gera relatório PDF via GET (conveniente para download direto do navegador)."""
    return _render_pdf_response(secoes, series, disciplinas, incluir_apendice)
