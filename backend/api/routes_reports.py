"""Rotas da API para geração de relatórios PDF."""

from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response

from backend.reports.pdf_generator import generate_pdf

router = APIRouter()


@router.post("/generate")
async def generate_report(
    secoes: Optional[list[str]] = Query(
        None, description="Seções: proficiencia, equidade, tecnologia, etica"
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
    pdf_bytes = generate_pdf(
        secoes=secoes,
        series=series,
        disciplinas=disciplinas,
        incluir_apendice=incluir_apendice,
    )

    filename = "relatorio_ia_educacao_uff.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/generate")
async def generate_report_get(
    secoes: Optional[list[str]] = Query(
        None, description="Seções: proficiencia, equidade, tecnologia, etica"
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
    pdf_bytes = generate_pdf(
        secoes=secoes,
        series=series,
        disciplinas=disciplinas,
        incluir_apendice=incluir_apendice,
    )

    filename = "relatorio_ia_educacao_uff.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
