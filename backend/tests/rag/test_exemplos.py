from pathlib import Path

import pytest

from app.rag.chunking import validar_texto

EXEMPLOS = sorted((Path(__file__).resolve().parents[2] / "data" / "exemplos").glob("*.md"))


def test_existem_exemplos():
    assert len(EXEMPLOS) >= 2


@pytest.mark.parametrize("arquivo", EXEMPLOS, ids=lambda p: p.name)
def test_exemplo_dentro_dos_limites(arquivo):
    validar_texto(arquivo.read_text(encoding="utf-8"))
