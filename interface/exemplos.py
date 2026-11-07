"""Mensagens de exemplo para experimentar o agente sem ter um golpe em mãos."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from pydantic import BaseModel

from agente.modelos import Nivel

PASTA_EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"


class Exemplo(BaseModel):
    id: str
    titulo: str
    descricao: str
    texto: str = ""
    imagem: str | None = None
    nivel_esperado: Nivel

    @property
    def caminho_imagem(self) -> Path | None:
        return PASTA_EXEMPLOS / self.imagem if self.imagem else None

    @property
    def tipo_imagem(self) -> str:
        if not self.imagem:
            return "image/png"
        return mimetypes.guess_type(self.imagem)[0] or "image/png"

    def ler_imagem(self) -> bytes | None:
        caminho = self.caminho_imagem
        return caminho.read_bytes() if caminho else None


def carregar_exemplos(pasta: Path = PASTA_EXEMPLOS) -> list[Exemplo]:
    dados = json.loads((pasta / "mensagens.json").read_text(encoding="utf-8"))
    return [Exemplo.model_validate(item) for item in dados]
