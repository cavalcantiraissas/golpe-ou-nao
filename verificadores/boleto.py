"""Validador da linha digitável de boletos (regras da FEBRABAN).

Há dois formatos:

* **Boleto bancário** (47 dígitos): cobranças em geral. Os 3 primeiros dígitos
  são o banco onde o dinheiro cai. Três campos têm dígito verificador módulo 10
  e o código de barras inteiro tem um dígito geral módulo 11.

      AAABC.CCCCX DDDDD.DDDDDY EEEEE.EEEEEZ K FFFFVVVVVVVVVV
      AAA banco  B moeda  X/Y/Z DVs dos campos  K DV geral
      FFFF fator de vencimento  VVVVVVVVVV valor em centavos

* **Arrecadação** (48 dígitos, começa com 8): contas de luz, água, telefone e
  tributos. São quatro blocos de 11 dígitos, cada um com seu DV. O terceiro
  dígito diz se os DVs usam módulo 10 (6 ou 7) ou módulo 11 (8 ou 9).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from verificadores.modelos import ResultadoBoleto

BANCOS = {
    "001": "Banco do Brasil",
    "004": "Banco do Nordeste",
    "021": "Banestes",
    "033": "Santander",
    "041": "Banrisul",
    "070": "BRB",
    "077": "Banco Inter",
    "104": "Caixa Econômica Federal",
    "136": "Unicred",
    "197": "Stone",
    "208": "BTG Pactual",
    "237": "Bradesco",
    "260": "Nubank",
    "290": "PagBank",
    "323": "Mercado Pago",
    "336": "C6 Bank",
    "341": "Itaú",
    "380": "PicPay",
    "422": "Safra",
    "748": "Sicredi",
    "756": "Sicoob",
}

SEGMENTOS = {
    "1": "Prefeituras",
    "2": "Saneamento (água e esgoto)",
    "3": "Energia elétrica e gás",
    "4": "Telecomunicações",
    "5": "Órgãos governamentais",
    "6": "Carnês e demais empresas (identificadas por CNPJ)",
    "7": "Multas de trânsito",
    "9": "Uso exclusivo do banco",
}

# O fator de vencimento conta dias a partir de 07/10/1997. Ao chegar a 9999,
# em 21/02/2025, voltou para 1000 (= 22/02/2025). Por isso cada fator tem duas
# datas possíveis; vale a mais próxima da data de referência.
BASE_FATOR_ANTIGA = date(1997, 10, 7)
BASE_FATOR_NOVA = date(2025, 2, 22)


def modulo10(numero: str) -> int:
    """Pesos 2, 1, 2, 1... da direita para a esquerda, somando os algarismos dos produtos."""
    soma = 0
    for i, digito in enumerate(reversed(numero)):
        produto = int(digito) * (2 if i % 2 == 0 else 1)
        soma += produto // 10 + produto % 10
    return (10 - soma % 10) % 10


def _soma_modulo11(numero: str) -> int:
    """Pesos 2 a 9, recomeçando, da direita para a esquerda; devolve o resto por 11."""
    soma = sum(int(d) * (2 + i % 8) for i, d in enumerate(reversed(numero)))
    return soma % 11


def modulo11_bancario(numero: str) -> int:
    """DV geral do boleto bancário: resto 0, 1 ou 10 resulta em 1."""
    dv = 11 - _soma_modulo11(numero)
    return 1 if dv in (0, 10, 11) else dv


def modulo11_arrecadacao(numero: str) -> int:
    """DV de arrecadação: resto 0 ou 1 resulta em 0."""
    resto = _soma_modulo11(numero)
    return 0 if resto in (0, 1) else 11 - resto


def data_do_fator(fator: int, referencia: date | None = None) -> date | None:
    if fator == 0:
        return None
    referencia = referencia or date.today()
    candidatas = [BASE_FATOR_ANTIGA + timedelta(days=fator)]
    if fator >= 1000:
        candidatas.append(BASE_FATOR_NOVA + timedelta(days=fator - 1000))
    return min(candidatas, key=lambda d: abs((d - referencia).days))


def extrair_linhas_digitaveis(texto: str) -> list[str]:
    """Encontra linhas digitáveis num texto, aceitando pontos, espaços e hífens no meio."""
    achados = []
    for trecho in re.finditer(r"\d[\d.\s-]{42,70}\d", texto):
        digitos = re.sub(r"\D", "", trecho.group())
        if len(digitos) in (47, 48):
            achados.append(digitos)
    return achados


def _validar_bancario(linha: str, referencia: date | None) -> ResultadoBoleto:
    erros = []
    campos = [(linha[0:9], linha[9]), (linha[10:20], linha[20]), (linha[21:31], linha[31])]
    for n, (corpo, dv) in enumerate(campos, start=1):
        esperado = modulo10(corpo)
        if esperado != int(dv):
            erros.append(f"Dígito verificador do campo {n} não confere (esperado {esperado}, veio {dv})")

    codigo_barras = linha[0:4] + linha[32] + linha[33:47] + linha[4:9] + linha[10:20] + linha[21:31]
    dv_geral = modulo11_bancario(codigo_barras[:4] + codigo_barras[5:])
    if dv_geral != int(linha[32]):
        erros.append(f"Dígito verificador geral não confere (esperado {dv_geral}, veio {linha[32]})")
    if linha[3] != "9":
        erros.append("Moeda diferente do real")

    centavos = int(linha[37:47])
    banco = linha[0:3]
    return ResultadoBoleto(
        valido=not erros,
        erros=erros,
        tipo="bancario",
        linha_digitavel=linha,
        codigo_barras=codigo_barras,
        codigo_banco=banco,
        nome_banco=BANCOS.get(banco),
        valor=Decimal(centavos).scaleb(-2) if centavos else None,
        vencimento=data_do_fator(int(linha[33:37]), referencia),
    )


def _validar_arrecadacao(linha: str) -> ResultadoBoleto:
    erros = []
    identificador = linha[2]
    if identificador in "67":
        calcular_dv = modulo10
    elif identificador in "89":
        calcular_dv = modulo11_arrecadacao
    else:
        return ResultadoBoleto(
            valido=False,
            erros=[f"Terceiro dígito deveria ser 6, 7, 8 ou 9 (veio {identificador})"],
            tipo="arrecadacao",
            linha_digitavel=linha,
        )

    blocos = [linha[i : i + 12] for i in range(0, 48, 12)]
    for n, bloco in enumerate(blocos, start=1):
        esperado = calcular_dv(bloco[:11])
        if esperado != int(bloco[11]):
            erros.append(f"Dígito verificador do bloco {n} não confere (esperado {esperado}, veio {bloco[11]})")

    codigo_barras = "".join(b[:11] for b in blocos)
    dv_geral = calcular_dv(codigo_barras[:3] + codigo_barras[4:])
    if dv_geral != int(codigo_barras[3]):
        erros.append(f"Dígito verificador geral não confere (esperado {dv_geral}, veio {codigo_barras[3]})")

    segmento = codigo_barras[1]
    # Valor efetivo (6 e 8) em centavos; 7 e 9 trazem uma quantidade de referência, não reais.
    centavos = int(codigo_barras[4:15]) if identificador in "68" else 0
    empresa = codigo_barras[15:23] if segmento == "6" else codigo_barras[15:19]

    return ResultadoBoleto(
        valido=not erros,
        erros=erros,
        tipo="arrecadacao",
        linha_digitavel=linha,
        codigo_barras=codigo_barras,
        segmento=SEGMENTOS.get(segmento, f"Desconhecido ({segmento})"),
        codigo_empresa=empresa,
        valor=Decimal(centavos).scaleb(-2) if centavos else None,
    )


def validar_boleto(linha_digitavel: str, referencia: date | None = None) -> ResultadoBoleto:
    """Confere os dígitos verificadores e extrai banco (ou segmento), valor e vencimento.

    ``referencia`` decide entre as duas datas possíveis do fator de vencimento
    (padrão: hoje).
    """
    linha = re.sub(r"\D", "", linha_digitavel)
    if len(linha) == 47:
        return _validar_bancario(linha, referencia)
    if len(linha) == 48 and linha[0] == "8":
        return _validar_arrecadacao(linha)
    if len(linha) == 44:
        return ResultadoBoleto(
            valido=False,
            erros=["Isto parece o código de barras (44 dígitos), não a linha digitável"],
        )
    return ResultadoBoleto(
        valido=False,
        erros=[f"Linha digitável deveria ter 47 ou 48 dígitos (tem {len(linha)})"],
    )
