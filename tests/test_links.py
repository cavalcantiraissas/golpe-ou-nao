import json

import httpx
import pytest

from verificadores.links import (
    analisar_link,
    detectar_marca_imitada,
    dominio_registravel,
    extrair_links,
)


@pytest.fixture(autouse=True)
def sem_chave_no_ambiente(monkeypatch):
    monkeypatch.delenv("GOOGLE_SAFE_BROWSING_KEY", raising=False)


def cliente_falso(resposta: dict | None = None, status: int = 200, pedidos: list | None = None):
    def responder(request: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(request)
        return httpx.Response(status, json=resposta or {})

    return httpx.Client(transport=httpx.MockTransport(responder))


# --- Marca imitada ---------------------------------------------------------


@pytest.mark.parametrize(
    "host, marca",
    [
        ("nubank-seguranca.com", "Nubank"),
        ("seguranca-nubank.online", "Nubank"),
        ("nubamk.com.br", "Nubank"),
        ("itau.com.br.acesso-cliente.top", "Itaú"),
        ("1tau-desbloqueio.com", "Itaú"),
        ("correios-rastreio.com", "Correios"),
        ("rastreamento.c0rreios.net", "Correios"),
        ("enelcontas.com", "Enel"),
        ("enel-fatura.site", "Enel"),
        ("caixatem-auxilio.com", "Caixa"),
        ("bradescco.com", "Bradesco"),
        ("receitafederal-cpf.com", "Receita Federal"),
        ("detran-multas.online", "Detran"),
        ("mercadolivre.promo-black.com", "Mercado Livre"),
    ],
)
def test_detecta_imitacao(host, marca):
    assert detectar_marca_imitada(host) == marca


@pytest.mark.parametrize(
    "host",
    [
        "nubank.com.br",
        "www.itau.com.br",
        "internetbanking.caixa.gov.br",
        "www.gov.br",
        "detran.sp.gov.br",
        "rastreamento.correios.com.br",
        "www.enel.com.br",
        "www.bb.com.br",
        "www.mercadolivre.com.br",
    ],
)
def test_sites_oficiais_nao_sao_marcados(host):
    assert detectar_marca_imitada(host) is None


@pytest.mark.parametrize(
    "host",
    ["receitas.tudogostoso.com.br", "penelope.com", "github.com", "g1.globo.com", "uol.com.br"],
)
def test_palavras_comuns_nao_geram_falso_alarme(host):
    assert detectar_marca_imitada(host) is None


# --- Domínio registrável ---------------------------------------------------


@pytest.mark.parametrize(
    "host, dominio",
    [
        ("www.itau.com.br", "itau.com.br"),
        ("itau.com.br.acesso.top", "acesso.top"),
        ("a.b.exemplo.com", "exemplo.com"),
        ("detran.sp.gov.br", "sp.gov.br"),
        ("bit.ly", "bit.ly"),
    ],
)
def test_dominio_registravel(host, dominio):
    assert dominio_registravel(host) == dominio


# --- Análise completa (sem Safe Browsing) ----------------------------------


def test_link_falso_de_banco_acumula_sinais():
    r = analisar_link("http://itau.com.br.atualizacao-cadastral.xyz/token")
    assert r.marca_imitada == "Itaú"
    assert r.dominio == "atualizacao-cadastral.xyz"
    assert not r.https
    assert r.safe_browsing == "nao_consultado"
    texto = " ".join(r.sinais)
    assert "Itaú" in texto
    assert "HTTPS" in texto
    assert ".xyz" in texto


def test_site_oficial_com_https_nao_tem_sinais():
    r = analisar_link("https://www.nubank.com.br/ajuda")
    assert r.marca_imitada is None
    assert r.https
    assert r.sinais == []


def test_encurtador():
    r = analisar_link("bit.ly/3xYzAbc")
    assert r.encurtador
    assert r.host == "bit.ly"
    assert any("encurtado" in s for s in r.sinais)


def test_link_sem_esquema_e_tratado_como_http():
    r = analisar_link("correios-entrega.com/rastreio")
    assert not r.https
    assert r.marca_imitada == "Correios"


def test_ip_no_lugar_do_nome():
    r = analisar_link("http://185.23.10.4/login")
    assert r.dominio == "185.23.10.4"
    assert any("IP" in s for s in r.sinais)


def test_endereco_internacionalizado():
    r = analisar_link("https://xn--nbank-3ya.com")
    assert any("caracteres especiais" in s for s in r.sinais)


def test_arroba_no_link():
    r = analisar_link("https://www.bb.com.br@golpe.top/login")
    assert r.host == "golpe.top"
    assert any("@" in s for s in r.sinais)


def test_muitos_subdominios():
    r = analisar_link("https://login.conta.cliente.seguro.exemplo.com")
    assert any("muitos pedaços" in s for s in r.sinais)


def test_link_ilegivel():
    r = analisar_link("http://")
    assert r.host is None
    assert r.sinais


# --- Google Safe Browsing (simulado) ---------------------------------------


def test_safe_browsing_perigoso():
    pedidos = []
    resposta = {"matches": [{"threatType": "SOCIAL_ENGINEERING"}, {"threatType": "MALWARE"}]}
    r = analisar_link(
        "https://golpe.example/pagar",
        chave_safe_browsing="CHAVE",
        cliente=cliente_falso(resposta, pedidos=pedidos),
    )
    assert r.safe_browsing == "perigoso"
    assert r.ameacas == ["MALWARE", "SOCIAL_ENGINEERING"]
    assert "phishing" in r.sinais[0]

    pedido = pedidos[0]
    assert pedido.url.params["key"] == "CHAVE"
    corpo = json.loads(pedido.content)
    assert corpo["threatInfo"]["threatEntries"] == [{"url": "https://golpe.example/pagar"}]


def test_safe_browsing_limpo():
    r = analisar_link("https://www.nubank.com.br", chave_safe_browsing="CHAVE", cliente=cliente_falso({}))
    assert r.safe_browsing == "limpo"
    assert r.ameacas == []


def test_safe_browsing_erro_nao_derruba_a_analise():
    r = analisar_link(
        "http://enel-fatura.site", chave_safe_browsing="CHAVE", cliente=cliente_falso(status=500)
    )
    assert r.safe_browsing == "erro"
    assert r.marca_imitada == "Enel"


def test_chave_lida_do_ambiente(monkeypatch):
    monkeypatch.setenv("GOOGLE_SAFE_BROWSING_KEY", "DO_AMBIENTE")
    pedidos = []
    analisar_link("https://exemplo.com", cliente=cliente_falso({}, pedidos=pedidos))
    assert pedidos[0].url.params["key"] == "DO_AMBIENTE"


def test_link_sem_esquema_e_enviado_com_http():
    pedidos = []
    analisar_link("bit.ly/abc", chave_safe_browsing="C", cliente=cliente_falso({}, pedidos=pedidos))
    assert json.loads(pedidos[0].content)["threatInfo"]["threatEntries"] == [{"url": "http://bit.ly/abc"}]


# --- Extração de dentro de uma mensagem ------------------------------------


def test_extrai_links_de_uma_mensagem():
    mensagem = (
        "CORREIOS: sua encomenda foi taxada. Regularize em https://correios-taxa.com/pagar. "
        "Ou acesse bit.ly/3xYz em até 24h. Dúvidas: www.correios.com.br"
    )
    assert extrair_links(mensagem) == [
        "https://correios-taxa.com/pagar",
        "bit.ly/3xYz",
        "www.correios.com.br",
    ]


def test_ignora_email_e_numeros():
    mensagem = "Escreva para atendimento@banco.com.br ou ligue 4004.0001. Valor R$ 1.500,00"
    assert extrair_links(mensagem) == []


def test_sem_repeticao():
    assert extrair_links("veja bit.ly/a e de novo bit.ly/a") == ["bit.ly/a"]
