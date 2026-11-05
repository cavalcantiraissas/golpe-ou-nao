"""Modelos de saída das ferramentas de verificação.

Cada ferramenta devolve um objeto destes, nunca levanta exceção para entrada
ruim: um código malformado também é informação útil para o agente
(``valido=False`` com a lista de ``erros``).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

TipoChavePix = Literal["cpf", "cnpj", "telefone", "email", "aleatoria", "desconhecida"]
TipoRecebedor = Literal["pessoa_fisica", "pessoa_juridica", "indefinido"]


class ResultadoPix(BaseModel):
    """O que um Pix copia e cola (BR Code) revela sobre o recebedor."""

    valido: bool = Field(description="Estrutura correta e CRC conferido")
    crc_ok: bool = False
    erros: list[str] = Field(default_factory=list)

    dinamico: bool = Field(
        default=False,
        description="QR dinâmico: os dados finais da cobrança ficam numa URL do banco",
    )
    chave: str | None = None
    tipo_chave: TipoChavePix = "desconhecida"
    url_cobranca: str | None = None
    nome_recebedor: str | None = None
    cidade: str | None = None
    valor: Decimal | None = Field(default=None, description="None quando o valor é livre")
    identificador: str | None = Field(default=None, description="txid da transação")
    descricao: str | None = None
    tipo_recebedor: TipoRecebedor = "indefinido"


TipoBoleto = Literal["bancario", "arrecadacao", "desconhecido"]


class ResultadoBoleto(BaseModel):
    """O que a linha digitável de um boleto revela."""

    valido: bool = Field(description="Todos os dígitos verificadores conferem")
    erros: list[str] = Field(default_factory=list)

    tipo: TipoBoleto = "desconhecido"
    linha_digitavel: str | None = None
    codigo_barras: str | None = None

    # Boleto bancário
    codigo_banco: str | None = None
    nome_banco: str | None = None

    # Conta de consumo / tributo (arrecadação)
    segmento: str | None = None
    codigo_empresa: str | None = None

    valor: Decimal | None = Field(default=None, description="None quando o valor está em aberto")
    vencimento: date | None = None


StatusSafeBrowsing = Literal["nao_consultado", "limpo", "perigoso", "erro"]


class ResultadoLink(BaseModel):
    """Sinais de risco encontrados num link, sem nunca abri-lo."""

    url: str
    host: str | None = None
    dominio: str | None = Field(default=None, description="Domínio registrável, ex.: exemplo.com.br")
    https: bool = False
    encurtador: bool = False
    marca_imitada: str | None = None
    safe_browsing: StatusSafeBrowsing = "nao_consultado"
    ameacas: list[str] = Field(default_factory=list)
    sinais: list[str] = Field(default_factory=list, description="Sinais explicados em português simples")
