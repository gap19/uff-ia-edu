"""Fixtures compartilhadas para os testes."""

import sys
from pathlib import Path

import pytest

# Garantir que o projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
