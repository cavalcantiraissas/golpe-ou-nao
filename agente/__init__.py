"""Agente que analisa mensagens suspeitas e explica o veredito com provas."""

from agente.analise import analisar_mensagem
from agente.modelos import Sinal, Veredito

__all__ = ["Sinal", "Veredito", "analisar_mensagem"]
