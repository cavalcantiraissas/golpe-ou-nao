"""Cruzamento determinístico: o que a mensagem diz x o que os códigos revelam.

Esta é a parte do veredito que não depende da IA. Ela recebe os resultados
dos verificadores e o texto da mensagem e produz sinais com gravidade:

* **alta**: prova forte de golpe (ex.: diz ser a Enel, mas o Pix vai para
  uma pessoa física). Basta uma para o veredito ser "provável golpe".
* **media**: motivo para desconfiar (link encurtado, pressa, valor diferente).
* **baixa**: detalhe que sozinho não preocupa (link sem HTTPS).
* **info**: o que o código revela, para a pessoa conferir (recebedor, banco).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import urlsplit

import httpx

from agente.modelos import Nivel, Sinal
from verificadores import (
    analisar_link,
    decodificar_pix,
    extrair_linhas_digitaveis,
    extrair_links,
    extrair_pix,
    validar_boleto,
)
from verificadores.links import MARCAS as MARCAS_LINKS
from verificadores.links import TLDS_SUSPEITOS
from verificadores.modelos import ResultadoBoleto, ResultadoLink, ResultadoPix

Origem = Literal["texto", "imagem"]

# Marca -> (expressão no texto já sem acentos e em minúsculas, categoria)
MARCAS_NO_TEXTO: dict[str, tuple[str, str]] = {
    "Enel": (r"\benel\b", "energia"),
    "Cemig": (r"\bcemig\b", "energia"),
    "CPFL": (r"\bcpfl\b", "energia"),
    "Neoenergia": (r"\b(neoenergia|coelba|celpe|cosern)\b", "energia"),
    "Equatorial": (r"\bequatorial energia\b", "energia"),
    "Copel": (r"\bcopel\b", "energia"),
    "Sabesp": (r"\bsabesp\b", "agua"),
    "Copasa": (r"\bcopasa\b", "agua"),
    "Embasa": (r"\bembasa\b", "agua"),
    "Sanepar": (r"\bsanepar\b", "agua"),
    "Cedae": (r"\bcedae\b", "agua"),
    "Itaú": (r"\bitau\b", "banco"),
    "Bradesco": (r"\bbradesco\b", "banco"),
    "Santander": (r"\bsantander\b", "banco"),
    "Nubank": (r"\bnubank\b", "banco"),
    "Banco do Brasil": (r"\bbanco do brasil\b", "banco"),
    "Caixa": (r"\bcaixa (economica|tem)\b|\bapp da caixa\b", "banco"),
    "Banco Inter": (r"\bbanco inter\b", "banco"),
    "C6 Bank": (r"\bc6 ?bank\b", "banco"),
    "PicPay": (r"\bpicpay\b", "banco"),
    "Mercado Pago": (r"\bmercado ?pago\b", "banco"),
    "Correios": (r"\bcorreios\b", "entrega"),
    "Receita Federal": (r"\breceita federal\b", "governo"),
    "Detran": (r"\bdetran\b", "governo"),
    "INSS": (r"\binss\b", "governo"),
    "Gov.br": (r"\bgov\.br\b", "governo"),
    "Serasa": (r"\bserasa\b", "outros"),
    "Mercado Livre": (r"\bmercado ?livre\b", "varejo"),
    "Shopee": (r"\bshopee\b", "varejo"),
    "Amazon": (r"\bamazon\b", "varejo"),
    "Magazine Luiza": (r"\b(magazine luiza|magalu)\b", "varejo"),
}

CODIGO_DO_BANCO = {
    "Itaú": "341",
    "Bradesco": "237",
    "Santander": "033",
    "Banco do Brasil": "001",
    "Caixa": "104",
    "Nubank": "260",
    "Banco Inter": "077",
    "C6 Bank": "336",
    "PicPay": "380",
    "Mercado Pago": "323",
}

SEGMENTO_DA_CATEGORIA = {"energia": "Energia elétrica e gás", "agua": "Saneamento (água e esgoto)"}

# Táticas de manipulação: (expressão, gravidade, explicação)
_PEDIDO_DE_DINHEIRO = r"\b(pix|transfer\w*|deposit\w*|pag(a|ar|ue)|boleto|emprest\w*|dinheiro)\b"
TATICAS: list[tuple[str, str, str]] = [
    (
        r"\b(troquei|mudei) (de |o |meu )?(numero|celular|telefone|whats\w*)\b|\bnumero novo\b|\bnovo numero\b"
        r"|\bperdi (o |meu )?celular\b",
        "media",
        "Diz que trocou de número: confirme ligando para o número antigo da pessoa.",
    ),
    (
        r"\burgente\b|\bimediatamente\b|\bainda hoje\b|\bultimo dia\b|\bem ate \d+ ?(h|horas)\b"
        r"|\bnas proximas \d+ ?(h|horas)\b|\bevit(e|ar) (o |a )?(corte|bloqueio|cancelamento|suspensao)\b"
        r"|\bsera (bloquead|cancelad|suspens|cortad)\w*",
        "media",
        "Cria pressa ou ameaça (corte, bloqueio, prazo de horas) para você não ter tempo de pensar.",
    ),
    (
        r"\bnao (conta|fala|comenta|diga)\w* (nada )?(pra|pro|para|com|a|ao) (ninguem|o pai|a mae|pai|mae|meu pai"
        r"|minha mae|seu pai|sua mae|ele|ela)\b|\bsegredo\b|\bsigilo\b|\bentre nos\b",
        "media",
        "Pede segredo: golpistas querem impedir que você pergunte a alguém.",
    ),
    (
        r"\b(passa|passe|envia|envie|manda|mande|informe|repasse|me fala)\b.{0,25}\bcodigo\b"
        r"|\bcodigo\b.{0,40}\bme (passa|passe|envia|envie|manda|mande|fala|repassa)\b",
        "alta",
        "Pede um código recebido por SMS ou WhatsApp: com ele, golpistas tomam a sua conta.",
    ),
    (
        r"\b(confirme|atualize|informe|digite|valide)\b.{0,30}\b(senha|dados bancarios|dados do cartao|token)\b",
        "media",
        "Pede senha, token ou dados do cartão: bancos e empresas nunca pedem isso por mensagem.",
    ),
    (
        r"\btaxa (de|para) (liberacao|desembaraco|entrega|alfandega)\w*|\bpague a taxa\b"
        r"|\bencomenda (foi )?(taxada|retida)\b",
        "media",
        "Cobra taxa para liberar uma entrega: é o golpe mais comum em nome dos Correios.",
    ),
    (
        r"\bvoce (foi sorteado|ganhou)\b|\bresgat(e|ar) (seu|o|sua) (premio|valor|saldo|pontos)\b",
        "media",
        "Promete prêmio ou dinheiro a resgatar, o que costuma ser isca.",
    ),
    (
        r"\bcentral de seguranca\b|\b(compra|transacao) (suspeita|nao reconhecida)\b",
        "media",
        "Fala em compra suspeita ou central de segurança, típico da falsa ligação do banco.",
    ),
]


@dataclass
class Achados:
    """Tudo o que os verificadores encontraram, com a origem de cada código."""

    pix: list[tuple[ResultadoPix, Origem]] = field(default_factory=list)
    boletos: list[tuple[ResultadoBoleto, Origem]] = field(default_factory=list)
    links: list[ResultadoLink] = field(default_factory=list)


# --- Leitura do texto ------------------------------------------------------


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower())


def marcas_mencionadas(texto: str) -> list[str]:
    norm = normalizar(texto)
    return [marca for marca, (expr, _) in MARCAS_NO_TEXTO.items() if re.search(expr, norm)]


def valores_mencionados(texto: str) -> list[Decimal]:
    """Valores em reais escritos na mensagem: R$ 1.234,56, R$50, R$ 89,90."""
    valores = []
    for achado in re.finditer(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)", texto):
        try:
            valores.append(Decimal(achado.group(1).replace(".", "").replace(",", ".")))
        except InvalidOperation:
            continue
    return valores


def reais(valor: Decimal) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _cita_marca(nome: str | None, marca: str) -> bool:
    if not nome or marca not in MARCAS_NO_TEXTO:
        return False
    return re.search(MARCAS_NO_TEXTO[marca][0], normalizar(nome)) is not None


def _sinal(descricao: str, gravidade: str, fonte: str = "verificador") -> Sinal:
    return Sinal(descricao=descricao, gravidade=gravidade, fonte=fonte)


def _sinal_de_valor(tipo: str, valor: Decimal | None, valores: list[Decimal]) -> list[Sinal]:
    if valor is None or not valores or valor in valores:
        return []
    escritos = " ou ".join(reais(v) for v in dict.fromkeys(valores))
    return [_sinal(f"O valor no {tipo} ({reais(valor)}) é diferente do escrito na mensagem ({escritos}).", "media")]


# --- Sinais por tipo de código ---------------------------------------------


def sinais_de_pix(pix: ResultadoPix, origem: Origem, marcas: list[str], valores: list[Decimal]) -> list[Sinal]:
    sinais = []
    if not pix.valido:
        if origem == "imagem":
            sinais.append(_sinal(
                "Não deu para ler o código Pix do print com certeza. Cole o código como texto para uma conferência segura.",
                "media",
            ))
        else:
            sinais.append(_sinal(
                "O código Pix não passa na conferência: foi alterado ou está incompleto. "
                "Códigos gerados por bancos sempre passam.",
                "alta",
            ))
    if not pix.nome_recebedor:
        return sinais

    nome = pix.nome_recebedor
    local = f", em {pix.cidade.title()}" if pix.cidade else ""
    if marcas and not any(_cita_marca(nome, m) for m in marcas):
        marca = marcas[0]
        if pix.tipo_recebedor == "pessoa_fisica":
            sinais.append(_sinal(
                f"A mensagem fala em nome de {marca}, mas o Pix vai para uma pessoa física: {nome}{local}.",
                "alta",
            ))
        else:
            # Empresa com outro nome pode ser um intermediador de pagamento: motivo de dúvida, não prova.
            # Nome sem cara de empresa recebendo por uma marca é prova.
            sinais.append(_sinal(
                f"A mensagem fala em nome de {marca}, mas o Pix vai para {nome}{local}.",
                "media" if pix.tipo_recebedor == "pessoa_juridica" else "alta",
            ))
    else:
        tipo = {"pessoa_fisica": " (pessoa física)", "pessoa_juridica": " (empresa)"}.get(pix.tipo_recebedor, "")
        valor = f", valor {reais(pix.valor)}" if pix.valor else ""
        sinais.append(_sinal(f"O Pix vai para {nome}{tipo}{local}{valor}.", "info"))

    sinais += _sinal_de_valor("código Pix", pix.valor, valores)
    return sinais


def sinais_de_boleto(
    boleto: ResultadoBoleto, origem: Origem, marcas: list[str], valores: list[Decimal]
) -> list[Sinal]:
    if not boleto.valido:
        if origem == "imagem":
            return [_sinal(
                "Não deu para ler a linha do boleto do print com certeza. Digite ou cole os números para conferir.",
                "media",
            )]
        return [_sinal(
            "Os números do boleto não conferem: ele foi alterado ou está incompleto. Não pague por essa linha.",
            "media",
        )]

    sinais = []
    valor = f", valor {reais(boleto.valor)}" if boleto.valor else ""
    vencimento = f", vencimento {boleto.vencimento:%d/%m/%Y}" if boleto.vencimento else ""
    categorias = {m: MARCAS_NO_TEXTO[m][1] for m in marcas if m in MARCAS_NO_TEXTO}

    if boleto.tipo == "bancario":
        banco = boleto.nome_banco or f"código {boleto.codigo_banco}"
        sinais.append(_sinal(f"O boleto é pago a um cliente do banco {banco}{valor}{vencimento}.", "info"))
        for marca, categoria in categorias.items():
            if categoria in SEGMENTO_DA_CATEGORIA:
                sinais.append(_sinal(
                    f"A mensagem é sobre uma conta de {marca}, mas o código é de um boleto bancário comum, "
                    "não de conta de consumo (que começa com 8). Confira o nome do beneficiário no app do banco.",
                    "media",
                ))
            elif marca in CODIGO_DO_BANCO and CODIGO_DO_BANCO[marca] != boleto.codigo_banco:
                sinais.append(_sinal(f"A mensagem fala em nome de {marca}, mas o boleto é do banco {banco}.", "media"))
    else:
        sinais.append(_sinal(f"Conta do segmento {boleto.segmento}{valor}.", "info"))
        for marca, categoria in categorias.items():
            esperado = SEGMENTO_DA_CATEGORIA.get(categoria)
            if esperado and esperado != boleto.segmento:
                sinais.append(_sinal(
                    f"A mensagem é sobre uma conta de {marca}, mas o código é do segmento {boleto.segmento}.",
                    "media",
                ))

    sinais += _sinal_de_valor("boleto", boleto.valor, valores)
    return sinais


def _link_oficial_de(host: str, marca: str) -> bool:
    _, oficiais = MARCAS_LINKS.get(marca, ((), ()))
    return any(host == d or host.endswith("." + d) for d in oficiais)


def sinais_de_link(link: ResultadoLink, marcas: list[str]) -> list[Sinal]:
    if not link.host:
        return [_sinal(f"Link ilegível: {link.url}", "baixa")]
    sinais = []
    host = link.host
    if link.safe_browsing == "perigoso":
        sinais.append(_sinal(link.sinais[0], "alta"))
    if link.marca_imitada:
        sinais.append(_sinal(
            f"O link {host} imita {link.marca_imitada}, mas não é um site oficial.", "alta"
        ))
    if link.encurtador:
        sinais.append(_sinal(f"Link encurtado ({host}): esconde para onde você seria levado.", "media"))

    url = link.url if "://" in link.url else "http://" + link.url
    if "@" in urlsplit(url).netloc:
        sinais.append(_sinal("O link tem um '@', que faz o navegador ir para outro endereço.", "media"))
    if "xn--" in host:
        sinais.append(_sinal("O endereço do link usa caracteres que imitam letras comuns.", "media"))
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
        sinais.append(_sinal("O link usa um número (IP) no lugar do nome do site.", "media"))
    if host.rsplit(".", 1)[-1] in TLDS_SUSPEITOS:
        sinais.append(_sinal(f"O site termina em .{host.rsplit('.', 1)[-1]}, comum em sites descartáveis.", "baixa"))
    if link.url.lower().startswith("http://"):  # sem esquema escrito não dá para saber
        sinais.append(_sinal(f"O link {host} não usa HTTPS (conexão sem cadeado).", "baixa"))

    if not link.marca_imitada and not link.encurtador:
        for marca in marcas:
            if marca in MARCAS_LINKS and not _link_oficial_de(host, marca):
                sinais.append(_sinal(
                    f"A mensagem fala em nome de {marca}, mas o link leva para outro site: {link.dominio}.",
                    "media",
                ))
                break
    return sinais


def sinais_de_texto(texto: str) -> list[Sinal]:
    norm = normalizar(texto)
    sinais = []
    for expr, gravidade, explicacao in TATICAS:
        if re.search(expr, norm):
            sinais.append(_sinal(explicacao, gravidade, fonte="regra"))
    troca = re.search(TATICAS[0][0], norm)
    if troca and re.search(_PEDIDO_DE_DINHEIRO, norm):
        # O sinal forte substitui o aviso simples de troca de número.
        sinais = [x for x in sinais if x.descricao != TATICAS[0][2]]
        sinais.append(_sinal(
            "Pede dinheiro logo depois de dizer que trocou de número: é o golpe mais comum do WhatsApp.",
            "alta",
            fonte="regra",
        ))
    return sinais


# --- Junta tudo ------------------------------------------------------------


def levantar_achados(
    texto: str, chave_safe_browsing: str | None = None, cliente_http: httpx.Client | None = None
) -> Achados:
    """Acha e confere todos os códigos escritos na mensagem."""
    pix_codigos = extrair_pix(texto)
    # Um Pix contém URLs (QR dinâmico) e muitos dígitos; tira os códigos antes de procurar links e boletos.
    restante = texto
    for codigo in pix_codigos:
        restante = restante.replace(codigo, " ")
    return Achados(
        pix=[(decodificar_pix(c), "texto") for c in pix_codigos],
        boletos=[(validar_boleto(linha), "texto") for linha in extrair_linhas_digitaveis(restante)],
        links=[analisar_link(u, chave_safe_browsing, cliente_http) for u in extrair_links(restante)],
    )


def cruzar(texto: str, achados: Achados, marca_alegada: str | None = None) -> list[Sinal]:
    """Produz todos os sinais determinísticos da mensagem."""
    marcas = marcas_mencionadas(texto)
    if marca_alegada:
        conhecida = next((m for m in MARCAS_NO_TEXTO if normalizar(m) == normalizar(marca_alegada)), None)
        if conhecida and conhecida not in marcas:
            marcas.append(conhecida)
    valores = valores_mencionados(texto)

    sinais: list[Sinal] = []
    for pix, origem in achados.pix:
        sinais += sinais_de_pix(pix, origem, marcas, valores)
    for boleto, origem in achados.boletos:
        sinais += sinais_de_boleto(boleto, origem, marcas, valores)
    for link in achados.links:
        sinais += sinais_de_link(link, marcas)
    sinais += sinais_de_texto(texto)

    # Ordem: mais graves primeiro, sem repetir a mesma frase.
    ordem = {"alta": 0, "media": 1, "baixa": 2, "info": 3}
    unicos = {s.descricao: s for s in sinais}
    return sorted(unicos.values(), key=lambda s: ordem[s.gravidade])


def nivel_pelos_sinais(sinais: list[Sinal]) -> Nivel:
    """Uma prova alta ou três motivos médios: provável golpe. Algum motivo médio: atenção."""
    altas = sum(s.gravidade == "alta" for s in sinais)
    medias = sum(s.gravidade == "media" for s in sinais)
    if altas or medias >= 3:
        return "provavel_golpe"
    if medias:
        return "atencao"
    return "sem_sinais"
