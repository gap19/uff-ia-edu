"""Parse R scripts to extract variable labels and response options for SAEB 2023.

The INEP-provided R scripts in INPUTS/ contain commented-out factor() calls
that define the mapping between coded values and human-readable labels for
each variable.  The TS_ESCOLA script also has a ``labels <- list(...)`` block
with variable descriptions.

All R files are encoded in latin-1 (ISO-8859-1).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from backend.config import SAEB_INPUTS_DIR

# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------
_codebook_cache: Optional[dict] = None
_variable_labels_cache: Optional[dict] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_r_file(path: Path) -> str:
    """Read an R script encoded in latin-1 and return its text."""
    return path.read_text(encoding="latin-1")


def _parse_r_values(raw: str) -> list[str]:
    """Parse a comma-separated R vector body into a list of string values.

    Handles both quoted strings (``'A'``, ``"A"``) and unquoted numbers.
    """
    values: list[str] = []
    for token in re.finditer(r"""'([^']*)'|"([^"]*)"|([^\s,'"]+)""", raw):
        values.append(token.group(1) or token.group(2) or token.group(3))
    return values


def _extract_factor_definitions(text: str, table_name: str) -> dict:
    """Extract factor() calls from an R script.

    Returns ``{column_name: {"levels": [...], "labels": [...]}}``.

    The factor calls may span multiple lines (the escola script wraps them)
    and are always commented out with ``#``.
    """
    # First, join continuation lines: a commented line ending with a comma
    # followed by another commented line is part of the same statement.
    # We strip leading ``# `` and re-join so that the factor regex can match
    # multi-line calls.
    comment_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            # Remove leading '# ' or '#'
            content = re.sub(r"^#\s?", "", stripped)
            comment_lines.append(content)
        else:
            # Keep non-comment lines so that line indices stay aligned; they
            # won't match the factor pattern anyway.
            comment_lines.append(stripped)

    joined = "\n".join(comment_lines)

    # Pattern:  TABLE$COLUMN <- factor(TABLE$COLUMN, levels = c(...), labels = c(...))
    # The TABLE name inside the call may differ from the one we derived from
    # the filename, so we capture the column from the assignment target.
    pattern = re.compile(
        r"(?P<tbl>\w+)\$(?P<col>\w+)\s*<-\s*factor\("
        r"[^,]+,\s*"                               # first arg (the vector)
        r"levels\s*=\s*c\((?P<levels>[^)]+)\)\s*,\s*"
        r"labels\s*=\s*c\((?P<labels>[^)]+)\)\s*\)",
        re.DOTALL,
    )

    result: dict = {}
    for m in pattern.finditer(joined):
        col = m.group("col")
        levels = _parse_r_values(m.group("levels"))
        labels = _parse_r_values(m.group("labels"))
        result[col] = {"levels": levels, "labels": labels}

    return result


def _extract_variable_labels(text: str) -> dict[str, str]:
    """Extract the ``labels <- list(...)`` block from the TS_ESCOLA R script.

    Returns ``{VARIABLE_NAME: "description text"}``.
    """
    # Match the whole labels <- list(...) block.
    block_match = re.search(
        r"labels\s*<-\s*list\((.+?)\)", text, re.DOTALL
    )
    if not block_match:
        return {}

    body = block_match.group(1)

    result: dict[str, str] = {}
    # Each entry:  VAR_NAME = 'some description'
    for m in re.finditer(
        r"(\w+)\s*=\s*'([^']*)'", body
    ):
        result[m.group(1)] = m.group(2)

    return result


def _table_name_from_filename(filename: str) -> str:
    """Derive the table name from an R script filename.

    ``INPUT_R_TS_ALUNO_5EF.R`` -> ``TS_ALUNO_5EF``
    """
    name = filename.removesuffix(".R")
    name = name.removeprefix("INPUT_R_")
    return name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_codebook() -> dict[str, dict[str, dict]]:
    """Parse all R scripts and return the full codebook.

    Returns::

        {
            "TS_ALUNO_5EF": {
                "ID_REGIAO": {"levels": ["1","2",...], "labels": ["Norte",...]},
                ...
            },
            ...
        }

    The result is cached after the first call.
    """
    global _codebook_cache  # noqa: PLW0603
    if _codebook_cache is not None:
        return _codebook_cache

    codebook: dict[str, dict[str, dict]] = {}

    for r_file in sorted(SAEB_INPUTS_DIR.glob("INPUT_R_*.R")):
        table = _table_name_from_filename(r_file.name)
        text = _read_r_file(r_file)
        factors = _extract_factor_definitions(text, table)
        if factors:
            codebook[table] = factors

    _codebook_cache = codebook
    return codebook


def _load_variable_labels() -> dict[str, str]:
    """Parse and cache the variable description labels from TS_ESCOLA."""
    global _variable_labels_cache  # noqa: PLW0603
    if _variable_labels_cache is not None:
        return _variable_labels_cache

    escola_path = SAEB_INPUTS_DIR / "INPUT_R_TS_ESCOLA.R"
    if escola_path.exists():
        text = _read_r_file(escola_path)
        _variable_labels_cache = _extract_variable_labels(text)
    else:
        _variable_labels_cache = {}

    return _variable_labels_cache


def get_variable_label(table: str, column: str) -> str:
    """Return the human-readable description for a variable.

    Looks up the ``labels <- list(...)`` section from the escola script,
    which contains descriptions that apply across tables.  Returns an empty
    string if no description is found.
    """
    labels = _load_variable_labels()
    return labels.get(column, "")


def get_response_labels(table: str, column: str) -> dict[str, str]:
    """Return a mapping of level values to label texts for a variable.

    Example::

        >>> get_response_labels("TS_ALUNO_5EF", "TX_RESP_Q01_")
        {"*": "Nulo", ".": "Branco", "A": "Masculino", ...}

    Returns an empty dict if the table/column is not found.
    """
    codebook = load_codebook()
    entry = codebook.get(table, {}).get(column)
    if entry is None:
        return {}
    return dict(zip(entry["levels"], entry["labels"]))
