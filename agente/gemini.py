"""Conexão com o Gemini: chave, modelo, retentativas e mensagens de erro.

Na camada gratuita os limites por minuto são baixos; erros temporários
(429, 500, 503) têm até 3 tentativas com espera crescente. As retentativas
automáticas do SDK ficam desligadas para controlar o número de chamadas.
"""

from __future__ import annotations

import os
import time

import httpx
from google import genai
from google.genai import errors, types

MODELO_PADRAO = "gemini-3-flash-preview"
MAX_TENTATIVAS = 3
ESPERA_INICIAL_SEGUNDOS = 5
TIMEOUT_MS = 60_000
CODIGOS_TEMPORARIOS = {429, 500, 503}


class ErroGemini(Exception):
    """Falha ao falar com o Gemini, com mensagem pronta para o usuário."""


def obter_chave() -> str | None:
    """Lê a chave de GEMINI_API_KEY ou, como alternativa, de GOOGLE_API_KEY."""
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None


def obter_modelo() -> str:
    return os.getenv("GEMINI_MODEL", MODELO_PADRAO)


def criar_cliente(chave: str) -> genai.Client:
    opcoes = types.HttpOptions(timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1))
    return genai.Client(api_key=chave, http_options=opcoes)


def gerar(
    cliente: genai.Client,
    modelo: str,
    conteudos: list[types.Content],
    config: types.GenerateContentConfig,
    esperar=None,
) -> types.GenerateContentResponse:
    """Uma chamada ao modelo, repetida só em erros temporários."""
    esperar = esperar or time.sleep
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            return cliente.models.generate_content(model=modelo, contents=conteudos, config=config)
        except (errors.ClientError, errors.ServerError) as erro:
            if erro.code not in CODIGOS_TEMPORARIOS or tentativa == MAX_TENTATIVAS:
                raise ErroGemini(mensagem_de_erro(erro, modelo)) from erro
            esperar(ESPERA_INICIAL_SEGUNDOS * 2 ** (tentativa - 1))
        except httpx.HTTPError as erro:
            raise ErroGemini("Não foi possível conectar ao Gemini. Verifique a internet e tente de novo.") from erro
    raise AssertionError("inalcançável")


def mensagem_de_erro(erro: errors.APIError, modelo: str) -> str:
    if erro.code == 429:
        return (
            "Limite de uso da camada gratuita do Gemini atingido. Aguarde um minuto e tente de novo. "
            "Se persistir, o limite diário pode ter acabado: tente amanhã ou troque o modelo em GEMINI_MODEL."
        )
    if erro.code in (500, 503):
        return "Os servidores do Gemini estão sobrecarregados. Tente de novo em alguns minutos."
    if erro.code in (400, 401, 403) and "API key" in str(erro.message):
        return "A chave da API foi recusada. Confira a chave informada (ou o valor de GEMINI_API_KEY)."
    if erro.code == 404:
        return f"Modelo '{modelo}' não encontrado. Confira a variável GEMINI_MODEL."
    return f"Erro da API do Gemini ({erro.code}): {erro.message}"
