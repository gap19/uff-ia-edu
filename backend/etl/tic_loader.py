"""Conversão de tabelas TIC Educação 2023 (Excel) para Parquet.

Lê os 4 arquivos XLSX da pesquisa TIC Educação 2023 — escolas (proporção,
total, margem de erro e margem de erro do total), publicados pelo CETIC.br em
https://cetic.br/media/microdados/786/tic_educacao_2023_escolas_tabelas_xlsx_v1.0.zip
— e normaliza as planilhas em formato longo num único Parquet.

Layout de cada planilha (um indicador por aba, ex.: A1, E6):

* linha 1: título ("A1 - ESCOLAS COM ACESSO À INTERNET");
* linha 2: universo ("Total de escolas de Ensino Fundamental e Médio");
* linhas 3–4: cabeçalho. Indicadores simples têm as opções de resposta na
  linha 3 (células mescladas com a linha 4). Indicadores com subitens têm o
  subitem na linha 3 (mesclado na horizontal) e a resposta na linha 4;
* a partir da linha 5: coluna A = variável de corte (TOTAL, REGIÃO, ...,
  mesclada na vertical), coluna B = categoria (Norte, Sudeste, ...), e os
  valores a partir da coluna C; termina na linha "Fonte: ...".

Colunas do Parquet: indicador, titulo, universo, tipo, variavel_corte,
valor_corte, item, resposta, coluna, valor.
"""

from __future__ import annotations

import logging
import math
import re
import warnings
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from backend.config import TIC_PARQUET_DIR, TIC_XLSX_FILES

logger = logging.getLogger(__name__)

# Primeira linha de dados (linhas 1–4 são título, universo e cabeçalhos)
_FIRST_DATA_ROW = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_text(value: Any) -> str | None:
    """Converte valor de célula em texto limpo (espaços normalizados) ou None."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _parse_numeric(value: Any) -> float | None:
    """Tenta converter um valor de célula em float finito.

    Retorna None para booleanos, não-finitos (NaN/Inf) e marcadores de
    ausência como '-', '*', '..', texto vazio. Aceita separador decimal
    brasileiro (``'92,4'``) e separador de milhar (``'1.234,5'``).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) else None
    text = str(value).strip()
    # Valores comuns que indicam ausência de dado
    if text in ("", "-", "*", "..", "…", "—", "–", "0*", "**"):
        return None
    # Formato brasileiro com vírgula decimal (e eventual ponto de milhar)
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        num = float(text)
    except ValueError:
        return None
    return num if math.isfinite(num) else None


def _merged_lookup(ws: Worksheet) -> dict[tuple[int, int], Any]:
    """Mapeia (linha, coluna) de cada célula mesclada ao valor do canto superior esquerdo."""
    lookup: dict[tuple[int, int], Any] = {}
    for rng in ws.merged_cells.ranges:
        top_left = ws.cell(row=rng.min_row, column=rng.min_col).value
        for r in range(rng.min_row, rng.max_row + 1):
            for c in range(rng.min_col, rng.max_col + 1):
                lookup[(r, c)] = top_left
    return lookup


def _strip_indicator_prefix(title: str | None, code: str) -> str | None:
    """'A1 - ESCOLAS COM ...' -> 'ESCOLAS COM ...'."""
    if not title:
        return title
    return re.sub(rf"^{re.escape(code)}\s*-\s*", "", title).strip()


# ---------------------------------------------------------------------------
# Parser principal de planilha
# ---------------------------------------------------------------------------


def parse_tic_sheet(
    ws: Worksheet,
    sheet_name: str,
    tipo: str,
) -> list[dict[str, Any]]:
    """Analisa uma planilha TIC e retorna linhas normalizadas.

    Parameters
    ----------
    ws:
        Planilha openpyxl já carregada (``read_only=False``, para ler as
        células mescladas).
    sheet_name:
        Nome da planilha (código do indicador, ex.: "A1").
    tipo:
        Tipo de arquivo: 'proporcao', 'total', 'margem_erro',
        'margem_erro_total'.

    Returns
    -------
    list[dict]
        Dicts com as chaves: indicador, titulo, universo, tipo,
        variavel_corte, valor_corte, item, resposta, coluna, valor.
    """
    rows: list[dict[str, Any]] = []
    max_row, max_col = ws.max_row or 0, ws.max_column or 0
    if max_row < _FIRST_DATA_ROW or max_col < 3:
        logger.warning("[tic_loader] Planilha '%s' vazia ou muito pequena, pulando.", sheet_name)
        return rows

    merged = _merged_lookup(ws)

    def value(r: int, c: int) -> Any:
        v = ws.cell(row=r, column=c).value
        return merged.get((r, c)) if v is None else v

    titulo = _strip_indicator_prefix(_clean_text(ws.cell(row=1, column=1).value), sheet_name)
    universo = _clean_text(ws.cell(row=2, column=1).value)

    # Indicador com subitens: a linha 4 tem respostas próprias (não mescladas
    # com a linha 3). Nos simples, a linha 4 só existe como parte da mesclagem.
    has_items = any(
        _clean_text(ws.cell(row=4, column=c).value) for c in range(3, max_col + 1)
    )

    columns: list[tuple[int, str | None, str]] = []  # (col, item, resposta)
    for c in range(3, max_col + 1):
        h3 = _clean_text(value(3, c))
        if has_items:
            resposta = _clean_text(ws.cell(row=4, column=c).value)
            item = h3
        else:
            resposta, item = h3, None
        if resposta:
            columns.append((c, item, resposta))

    variavel_corte: str | None = None
    for r in range(_FIRST_DATA_ROW, max_row + 1):
        first = _clean_text(value(r, 1))
        if first and first.lower().startswith("fonte"):
            break
        if first:
            variavel_corte = first
        categoria = _clean_text(value(r, 2)) or variavel_corte
        if not variavel_corte or not categoria:
            continue
        for idx, (c, item, resposta) in enumerate(columns, start=1):
            num = _parse_numeric(ws.cell(row=r, column=c).value)
            if num is None:
                continue
            rows.append({
                "indicador": sheet_name,
                "titulo": titulo,
                "universo": universo,
                "tipo": tipo,
                "variavel_corte": variavel_corte,
                "valor_corte": categoria,
                "item": item,
                "resposta": resposta,
                "coluna": idx,
                "valor": num,
            })

    return rows


# ---------------------------------------------------------------------------
# Inventário de indicadores
# ---------------------------------------------------------------------------


def get_tic_indicators() -> list[str]:
    """Retorna lista de códigos de indicadores disponíveis nos arquivos TIC.

    Lê os nomes das planilhas do primeiro arquivo disponível.
    """
    for tipo, path in TIC_XLSX_FILES.items():
        if path.exists():
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            names = list(wb.sheetnames)
            wb.close()
            return names
    return []


# ---------------------------------------------------------------------------
# Carga principal
# ---------------------------------------------------------------------------


def _open_workbook_safe(xlsx_path: Path):
    """Abre workbook ignorando drawings corrompidos.

    Alguns XLSX da pesquisa TIC referenciam 'xl/drawings/drawing1.xml' que
    não existe no arquivo ZIP.  O openpyxl tenta ler esse item e falha com
    KeyError.  Aqui fazemos monkey-patch temporário no ZipFile.read para
    retornar XML vazio em vez de falhar.
    """
    import zipfile

    _orig_read = zipfile.ZipFile.read

    def _patched_read(self, name, pwd=None):
        try:
            return _orig_read(self, name, pwd)
        except KeyError:
            if "drawing" in str(name).lower():
                logger.debug(
                    "[tic_loader] Drawing ausente ignorado: %s", name
                )
                return b'<?xml version="1.0" encoding="UTF-8"?><root/>'
            raise

    setattr(zipfile.ZipFile, "read", _patched_read)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = openpyxl.load_workbook(
                str(xlsx_path), read_only=False, data_only=True
            )
    finally:
        setattr(zipfile.ZipFile, "read", _orig_read)

    return wb


def load_all_tic() -> int:
    """Processa todos os 4 arquivos TIC e exporta Parquet consolidado.

    Returns
    -------
    int
        Total de linhas no Parquet resultante.
    """
    TIC_PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TIC_PARQUET_DIR / "tic_educacao_2023.parquet"

    all_rows: list[dict[str, Any]] = []
    total_sheets = 0
    skipped_sheets = 0

    for tipo, xlsx_path in TIC_XLSX_FILES.items():
        if not xlsx_path.exists():
            logger.warning(
                "[tic_loader] Arquivo não encontrado: %s, pulando.", xlsx_path
            )
            continue

        print(f"[tic_loader] Abrindo {xlsx_path.name} (tipo={tipo})...")

        # read_only=False para ler as células mescladas; alguns XLSX
        # referenciam drawings ausentes (contornado em _open_workbook_safe).
        try:
            wb = _open_workbook_safe(xlsx_path)
        except Exception as exc:
            logger.error(
                "[tic_loader] Falha ao abrir %s: %s", xlsx_path.name, exc
            )
            continue

        for sheet_name in wb.sheetnames:
            total_sheets += 1
            try:
                ws = wb[sheet_name]
                sheet_rows = parse_tic_sheet(ws, sheet_name, tipo)
                all_rows.extend(sheet_rows)
                print(
                    f"  [{tipo}] {sheet_name}: {len(sheet_rows)} registros"
                )
            except Exception:
                skipped_sheets += 1
                logger.warning(
                    "[tic_loader] Erro ao processar planilha '%s' de %s, pulando.",
                    sheet_name,
                    xlsx_path.name,
                    exc_info=True,
                )

        wb.close()

    if not all_rows:
        warnings.warn(
            "[tic_loader] Nenhum dado extraído dos arquivos TIC.",
            stacklevel=2,
        )
        return 0

    # --- Salvar como Parquet via pyarrow ---
    print(f"\n[tic_loader] Total de registros: {len(all_rows):,}")
    print(f"[tic_loader] Planilhas processadas: {total_sheets - skipped_sheets}/{total_sheets}")

    _save_parquet(all_rows, output_path)

    print(f"[tic_loader] Parquet salvo em: {output_path}")
    return len(all_rows)


_COLUMNS: list[tuple[str, str]] = [
    ("indicador", "VARCHAR"), ("titulo", "VARCHAR"), ("universo", "VARCHAR"),
    ("tipo", "VARCHAR"), ("variavel_corte", "VARCHAR"), ("valor_corte", "VARCHAR"),
    ("item", "VARCHAR"), ("resposta", "VARCHAR"), ("coluna", "INTEGER"),
    ("valor", "DOUBLE"),
]


def _save_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    """Salva lista de dicts como Parquet (via DuckDB, já dependência do projeto)."""
    import duckdb

    con = duckdb.connect()
    try:
        cols_sql = ", ".join(f"{name} {typ}" for name, typ in _COLUMNS)
        con.execute(f"CREATE TABLE tic_data ({cols_sql})")
        con.executemany(
            f"INSERT INTO tic_data VALUES ({', '.join('?' for _ in _COLUMNS)})",
            [tuple(r[name] for name, _ in _COLUMNS) for r in rows],
        )
        con.execute(
            f"COPY (SELECT * FROM tic_data ORDER BY indicador, tipo, coluna) "
            f"TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Execução direta
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    total = load_all_tic()
    print(f"\n[tic_loader] Concluído: {total:,} registros totais.")
