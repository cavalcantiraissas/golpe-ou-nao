"""Como cada parte do veredito aparece na tela.

Funções puras (sem Streamlit) para poderem ser testadas: rótulos, cores e as
linhas dos cartões de prova de Pix, boleto e link.
"""

from __future__ import annotations

import re

from agente.cruzamento import reais
from agente.modelos import Fonte, Gravidade, Nivel
from verificadores.modelos import ResultadoBoleto, ResultadoLink, ResultadoPix

# Cor da faixa do veredito (nomes aceitos pelo Streamlit) e ícone.
ESTILO_NIVEL: dict[Nivel, tuple[str, str]] = {
    "provavel_golpe": ("error", "🚨"),
    "atencao": ("warning", "⚠️"),
    "sem_sinais": ("success", "✅"),
}

ICONE_GRAVIDADE: dict[Gravidade, str] = {"alta": "🔴", "media": "🟠", "baixa": "🟡", "info": "🔵"}

ROTULO_FONTE: dict[Fonte, str] = {
    "verificador": "prova",
    "regra": "padrão de golpe",
    "ia": "análise da IA",
}

# Etiqueta colorida do Markdown do Streamlit (:cor-badge[texto]).
COR_FONTE: dict[Fonte, str] = {"verificador": "blue", "regra": "violet", "ia": "gray"}


def etiqueta(fonte: Fonte) -> str:
    return f":{COR_FONTE[fonte]}-badge[{ROTULO_FONTE[fonte]}]"


EXPLICACAO_FONTE = (
    f"{etiqueta('verificador')} conferido dentro do código Pix, do boleto ou do link · "
    f"{etiqueta('regra')} frase típica de golpes conhecidos · "
    f"{etiqueta('ia')} interpretação do modelo"
)

ROTULO_RECEBEDOR = {"pessoa_fisica": "Pessoa física", "pessoa_juridica": "Empresa", "indefinido": "Não dá para saber"}

ROTULO_CHAVE = {
    "cpf": "CPF",
    "cnpj": "CNPJ",
    "telefone": "Telefone",
    "email": "E-mail",
    "aleatoria": "Chave aleatória",
    "desconhecida": "Desconhecida",
}

ROTULO_SAFE_BROWSING = {
    "nao_consultado": "Não consultado",
    "limpo": "Nenhum alerta",
    "perigoso": "Site marcado como perigoso",
    "erro": "Não foi possível consultar",
}


def linha_do_sinal(gravidade: Gravidade, fonte: Fonte, descricao: str) -> str:
    return f"{ICONE_GRAVIDADE[gravidade]} {escapar(descricao)} {etiqueta(fonte)}"


def _conferencia(valido: bool) -> str:
    return "✅ Confere" if valido else "❌ Não confere"


def linhas_pix(pix: ResultadoPix) -> list[tuple[str, str]]:
    linhas = [("Quem recebe", pix.nome_recebedor or "—")]
    linhas.append(("Tipo", ROTULO_RECEBEDOR[pix.tipo_recebedor]))
    if pix.cidade:
        linhas.append(("Cidade", pix.cidade.title()))
    linhas.append(("Valor", reais(pix.valor) if pix.valor is not None else "Em aberto"))
    if pix.chave:
        linhas.append((f"Chave ({ROTULO_CHAVE[pix.tipo_chave]})", pix.chave))
    if pix.url_cobranca:
        linhas.append(("Cobrança dinâmica", pix.url_cobranca))
    linhas.append(("Conferência do código", _conferencia(pix.valido)))
    return linhas


def linhas_boleto(boleto: ResultadoBoleto) -> list[tuple[str, str]]:
    if boleto.tipo == "arrecadacao":
        linhas = [("Tipo", "Conta de consumo ou tributo"), ("Segmento", boleto.segmento or "—")]
    else:
        banco = f"{boleto.nome_banco} ({boleto.codigo_banco})" if boleto.nome_banco else boleto.codigo_banco or "—"
        linhas = [("Tipo", "Boleto bancário"), ("Banco", banco)]
    linhas.append(("Valor", reais(boleto.valor) if boleto.valor is not None else "Em aberto"))
    if boleto.vencimento:
        linhas.append(("Vencimento", f"{boleto.vencimento:%d/%m/%Y}"))
    linhas.append(("Dígitos verificadores", _conferencia(boleto.valido)))
    return linhas


def linhas_link(link: ResultadoLink) -> list[tuple[str, str]]:
    linhas = [("Endereço do site", link.dominio or link.host or link.url)]
    if link.marca_imitada:
        linhas.append(("Imita", link.marca_imitada))
    linhas.append(("Cadeado (HTTPS)", "Sim" if link.https else "Não"))
    if link.encurtador:
        linhas.append(("Encurtador", "Sim: esconde o destino real"))
    linhas.append(("Lista de sites perigosos do Google", ROTULO_SAFE_BROWSING[link.safe_browsing]))
    return linhas


def titulo_do_pix(pix: ResultadoPix, indice: int) -> str:
    return f"Pix {indice}: {pix.nome_recebedor}" if pix.nome_recebedor else f"Pix {indice}"


def titulo_do_boleto(boleto: ResultadoBoleto, indice: int) -> str:
    return f"Boleto {indice}: {boleto.nome_banco or boleto.segmento or 'não identificado'}"


def titulo_do_link(link: ResultadoLink, indice: int) -> str:
    return f"Link {indice}: {link.dominio or link.host or link.url}"


def em_markdown(linhas: list[tuple[str, str]]) -> str:
    """Uma linha "**rótulo:** valor" por item (o valor sai como texto, sem formatação)."""
    return "  \n".join(f"**{rotulo}:** {escapar(valor)}" for rotulo, valor in linhas)


def escapar(texto: str) -> str:
    """Mostra o texto como está no Markdown do Streamlit.

    Nomes, chaves, endereços e frases da IA não podem virar formatação, link
    clicável ou fórmula (no Streamlit, dois "R$" na mesma linha viram LaTeX).
    """
    return re.sub(r"([\\`*_{}\[\]()#!|<>~$:@])", r"\\\1", texto)


def resumo_sem_rotulo(rotulo: str, resumo: str) -> str:
    """Tira o rótulo do começo do resumo, já que ele aparece no título do veredito."""
    if resumo.lower().startswith(rotulo.lower()):
        return resumo[len(rotulo) :].lstrip(" .:").strip() or resumo
    return resumo
