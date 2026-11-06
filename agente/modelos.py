"""Modelos do veredito que o agente entrega."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from verificadores.modelos import ResultadoBoleto, ResultadoLink, ResultadoPix

Nivel = Literal["provavel_golpe", "atencao", "sem_sinais"]
Gravidade = Literal["alta", "media", "baixa", "info"]
Fonte = Literal["verificador", "regra", "ia"]

ORDEM_NIVEL: dict[Nivel, int] = {"sem_sinais": 0, "atencao": 1, "provavel_golpe": 2}
ROTULO_NIVEL: dict[Nivel, str] = {
    "provavel_golpe": "Provável golpe",
    "atencao": "Atenção",
    "sem_sinais": "Sem sinais de golpe",
}


class Sinal(BaseModel):
    """Um motivo de alerta, explicado para quem não entende de tecnologia."""

    descricao: str
    gravidade: Gravidade
    fonte: Fonte = Field(
        description=(
            "'verificador': conferido num código Pix, boleto ou link (prova); "
            "'regra': padrão de texto conhecido de golpes; 'ia': interpretação do modelo"
        ),
    )


class Veredito(BaseModel):
    nivel: Nivel
    resumo: str
    sinais: list[Sinal] = Field(default_factory=list)
    o_que_fazer: list[str] = Field(default_factory=list)
    marca_alegada: str | None = Field(default=None, description="Quem a mensagem diz ser")
    texto_do_print: str | None = Field(default=None, description="Texto da mensagem transcrito do print pela IA")

    pix: list[ResultadoPix] = Field(default_factory=list)
    boletos: list[ResultadoBoleto] = Field(default_factory=list)
    links: list[ResultadoLink] = Field(default_factory=list)

    usou_ia: bool = False
    ferramentas_chamadas: list[str] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)

    @property
    def rotulo(self) -> str:
        return ROTULO_NIVEL[self.nivel]

    @property
    def provas(self) -> list[Sinal]:
        return [s for s in self.sinais if s.fonte == "verificador"]


def nivel_mais_grave(*niveis: Nivel) -> Nivel:
    return max(niveis, key=ORDEM_NIVEL.__getitem__)
