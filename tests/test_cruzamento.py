from decimal import Decimal

import pytest

from agente.cruzamento import (
    Achados,
    cruzar,
    levantar_achados,
    marcas_mencionadas,
    nivel_pelos_sinais,
    reais,
    sinais_de_texto,
    valores_mencionados,
)
from agente.modelos import Sinal
from tests.test_boleto import EXEMPLO_BB, montar_arrecadacao, montar_bancario
from tests.test_pix import montar_pix
from verificadores import analisar_link, decodificar_pix, validar_boleto


@pytest.fixture(autouse=True)
def sem_safe_browsing(monkeypatch):
    monkeypatch.delenv("GOOGLE_SAFE_BROWSING_KEY", raising=False)


def graves(sinais: list[Sinal], gravidade: str) -> list[str]:
    return [s.descricao for s in sinais if s.gravidade == gravidade]


# --- Leitura do texto ------------------------------------------------------


def test_marcas_mencionadas_sem_acento_e_maiusculas():
    assert marcas_mencionadas("ITAÚ: sua conta foi bloqueada") == ["Itaú"]
    assert marcas_mencionadas("Conta Enel e boleto Sabesp") == ["Enel", "Sabesp"]


def test_palavras_comuns_nao_viram_marca():
    assert marcas_mencionadas("Deixei a caixa de som com o inter do prédio") == []


def test_caixa_so_quando_e_o_banco():
    assert marcas_mencionadas("Seu benefício no Caixa Tem foi liberado") == ["Caixa"]


@pytest.mark.parametrize(
    "texto, valores",
    [
        ("Pague R$ 189,90 hoje", [Decimal("189.90")]),
        ("Valor: R$1.250,00", [Decimal("1250.00")]),
        ("me manda R$ 50 e depois R$ 30,50", [Decimal("50"), Decimal("30.50")]),
        ("sem valor nenhum", []),
    ],
)
def test_valores_mencionados(texto, valores):
    assert valores_mencionados(texto) == valores


def test_reais_no_formato_brasileiro():
    assert reais(Decimal("1250.5")) == "R$ 1.250,50"


# --- Pix -------------------------------------------------------------------


def test_marca_com_pix_para_pessoa_fisica_e_prova_alta():
    texto = "ENEL informa: conta em atraso. Pague via Pix: " + montar_pix(nome="JOAO DA SILVA", cidade="CAMPINAS")
    sinais = cruzar(texto, levantar_achados(texto))
    assert graves(sinais, "alta") == [
        "A mensagem fala em nome de Enel, mas o Pix vai para uma pessoa física: JOAO DA SILVA, em Campinas."
    ]
    assert sinais[0].fonte == "verificador"
    assert nivel_pelos_sinais(sinais) == "provavel_golpe"


def test_nome_sem_cara_de_empresa_tambem_e_alta():
    texto = "Itaú: regularize seu cartão. " + montar_pix(chave="+5511999990000", nome="MARIA SOUZA")
    assert "MARIA SOUZA" in graves(cruzar(texto, levantar_achados(texto)), "alta")[0]


def test_empresa_com_outro_nome_e_so_media():
    pix = montar_pix(chave="11222333000181", nome="PAGAMENTOS DIGITAIS LTDA")
    texto = "Correios: pague a sua encomenda " + pix
    sinais = cruzar(texto, levantar_achados(texto))
    assert any("PAGAMENTOS DIGITAIS LTDA" in d for d in graves(sinais, "media"))
    assert not any("PAGAMENTOS" in d for d in graves(sinais, "alta"))


def test_pix_da_propria_marca_so_informa_o_recebedor():
    pix = montar_pix(chave="11222333000181", nome="ENEL DISTRIBUICAO SP", cidade="SAO PAULO", valor="189.90")
    texto = f"Enel: sua fatura de R$ 189,90 pode ser paga com o Pix {pix}"
    sinais = cruzar(texto, levantar_achados(texto))
    assert graves(sinais, "info") == [
        "O Pix vai para ENEL DISTRIBUICAO SP (empresa), em Sao Paulo, valor R$ 189,90."
    ]
    assert nivel_pelos_sinais(sinais) == "sem_sinais"


def test_valor_do_pix_diferente_do_texto():
    texto = "Sua parcela é de R$ 89,90. Pix: " + montar_pix(valor="890.00")
    assert any("R$ 890,00" in d and "R$ 89,90" in d for d in graves(cruzar(texto, levantar_achados(texto)), "media"))


def test_pix_adulterado_no_texto_e_alta():
    codigo = montar_pix(nome="JOAO DA SILVA").replace("JOAO DA SILVA", "JOAO DA SILVO")
    texto = "Paga aqui: " + codigo
    achados = Achados(pix=[(decodificar_pix(codigo), "texto")])
    assert any("não passa na conferência" in d for d in graves(cruzar(texto, achados), "alta"))


def test_pix_ilegivel_lido_do_print_e_so_media():
    codigo = montar_pix()[:-1] + "0"
    achados = Achados(pix=[(decodificar_pix(codigo), "imagem")])
    sinais = cruzar("", achados)
    assert not graves(sinais, "alta")
    assert any("print" in d for d in graves(sinais, "media"))


def test_marca_alegada_pela_ia_entra_no_cruzamento():
    # A marca só aparece no print (a IA a identificou); o texto colado não a cita.
    pix = decodificar_pix(montar_pix(nome="CARLOS PEREIRA"))
    sinais = cruzar("", Achados(pix=[(pix, "imagem")]), marca_alegada="enel")
    assert graves(sinais, "alta") == [
        "A mensagem fala em nome de Enel, mas o Pix vai para uma pessoa física: CARLOS PEREIRA, em Salvador."
    ]


# --- Boleto ----------------------------------------------------------------


def test_boleto_bancario_em_conta_de_luz():
    texto = "Cemig: segunda via da sua conta. Linha: " + montar_bancario(banco="341")
    sinais = cruzar(texto, levantar_achados(texto))
    assert any("boleto bancário comum" in d for d in graves(sinais, "media"))
    assert any("Itaú" in d for d in graves(sinais, "info"))


def test_boleto_de_outro_banco_em_nome_de_banco():
    texto = "Bradesco: pague a fatura do cartão " + montar_bancario(banco="260")
    assert any("Nubank" in d for d in graves(cruzar(texto, levantar_achados(texto)), "media"))


def test_conta_de_luz_de_verdade_nao_gera_alerta():
    texto = "Enel: sua conta de R$ 189,90. Código: " + montar_arrecadacao(segmento="3", centavos=18990)
    sinais = cruzar(texto, levantar_achados(texto))
    assert nivel_pelos_sinais(sinais) == "sem_sinais"
    assert graves(sinais, "info") == ["Conta do segmento Energia elétrica e gás, valor R$ 189,90."]


def test_conta_de_luz_com_segmento_de_agua():
    texto = "Enel: pague sua conta " + montar_arrecadacao(segmento="2")
    assert any("Saneamento" in d for d in graves(cruzar(texto, levantar_achados(texto)), "media"))


def test_boleto_invalido_e_media():
    linha = EXEMPLO_BB.replace("3 3737", "4 3737")
    sinais = cruzar("", Achados(boletos=[(validar_boleto(linha), "texto")]))
    assert any("não conferem" in d for d in graves(sinais, "media"))


# --- Links -----------------------------------------------------------------


def test_link_que_imita_marca_e_alta():
    texto = "Nubank: confirme seus dados em http://nubank-seguranca.top/login"
    sinais = cruzar(texto, levantar_achados(texto))
    assert any("imita Nubank" in d for d in graves(sinais, "alta"))
    assert any("HTTPS" in d for d in graves(sinais, "baixa"))


def test_marca_com_link_para_outro_site():
    texto = "Correios: sua encomenda aguarda pagamento em https://entregarapida.com/pagar"
    assert any("entregarapida.com" in d for d in graves(cruzar(texto, levantar_achados(texto)), "media"))


def test_link_oficial_da_marca_nao_gera_alerta():
    texto = "Correios: acompanhe em https://rastreamento.correios.com.br/app"
    assert nivel_pelos_sinais(cruzar(texto, levantar_achados(texto))) == "sem_sinais"


def test_link_sem_esquema_nao_e_acusado_de_sem_https():
    texto = "veja bit.ly/abc"
    sinais = cruzar(texto, levantar_achados(texto))
    assert not any("HTTPS" in s.descricao for s in sinais)
    assert any("encurtado" in d for d in graves(sinais, "media"))


def test_link_perigoso_no_safe_browsing_e_alta():
    link = analisar_link("https://exemplo.com").model_copy(
        update={"safe_browsing": "perigoso", "sinais": ["O Google classifica este link como perigoso: phishing"]}
    )
    assert graves(cruzar("", Achados(links=[link])), "alta") == [
        "O Google classifica este link como perigoso: phishing"
    ]


def test_url_dentro_do_pix_dinamico_nao_vira_link():
    pix = montar_pix(chave=None, url="pix.exemplo.com.br/qr/v2/abc")
    achados = levantar_achados("Pague: " + pix)
    assert len(achados.pix) == 1
    assert achados.links == []


# --- Táticas no texto ------------------------------------------------------


def test_troca_de_numero_pedindo_pix_e_alta():
    sinais = sinais_de_texto("Oi mãe, troquei de número! Salva esse. Consegue me fazer um Pix urgente?")
    assert any("trocou de número" in d for d in graves(sinais, "alta"))
    assert all(s.fonte == "regra" for s in sinais)
    assert not any("trocou de número" in d for d in graves(sinais, "media"))


def test_troca_de_numero_sem_dinheiro_e_so_media():
    sinais = sinais_de_texto("Oi, mudei de número, salva aí")
    assert not graves(sinais, "alta")
    assert graves(sinais, "media")


def test_pedido_de_codigo_e_alta():
    assert graves(sinais_de_texto("Te mandei um código por SMS sem querer, me passa ele?"), "alta")


def test_aviso_legitimo_de_codigo_nao_dispara():
    assert sinais_de_texto("Seu código de verificação é 482913. Não compartilhe com ninguém.") == []


@pytest.mark.parametrize(
    "texto, trecho",
    [
        ("Sua conta será bloqueada em até 24h", "pressa"),
        ("Não conta pra ninguém, é surpresa", "segredo"),
        ("Faz o Pix e não conta pro pai", "segredo"),
        ("Atualize sua senha no link", "senha"),
        ("Sua encomenda foi taxada, pague a taxa de liberação", "taxa"),
        ("Parabéns, você ganhou um prêmio!", "prêmio"),
        ("Identificamos uma compra suspeita no seu cartão", "compra suspeita"),
    ],
)
def test_taticas(texto, trecho):
    assert any(trecho in s.descricao for s in sinais_de_texto(texto))


@pytest.mark.parametrize(
    "texto",
    [
        "Oi! Chego às 19h para o jantar.",
        "Seu pedido foi entregue. Obrigado por comprar conosco.",
        "Lembrete: consulta amanhã às 10h. Responda SIM para confirmar.",
    ],
)
def test_mensagens_comuns_sem_sinais(texto):
    assert nivel_pelos_sinais(cruzar(texto, levantar_achados(texto))) == "sem_sinais"


# --- Nível -----------------------------------------------------------------


def s(gravidade):
    return Sinal(descricao=gravidade, gravidade=gravidade, fonte="regra")


@pytest.mark.parametrize(
    "gravidades, nivel",
    [
        ([], "sem_sinais"),
        (["info", "baixa", "baixa"], "sem_sinais"),
        (["media"], "atencao"),
        (["media", "media"], "atencao"),
        (["media", "media", "media"], "provavel_golpe"),
        (["alta"], "provavel_golpe"),
    ],
)
def test_nivel_pelos_sinais(gravidades, nivel):
    assert nivel_pelos_sinais([s(g) for g in gravidades]) == nivel


def test_sinais_ordenados_e_sem_repeticao():
    texto = "Itaú urgente urgente " + montar_pix(nome="ANA LIMA") + " " + montar_pix(nome="ANA LIMA")
    sinais = cruzar(texto, levantar_achados(texto))
    assert [x.gravidade for x in sinais] == sorted(
        (x.gravidade for x in sinais), key=["alta", "media", "baixa", "info"].index
    )
    assert len({x.descricao for x in sinais}) == len(sinais)
