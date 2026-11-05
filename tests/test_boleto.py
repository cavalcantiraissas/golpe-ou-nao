from datetime import date
from decimal import Decimal

import pytest

from verificadores.boleto import (
    data_do_fator,
    extrair_linhas_digitaveis,
    modulo10,
    modulo11_arrecadacao,
    modulo11_bancario,
    validar_boleto,
)

# Exemplo de boleto do Banco do Brasil publicado na documentação de cobrança.
EXEMPLO_BB = "00190.50095 40144.816069 06809.350314 3 37370000000100"


# Gerador de linhas para os testes, com cálculo de DV escrito de outro jeito
# (tabela de pesos explícita) para não conferir o código contra ele mesmo.


def _dv10(n: str) -> int:
    pesos = [2, 1] * len(n)
    total = sum(sum(divmod(int(d) * p, 10)) for d, p in zip(n[::-1], pesos))
    return -total % 10


def _resto11(n: str) -> int:
    pesos = [2, 3, 4, 5, 6, 7, 8, 9] * 6
    return sum(int(d) * p for d, p in zip(n[::-1], pesos)) % 11


def montar_bancario(banco="341", fator="1500", centavos=12345, livre="1" * 25) -> str:
    sem_dv = banco + "9" + fator + f"{centavos:010d}" + livre  # 43 dígitos
    dv = 11 - _resto11(sem_dv)
    dv = 1 if dv > 9 or dv == 0 else dv
    barras = sem_dv[:4] + str(dv) + sem_dv[4:]
    c1 = barras[0:4] + barras[19:24]
    c2, c3 = barras[24:34], barras[34:44]
    return f"{c1}{_dv10(c1)}{c2}{_dv10(c2)}{c3}{_dv10(c3)}{barras[4]}{barras[5:19]}"


def montar_arrecadacao(segmento="3", identificador="6", centavos=18990, empresa="0123", resto="9" * 25):
    sem_dv = "8" + segmento + identificador + f"{centavos:011d}" + empresa + resto
    sem_dv = sem_dv[:43]
    if identificador in "67":
        calc = _dv10
    else:
        def calc(n):
            r = _resto11(n)
            return 0 if r < 2 else 11 - r
    barras = sem_dv[:3] + str(calc(sem_dv)) + sem_dv[3:]
    return "".join(b + str(calc(b)) for b in (barras[i : i + 11] for i in range(0, 44, 11)))


def trocar_digito(linha: str, posicao: int) -> str:
    novo = str((int(linha[posicao]) + 1) % 10)
    return linha[:posicao] + novo + linha[posicao + 1 :]


# --- Funções de DV ---------------------------------------------------------


def test_modulo10_campo1_do_exemplo_bb():
    assert modulo10("001905009") == 5


def test_modulo11_bancario_resto_que_daria_10_vira_1():
    # Procura um número cujo DV "natural" seria 0, 10 ou 11.
    for n in range(1000):
        numero = f"{n:043d}"
        if 11 - _resto11(numero) in (10, 11):
            assert modulo11_bancario(numero) == 1
            break
    else:
        pytest.fail("nenhum caso encontrado")


def test_modulo11_arrecadacao_resto_0_ou_1_vira_0():
    for n in range(1000):
        numero = f"{n:043d}"
        if _resto11(numero) in (0, 1):
            assert modulo11_arrecadacao(numero) == 0
            break
    else:
        pytest.fail("nenhum caso encontrado")


# --- Boleto bancário -------------------------------------------------------


def test_exemplo_banco_do_brasil():
    r = validar_boleto(EXEMPLO_BB, referencia=date(2008, 1, 1))
    assert r.valido, r.erros
    assert r.tipo == "bancario"
    assert r.codigo_banco == "001"
    assert r.nome_banco == "Banco do Brasil"
    assert r.valor == Decimal("1.00")
    assert r.vencimento == date(2007, 12, 31)
    assert r.codigo_barras == "00193373700000001000500940144816060680935031"


def test_boleto_gerado_itau():
    r = validar_boleto(montar_bancario(banco="341", centavos=48990))
    assert r.valido, r.erros
    assert r.nome_banco == "Itaú"
    assert r.valor == Decimal("489.90")


def test_banco_fora_da_lista_mantem_o_codigo():
    r = validar_boleto(montar_bancario(banco="999"))
    assert r.valido
    assert r.codigo_banco == "999"
    assert r.nome_banco is None


def test_valor_zero_significa_valor_em_aberto():
    r = validar_boleto(montar_bancario(centavos=0))
    assert r.valido
    assert r.valor is None


def test_fator_zero_sem_vencimento():
    r = validar_boleto(montar_bancario(fator="0000"))
    assert r.valido
    assert r.vencimento is None


@pytest.mark.parametrize("posicao", [0, 5, 9, 12, 20, 25, 31, 32, 35, 46])
def test_qualquer_digito_trocado_e_detectado(posicao):
    linha = montar_bancario()
    r = validar_boleto(trocar_digito(linha, posicao))
    assert not r.valido
    assert r.erros


def test_valor_adulterado_quebra_o_dv_geral():
    linha = montar_bancario(centavos=12345)
    adulterada = linha[:37] + f"{99999:010d}"
    r = validar_boleto(adulterada)
    assert not r.valido
    assert any("geral" in e for e in r.erros)
    assert r.valor == Decimal("999.99")


def test_formatacao_com_pontos_e_espacos():
    linha = montar_bancario()
    formatada = f"{linha[:5]}.{linha[5:10]} {linha[10:15]}.{linha[15:21]} {linha[21:26]}.{linha[26:32]} {linha[32]} {linha[33:]}"
    assert validar_boleto(formatada).valido


# --- Fator de vencimento ---------------------------------------------------


def test_fator_1000_depois_do_reinicio_de_2025():
    assert data_do_fator(1000, referencia=date(2026, 11, 5)) == date(2025, 2, 22)


def test_fator_1000_no_ciclo_antigo():
    assert data_do_fator(1000, referencia=date(2000, 7, 1)) == date(2000, 7, 3)


def test_fator_9999_ultimo_dia_do_ciclo_antigo():
    assert data_do_fator(9999, referencia=date(2025, 2, 1)) == date(2025, 2, 21)


def test_fator_recente():
    # 22/02/2025 + 640 dias = 24/11/2026
    assert data_do_fator(1640, referencia=date(2026, 11, 5)) == date(2026, 11, 24)


# --- Arrecadação (contas de consumo e tributos) ----------------------------


def test_conta_de_luz_modulo10():
    r = validar_boleto(montar_arrecadacao(segmento="3", identificador="6", centavos=18990))
    assert r.valido, r.erros
    assert r.tipo == "arrecadacao"
    assert r.segmento == "Energia elétrica e gás"
    assert r.valor == Decimal("189.90")
    assert r.codigo_empresa == "0123"
    assert r.codigo_banco is None


def test_conta_de_agua_modulo11():
    r = validar_boleto(montar_arrecadacao(segmento="2", identificador="8", centavos=7450))
    assert r.valido, r.erros
    assert r.segmento == "Saneamento (água e esgoto)"
    assert r.valor == Decimal("74.50")


def test_identificador_7_nao_traz_valor_em_reais():
    r = validar_boleto(montar_arrecadacao(identificador="7", centavos=500))
    assert r.valido
    assert r.valor is None


def test_segmento_6_usa_cnpj_de_8_digitos():
    r = validar_boleto(montar_arrecadacao(segmento="6", empresa="11222333"))
    assert r.valido
    assert r.codigo_empresa == "11222333"


@pytest.mark.parametrize("identificador", ["6", "8"])
@pytest.mark.parametrize("posicao", [1, 4, 11, 15, 23, 30, 35, 47])
def test_arrecadacao_digito_trocado(identificador, posicao):
    linha = montar_arrecadacao(identificador=identificador)
    assert not validar_boleto(trocar_digito(linha, posicao)).valido


def test_terceiro_digito_invalido():
    linha = "835" + "0" * 45
    r = validar_boleto(linha)
    assert not r.valido
    assert "terceiro dígito" in r.erros[0].lower()


# --- Entradas inválidas ----------------------------------------------------


def test_codigo_de_barras_em_vez_de_linha():
    r = validar_boleto("0" * 44)
    assert not r.valido
    assert "código de barras" in r.erros[0]


@pytest.mark.parametrize("entrada", ["", "abc", "123", "1" * 50])
def test_tamanho_errado(entrada):
    r = validar_boleto(entrada)
    assert not r.valido
    assert r.erros


# --- Extração de dentro de uma mensagem ------------------------------------


def test_extrai_linha_formatada_de_uma_mensagem():
    mensagem = f"Prezado cliente, sua fatura vence hoje. Pague pelo código: {EXEMPLO_BB}. Evite o corte!"
    assert extrair_linhas_digitaveis(mensagem) == ["00190500954014481606906809350314337370000000100"]


def test_extrai_linha_de_arrecadacao():
    linha = montar_arrecadacao()
    mensagem = f"Conta de luz: {linha[:12]}-{linha[12:24]} {linha[24:36]} {linha[36:]}"
    assert extrair_linhas_digitaveis(mensagem) == [linha]


def test_mensagem_sem_boleto():
    assert extrair_linhas_digitaveis("Ligue 0800 123 4567 para regularizar") == []
