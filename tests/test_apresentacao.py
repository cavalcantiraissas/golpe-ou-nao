import re
from datetime import date
from decimal import Decimal

from agente.modelos import Sinal, Veredito
from interface.apresentacao import (
    ESTILO,
    html_avisos,
    html_cartao,
    html_cartoes,
    html_passos,
    html_sinais,
    html_veredito,
    linhas_boleto,
    linhas_link,
    linhas_pix,
    resumo_sem_rotulo,
    titulo_do_boleto,
    titulo_do_link,
    titulo_do_pix,
)
from verificadores.modelos import ResultadoBoleto, ResultadoLink, ResultadoPix

# Pictogramas e símbolos fora do básico: a tela não usa emoji.
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")

PIX = ResultadoPix(
    valido=True, crc_ok=True, chave="12345678909", tipo_chave="cpf", nome_recebedor="RODRIGO A FERREIRA",
    cidade="MANAUS", valor=Decimal("247.30"), tipo_recebedor="pessoa_fisica",
)


def veredito(**extra) -> Veredito:
    base = dict(
        nivel="provavel_golpe",
        resumo="Provável golpe. O Pix vai para outra pessoa.",
        sinais=[
            Sinal(descricao="O Pix vai para outra pessoa.", gravidade="alta", fonte="verificador"),
            Sinal(descricao="Cria pressa.", gravidade="media", fonte="regra"),
        ],
        o_que_fazer=["Não pague."],
        pix=[PIX],
    )
    return Veredito(**{**base, **extra})


# --- Linhas dos cartões ----------------------------------------------------


def test_pix_de_pessoa_fisica():
    assert dict(linhas_pix(PIX)) == {
        "Quem recebe": "RODRIGO A FERREIRA",
        "Tipo": "Pessoa física",
        "Cidade": "Manaus",
        "Valor": "R$ 247,30",
        "Chave (CPF)": "12345678909",
        "Conferência do código": "Confere",
    }
    assert titulo_do_pix(PIX, 1) == "Pix 1: RODRIGO A FERREIRA"


def test_pix_dinamico_sem_valor_e_invalido():
    pix = ResultadoPix(valido=False, dinamico=True, url_cobranca="pix.banco.com/qr/abc")
    linhas = dict(linhas_pix(pix))
    assert linhas["Valor"] == "Em aberto"
    assert linhas["Cobrança dinâmica"] == "pix.banco.com/qr/abc"
    assert linhas["Conferência do código"] == "Não confere"
    assert "Cidade" not in linhas
    assert titulo_do_pix(pix, 2) == "Pix 2"


def test_boleto_bancario():
    boleto = ResultadoBoleto(
        valido=True, tipo="bancario", codigo_banco="237", nome_banco="Bradesco",
        valor=Decimal("589.40"), vencimento=date(2027, 2, 12),
    )
    assert dict(linhas_boleto(boleto)) == {
        "Tipo": "Boleto bancário",
        "Banco": "Bradesco (237)",
        "Valor": "R$ 589,40",
        "Vencimento": "12/02/2027",
        "Dígitos verificadores": "Confere",
    }
    assert titulo_do_boleto(boleto, 1) == "Boleto 1: Bradesco"


def test_conta_de_consumo():
    boleto = ResultadoBoleto(valido=True, tipo="arrecadacao", segmento="Energia elétrica e gás")
    linhas = dict(linhas_boleto(boleto))
    assert linhas["Tipo"] == "Conta de consumo ou tributo"
    assert linhas["Segmento"] == "Energia elétrica e gás"
    assert linhas["Valor"] == "Em aberto"


def test_boleto_ilegivel():
    assert titulo_do_boleto(ResultadoBoleto(valido=False), 3) == "Boleto 3: não identificado"


def test_link_que_imita_marca():
    link = ResultadoLink(
        url="http://correios-rastreio.top/taxa", host="correios-rastreio.top", dominio="correios-rastreio.top",
        marca_imitada="Correios", safe_browsing="perigoso",
    )
    assert dict(linhas_link(link)) == {
        "Endereço do site": "correios-rastreio.top",
        "Imita": "Correios",
        "Cadeado (HTTPS)": "Não",
        "Lista de sites perigosos do Google": "Marcado como perigoso",
    }
    assert titulo_do_link(link, 1) == "Link 1: correios-rastreio.top"


def test_link_encurtado():
    link = ResultadoLink(url="https://bit.ly/x", host="bit.ly", dominio="bit.ly", https=True, encurtador=True)
    linhas = dict(linhas_link(link))
    assert linhas["Encurtador"] == "Sim, esconde o destino real"
    assert linhas["Cadeado (HTTPS)"] == "Sim"


def test_resumo_sem_o_rotulo_repetido():
    assert resumo_sem_rotulo("Provável golpe", "Provável golpe. O Pix vai para outra pessoa.") == (
        "O Pix vai para outra pessoa."
    )
    assert resumo_sem_rotulo("Provável golpe", "É golpe: o Pix vai para outra pessoa.") == (
        "É golpe: o Pix vai para outra pessoa."
    )
    assert resumo_sem_rotulo("Provável golpe", "Provável golpe.") == "Provável golpe."


# --- HTML ------------------------------------------------------------------


def test_veredito_usa_a_cor_do_nivel_e_nao_repete_o_rotulo():
    html = html_veredito(veredito(marca_alegada="Enel"))
    assert 'class="gn-veredito gn-provavel_golpe"' in html
    assert '<p class="gn-nivel">Provável golpe</p>' in html
    assert '<p class="gn-resumo">O Pix vai para outra pessoa.</p>' in html
    assert "Diz ser: Enel" in html


def test_sinais_mostram_gravidade_origem_e_legenda_so_das_origens_presentes():
    html = html_sinais(veredito().sinais)
    assert '<li class="gn-sinal gn-alta"><span class="gn-gravidade">Grave</span>' in html
    assert '<span class="gn-fonte gn-fonte-verificador">Prova</span>' in html
    assert '<span class="gn-fonte gn-fonte-regra">Padrão de golpe</span>' in html
    assert "<b>Prova</b>" in html and "<b>Padrão de golpe</b>" in html
    assert "Análise da IA" not in html


def test_cartao_marca_a_conferencia():
    assert '<span class="gn-ok">Confere</span>' in html_cartao("Pix 1", [("Conferência do código", "Confere")])
    assert '<span class="gn-falha">Não confere</span>' in html_cartao("Pix 1", [("Conferência", "Não confere")])


def test_cartoes_de_todos_os_codigos():
    link = ResultadoLink(url="http://x.top", host="x.top", dominio="x.top")
    html = html_cartoes(veredito(links=[link]))
    assert "Pix 1: RODRIGO A FERREIRA" in html
    assert "Link 1: x.top" in html
    assert "O link não foi aberto" in html


def test_texto_da_mensagem_e_da_ia_e_escapado():
    # Um golpista controla o nome no Pix, a descrição e o que a IA repete: nada disso pode virar HTML.
    ataque = '<a href="http://golpe.top">clique</a><img src=x onerror=alert(1)>'
    pix = PIX.model_copy(update={"nome_recebedor": ataque})
    v = veredito(
        resumo=ataque,
        marca_alegada=ataque,
        sinais=[Sinal(descricao=ataque, gravidade="alta", fonte="ia")],
        o_que_fazer=[ataque],
        avisos=[ataque],
        pix=[pix],
    )
    for html in (html_veredito(v), html_sinais(v.sinais), html_passos(v.o_que_fazer), html_cartoes(v),
                 html_avisos(v.avisos)):
        assert "<a " not in html and "<img" not in html
        assert "&lt;a href=" in html


def test_nada_na_tela_usa_emoji():
    v = veredito(avisos=["Análise feita sem IA."])
    for html in (ESTILO, html_veredito(v), html_sinais(v.sinais), html_passos(v.o_que_fazer), html_cartoes(v)):
        assert not EMOJI.search(html)
