from datetime import date
from decimal import Decimal

from interface.apresentacao import (
    ESTILO_NIVEL,
    em_markdown,
    escapar,
    linha_do_sinal,
    linhas_boleto,
    linhas_link,
    linhas_pix,
    resumo_sem_rotulo,
    titulo_do_boleto,
    titulo_do_link,
    titulo_do_pix,
)
from verificadores.modelos import ResultadoBoleto, ResultadoLink, ResultadoPix


def test_cada_nivel_tem_cor_de_alerta_do_streamlit():
    assert {cor for cor, _ in ESTILO_NIVEL.values()} == {"error", "warning", "success"}


def test_linha_do_sinal_mostra_gravidade_e_origem():
    assert linha_do_sinal("alta", "verificador", "O Pix vai para outra pessoa") == (
        "🔴 O Pix vai para outra pessoa :blue-badge[prova]"
    )
    assert linha_do_sinal("media", "ia", "Tom de ameaça").endswith(":gray-badge[análise da IA]")


def test_texto_da_mensagem_nao_vira_formatacao():
    assert escapar("Pague R$ 10 e R$ 20") == "Pague R\\$ 10 e R\\$ 20"
    assert escapar("[clique](http://x.top)") == "\\[clique\\]\\(http\\://x.top\\)"
    assert escapar("**urgente**") == "\\*\\*urgente\\*\\*"


def test_linhas_viram_rotulo_e_valor():
    assert em_markdown([("Quem recebe", "JOAO"), ("Chave (E-mail)", "a@b.com")]) == (
        "**Quem recebe:** JOAO  \n**Chave (E-mail):** a\\@b.com"
    )


def test_pix_de_pessoa_fisica():
    pix = ResultadoPix(
        valido=True, crc_ok=True, chave="12345678909", tipo_chave="cpf", nome_recebedor="RODRIGO A FERREIRA",
        cidade="MANAUS", valor=Decimal("247.30"), tipo_recebedor="pessoa_fisica",
    )
    assert dict(linhas_pix(pix)) == {
        "Quem recebe": "RODRIGO A FERREIRA",
        "Tipo": "Pessoa física",
        "Cidade": "Manaus",
        "Valor": "R$ 247,30",
        "Chave (CPF)": "12345678909",
        "Conferência do código": "✅ Confere",
    }
    assert titulo_do_pix(pix, 1) == "Pix 1: RODRIGO A FERREIRA"


def test_pix_dinamico_sem_valor_e_invalido():
    pix = ResultadoPix(valido=False, dinamico=True, url_cobranca="pix.banco.com/qr/abc")
    linhas = dict(linhas_pix(pix))
    assert linhas["Valor"] == "Em aberto"
    assert linhas["Cobrança dinâmica"] == "pix.banco.com/qr/abc"
    assert linhas["Conferência do código"] == "❌ Não confere"
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
        "Dígitos verificadores": "✅ Confere",
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
        marca_imitada="Correios", encurtador=False, safe_browsing="perigoso",
    )
    assert dict(linhas_link(link)) == {
        "Endereço do site": "correios-rastreio.top",
        "Imita": "Correios",
        "Cadeado (HTTPS)": "Não",
        "Lista de sites perigosos do Google": "Site marcado como perigoso",
    }
    assert titulo_do_link(link, 1) == "Link 1: correios-rastreio.top"


def test_link_encurtado():
    link = ResultadoLink(url="https://bit.ly/x", host="bit.ly", dominio="bit.ly", https=True, encurtador=True)
    linhas = dict(linhas_link(link))
    assert linhas["Encurtador"] == "Sim: esconde o destino real"
    assert linhas["Cadeado (HTTPS)"] == "Sim"


def test_resumo_sem_o_rotulo_repetido():
    assert resumo_sem_rotulo("Provável golpe", "Provável golpe. O Pix vai para outra pessoa.") == (
        "O Pix vai para outra pessoa."
    )
    assert resumo_sem_rotulo("Provável golpe", "É golpe: o Pix vai para outra pessoa.") == (
        "É golpe: o Pix vai para outra pessoa."
    )
    assert resumo_sem_rotulo("Provável golpe", "Provável golpe.") == "Provável golpe."
