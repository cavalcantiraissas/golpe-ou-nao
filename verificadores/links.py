"""Análise de links sem abri-los.

Abrir um link de golpe pode confirmar ao golpista que o número está ativo ou
baixar algo indesejado, então tudo aqui olha só para o endereço:

* domínio que imita uma marca conhecida (``nubank-seguranca.com``, ``itau.com.br.acesso.top``);
* erro de digitação proposital (``nubamk.com.br``) e letras trocadas por números (``1tau``);
* encurtador, que esconde o destino real;
* ausência de HTTPS, IP no lugar do nome, endereço internacionalizado (``xn--``);
* consulta à lista do Google Safe Browsing, quando há chave de API.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

import httpx

from verificadores.modelos import ResultadoLink

# Marca -> (termos que aparecem num domínio falso, domínios oficiais)
MARCAS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "Banco do Brasil": (("bancodobrasil", "bbseguranca"), ("bb.com.br",)),
    "Bradesco": (("bradesco",), ("bradesco.com.br",)),
    "Caixa": (("caixa",), ("caixa.gov.br",)),
    "Itaú": (("itau",), ("itau.com.br",)),
    "Santander": (("santander",), ("santander.com.br",)),
    "Nubank": (("nubank",), ("nubank.com.br", "nu.com.br")),
    "Banco Inter": (("bancointer",), ("bancointer.com.br", "inter.co")),
    "PicPay": (("picpay",), ("picpay.com",)),
    "Mercado Pago": (("mercadopago",), ("mercadopago.com.br", "mercadopago.com")),
    "Mercado Livre": (("mercadolivre",), ("mercadolivre.com.br", "mercadolivre.com")),
    "Correios": (("correios",), ("correios.com.br",)),
    "Receita Federal": (("receitafederal",), ("gov.br",)),
    "Gov.br": (("govbr",), ("gov.br",)),
    "Detran": (("detran",), ("gov.br",)),
    "Serasa": (("serasa",), ("serasa.com.br",)),
    "Enel": (("enel",), ("enel.com.br", "enel.com")),
    "Cemig": (("cemig",), ("cemig.com.br",)),
    "Sabesp": (("sabesp",), ("sabesp.com.br",)),
    "Magazine Luiza": (("magazineluiza", "magalu"), ("magazineluiza.com.br", "magalu.com")),
    "Shopee": (("shopee",), ("shopee.com.br", "shopee.com")),
    "Amazon": (("amazon",), ("amazon.com.br", "amazon.com")),
    "Netflix": (("netflix",), ("netflix.com",)),
    "WhatsApp": (("whatsapp",), ("whatsapp.com", "wa.me")),
}

ENCURTADORES = {
    "bit.ly", "bit.do", "cutt.ly", "encurtador.com.br", "goo.gl", "is.gd", "ow.ly",
    "rb.gy", "s.id", "shorturl.at", "t.co", "t.ly", "tiny.cc", "tinyurl.com", "abre.ai",
}

TLDS_SUSPEITOS = {
    "xyz", "top", "online", "site", "club", "icu", "buzz", "shop", "live", "click",
    "cfd", "sbs", "rest", "monster", "quest", "lat",
}

# Sufixos de dois níveis mais comuns; o domínio registrável fica um nível acima.
SUFIXOS_DUPLOS = {
    "com.br", "net.br", "org.br", "gov.br", "edu.br", "app.br", "art.br", "blog.br",
    "nom.br", "ind.br", "eco.br", "com.ar", "com.mx", "co.uk", "com.pt",
}

_TROCAS = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})
_IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_URL_NO_TEXTO = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+"  # com esquema ou www
    r"|\b(?:[a-z0-9-]+\.)+(?:[a-z]{2,})(?:/[^\s<>\"']*)?",  # domínio solto, ex.: bit.ly/abc
    re.I,
)
_TLDS_ACEITOS_SOLTOS = {
    "br", "com", "net", "org", "io", "co", "me", "ly", "gl", "gd", "at", "cc", "id", "ai",
    "app", "info", "biz",
} | TLDS_SUSPEITOS

SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
TIPOS_AMEACA = ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"]
NOMES_AMEACA = {
    "MALWARE": "programa malicioso",
    "SOCIAL_ENGINEERING": "golpe / página falsa (phishing)",
    "UNWANTED_SOFTWARE": "programa indesejado",
    "POTENTIALLY_HARMFUL_APPLICATION": "aplicativo potencialmente perigoso",
}


def extrair_links(texto: str) -> list[str]:
    """Encontra links num texto, inclusive os escritos sem http:// (``bit.ly/xyz``)."""
    links = []
    for achado in _URL_NO_TEXTO.finditer(texto):
        url = achado.group().rstrip(".,;:!?)]}")
        if not url.lower().startswith(("http://", "https://", "www.")):
            host = url.split("/")[0].lower()
            if "@" in texto[max(0, achado.start() - 1) : achado.start()]:
                continue  # parte de um e-mail
            if host.rsplit(".", 1)[-1] not in _TLDS_ACEITOS_SOLTOS:
                continue
        if url not in links:
            links.append(url)
    return links


def dominio_registravel(host: str) -> str:
    partes = host.split(".")
    if len(partes) >= 3 and ".".join(partes[-2:]) in SUFIXOS_DUPLOS:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:])


def _eh_oficial(host: str, oficiais: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in oficiais if "." in d)


def _distancia(a: str, b: str) -> int:
    """Distância de edição (Levenshtein)."""
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        atual = [i]
        for j, cb in enumerate(b, start=1):
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        anterior = atual
    return anterior[-1]


def detectar_marca_imitada(host: str) -> str | None:
    """Devolve a marca que o endereço tenta imitar, ou None se for oficial ou não imitar nenhuma.

    Termos longos valem em qualquer lugar do endereço (``seguranca-nubank``);
    termos curtos, como "itau" e "enel", só no começo de um pedaço
    (``itau-acesso``, ``enelcontas``), para não pegar palavras comuns.
    """
    host = host.lower()
    normalizado = host.translate(_TROCAS).replace("-", "").replace(".", "")
    pedacos = [p.translate(_TROCAS) for p in re.split(r"[.-]", host) if p]

    for marca, (termos, oficiais) in MARCAS.items():
        if _eh_oficial(host, oficiais):
            return None
    for marca, (termos, _) in MARCAS.items():
        for termo in termos:
            if len(termo) >= 7 and termo in normalizado:
                return marca
            if any(p.startswith(termo) for p in pedacos):
                return marca
            # Erro de digitação proposital: "nubamk", "bradescco".
            if len(termo) >= 6 and any(
                abs(len(p) - len(termo)) <= 1 and _distancia(p, termo) == 1 for p in pedacos
            ):
                return marca
    return None


def consultar_safe_browsing(
    url: str, chave: str, cliente: httpx.Client | None = None
) -> tuple[str, list[str]]:
    """Consulta a lista de sites perigosos do Google. Devolve (status, ameaças)."""
    corpo = {
        "client": {"clientId": "golpe-ou-nao", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": TIPOS_AMEACA,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    proprio = cliente is None
    cliente = cliente or httpx.Client(timeout=5)
    try:
        resposta = cliente.post(SAFE_BROWSING_URL, params={"key": chave}, json=corpo)
        resposta.raise_for_status()
        achados = resposta.json().get("matches", [])
    except (httpx.HTTPError, ValueError):
        return "erro", []
    finally:
        if proprio:
            cliente.close()
    if not achados:
        return "limpo", []
    return "perigoso", sorted({a.get("threatType", "DESCONHECIDA") for a in achados})


def analisar_link(
    url: str,
    chave_safe_browsing: str | None = None,
    cliente: httpx.Client | None = None,
) -> ResultadoLink:
    """Levanta os sinais de risco de um link sem abri-lo.

    A chave do Safe Browsing vem do argumento ou da variável de ambiente
    ``GOOGLE_SAFE_BROWSING_KEY``; sem ela, a consulta é pulada.
    """
    original = url.strip()
    com_esquema = original if re.match(r"^[a-z][a-z0-9+.-]*://", original, re.I) else "http://" + original
    partes = urlsplit(com_esquema)
    host = (partes.hostname or "").lower().rstrip(".")
    sinais: list[str] = []

    if not host:
        return ResultadoLink(url=original, sinais=["Não foi possível ler o endereço do link"])

    https = partes.scheme.lower() == "https"
    dominio = host if _IP.match(host) else dominio_registravel(host)
    encurtador = host.removeprefix("www.") in ENCURTADORES
    marca = None if encurtador else detectar_marca_imitada(host)

    if marca:
        sinais.append(f"O endereço imita a marca {marca}, mas não é um site oficial dela ({dominio})")
    if encurtador:
        sinais.append(f"Link encurtado ({host}): esconde para onde você seria levado")
    if not https:
        sinais.append("O link não usa HTTPS (conexão sem cadeado)")
    if _IP.match(host):
        sinais.append("O link usa um número (IP) no lugar do nome do site")
    if "xn--" in host:
        sinais.append("O endereço usa caracteres especiais que imitam letras comuns")
    if host.rsplit(".", 1)[-1] in TLDS_SUSPEITOS:
        sinais.append(f"Terminação .{host.rsplit('.', 1)[-1]}, muito usada em sites descartáveis")
    if host.count(".") >= 4:
        sinais.append("Endereço com muitos pedaços, um truque para esconder o domínio real")
    if partes.username or "@" in partes.netloc:
        sinais.append("O link tem um '@', que faz o navegador ir para outro endereço")

    chave = chave_safe_browsing or os.environ.get("GOOGLE_SAFE_BROWSING_KEY")
    status, ameacas = "nao_consultado", []
    if chave:
        status, ameacas = consultar_safe_browsing(com_esquema, chave, cliente)
        if status == "perigoso":
            nomes = ", ".join(NOMES_AMEACA.get(a, a) for a in ameacas)
            sinais.insert(0, f"O Google classifica este link como perigoso: {nomes}")

    return ResultadoLink(
        url=original,
        host=host,
        dominio=dominio,
        https=https,
        encurtador=encurtador,
        marca_imitada=marca,
        safe_browsing=status,
        ameacas=ameacas,
        sinais=sinais,
    )
