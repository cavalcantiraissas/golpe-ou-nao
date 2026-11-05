from decimal import Decimal

import pytest

from verificadores.pix import classificar_chave, crc16_ccitt, decodificar_pix, extrair_pix

# Exemplo oficial do Manual de Padrões para Iniciação do Pix (Banco Central).
EXEMPLO_BCB = (
    "00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-426655440000"
    "5204000053039865802BR5913Fulano de Tal6008BRASILIA62070503***63041D3D"
)


def campo(ident: str, valor: str) -> str:
    return f"{ident}{len(valor):02d}{valor}"


def montar_pix(
    chave: str | None = "12345678909",
    nome: str = "JOAO DA SILVA",
    cidade: str = "SALVADOR",
    valor: str | None = "350.00",
    txid: str = "***",
    url: str | None = None,
    descricao: str | None = None,
) -> str:
    conta = campo("00", "br.gov.bcb.pix")
    if chave:
        conta += campo("01", chave)
    if descricao:
        conta += campo("02", descricao)
    if url:
        conta += campo("25", url)
    corpo = campo("00", "01") + (campo("01", "12") if url else "") + campo("26", conta)
    corpo += campo("52", "0000") + campo("53", "986")
    if valor:
        corpo += campo("54", valor)
    corpo += campo("58", "BR") + campo("59", nome) + campo("60", cidade)
    corpo += campo("62", campo("05", txid)) + "6304"
    return corpo + crc16_ccitt(corpo)


# --- CRC -------------------------------------------------------------------


def test_crc_vetor_de_referencia_ccitt_false():
    assert crc16_ccitt("123456789") == "29B1"


def test_crc_do_exemplo_do_banco_central():
    assert crc16_ccitt(EXEMPLO_BCB[:-4]) == "1D3D"


# --- Decodificação ---------------------------------------------------------


def test_exemplo_do_banco_central():
    r = decodificar_pix(EXEMPLO_BCB)
    assert r.valido and r.crc_ok
    assert r.nome_recebedor == "Fulano de Tal"
    assert r.cidade == "BRASILIA"
    assert r.chave == "123e4567-e12b-12d1-a456-426655440000"
    assert r.tipo_chave == "aleatoria"
    assert r.valor is None
    assert r.identificador == "***"
    assert not r.dinamico


def test_pix_com_valor_para_pessoa_fisica():
    r = decodificar_pix(montar_pix())
    assert r.valido
    assert r.valor == Decimal("350.00")
    assert r.tipo_chave == "cpf"
    assert r.tipo_recebedor == "pessoa_fisica"
    assert r.nome_recebedor == "JOAO DA SILVA"
    assert r.cidade == "SALVADOR"


def test_pix_para_empresa_pelo_cnpj():
    r = decodificar_pix(montar_pix(chave="11222333000181", nome="ENEL DISTRIBUICAO SP"))
    assert r.tipo_chave == "cnpj"
    assert r.tipo_recebedor == "pessoa_juridica"


def test_empresa_reconhecida_pelo_nome_quando_chave_nao_diz():
    r = decodificar_pix(montar_pix(chave="financeiro@loja.com.br", nome="LOJA EXEMPLO LTDA"))
    assert r.tipo_chave == "email"
    assert r.tipo_recebedor == "pessoa_juridica"


def test_telefone_sem_nome_de_empresa_fica_indefinido():
    r = decodificar_pix(montar_pix(chave="+5511987654321", nome="MARIA SOUZA"))
    assert r.tipo_chave == "telefone"
    assert r.tipo_recebedor == "indefinido"


def test_pix_dinamico_traz_url_de_cobranca():
    r = decodificar_pix(montar_pix(chave=None, url="pix.exemplo.com.br/qr/v2/abc123"))
    assert r.valido
    assert r.dinamico
    assert r.url_cobranca == "pix.exemplo.com.br/qr/v2/abc123"
    assert r.chave is None


def test_descricao_e_txid():
    r = decodificar_pix(montar_pix(descricao="Fatura outubro", txid="FAT2026"))
    assert r.descricao == "Fatura outubro"
    assert r.identificador == "FAT2026"


def test_nome_com_acento_usa_utf8_no_crc():
    r = decodificar_pix(montar_pix(nome="JOSÉ ARAÚJO", cidade="SÃO PAULO"))
    assert r.valido
    assert r.nome_recebedor == "JOSÉ ARAÚJO"


def test_quebras_de_linha_e_espacos_nas_pontas_sao_ignorados():
    codigo = montar_pix()
    quebrado = "  " + codigo[:40] + "\n" + codigo[40:] + "\n"
    assert decodificar_pix(quebrado).valido


# --- Códigos adulterados ou inválidos --------------------------------------


def test_nome_trocado_quebra_o_crc():
    adulterado = montar_pix(nome="JOAO DA SILVA").replace("JOAO DA SILVA", "ENEL SP LTDAA")
    r = decodificar_pix(adulterado)
    assert not r.valido
    assert not r.crc_ok
    assert any("CRC" in e for e in r.erros)
    # Mesmo inválido, o que foi lido continua disponível para o agente explicar.
    assert r.nome_recebedor == "ENEL SP LTDAA"


def test_crc_em_minusculas_e_aceito():
    codigo = montar_pix()
    assert decodificar_pix(codigo[:-4] + codigo[-4:].lower()).crc_ok


def test_codigo_cortado():
    r = decodificar_pix(montar_pix()[:60])
    assert not r.valido
    assert r.erros


@pytest.mark.parametrize("entrada", ["", "olá, tudo bem?", "12ab", "0002"])
def test_lixo_nao_levanta_excecao(entrada):
    r = decodificar_pix(entrada)
    assert not r.valido
    assert r.erros


def test_sem_conta_pix():
    corpo = campo("00", "01") + campo("26", campo("00", "br.com.outro")) + campo("59", "X")
    corpo += campo("60", "Y") + "6304"
    r = decodificar_pix(corpo + crc16_ccitt(corpo))
    assert r.crc_ok
    assert not r.valido
    assert any("br.gov.bcb.pix" in e for e in r.erros)


def test_texto_sobrando_depois_do_crc():
    r = decodificar_pix(montar_pix() + "XYZ")
    assert not r.valido
    assert any("sobrando" in e for e in r.erros)


# --- Extração de dentro de uma mensagem ------------------------------------


def test_extrai_pix_do_meio_de_uma_mensagem():
    codigo = montar_pix(nome="CARLOS PEREIRA")
    mensagem = f"Oi mãe, troquei de número. Paga pra mim esse aqui:\n{codigo}\nDepois te devolvo!"
    assert extrair_pix(mensagem) == [codigo]


def test_extrai_pix_quebrado_em_linhas():
    codigo = montar_pix()
    mensagem = "Segue o código:\n" + codigo[:50] + "\n" + codigo[50:]
    assert extrair_pix(mensagem) == [codigo]


def test_extrai_dois_codigos():
    a, b = montar_pix(nome="A SILVA"), montar_pix(nome="B SOUZA")
    assert extrair_pix(f"{a} ou então {b}") == [a, b]


def test_mensagem_sem_pix():
    assert extrair_pix("Sua encomenda está a caminho") == []


# --- Tipo de chave ---------------------------------------------------------


@pytest.mark.parametrize(
    "chave, esperado",
    [
        ("12345678909", "cpf"),
        ("11222333000181", "cnpj"),
        ("+5561999998888", "telefone"),
        ("fulano@gmail.com", "email"),
        ("123e4567-e12b-12d1-a456-426655440000", "aleatoria"),
        ("abc", "desconhecida"),
    ],
)
def test_classificar_chave(chave, esperado):
    assert classificar_chave(chave) == esperado
