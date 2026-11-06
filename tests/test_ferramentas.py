import json

import pytest

from agente.cruzamento import Achados, levantar_achados
from agente.ferramentas import DECLARACOES, Executor, achados_em_json
from tests.test_boleto import montar_bancario
from tests.test_pix import montar_pix


@pytest.fixture(autouse=True)
def sem_safe_browsing(monkeypatch):
    monkeypatch.delenv("GOOGLE_SAFE_BROWSING_KEY", raising=False)


def test_declaracoes():
    assert [d.name for d in DECLARACOES] == [
        "decodificar_pix",
        "validar_boleto",
        "analisar_link",
        "emitir_veredito",
    ]
    veredito = DECLARACOES[-1].parameters_json_schema
    assert veredito["properties"]["nivel"]["enum"] == ["provavel_golpe", "atencao", "sem_sinais"]


def test_pix_lido_do_print_fica_com_origem_imagem():
    executor = Executor("", Achados(), tem_imagem=True)
    resposta = executor.executar("decodificar_pix", {"codigo": montar_pix(nome="ANA LIMA")})
    assert resposta["nome_recebedor"] == "ANA LIMA"
    assert executor.achados.pix[0][1] == "imagem"
    assert executor.chamadas == ["decodificar_pix"]


def test_pix_que_esta_no_texto_fica_com_origem_texto():
    codigo = montar_pix()
    texto = "Paga esse: " + codigo[:30] + "\n" + codigo[30:]
    executor = Executor(texto, Achados(), tem_imagem=True)
    executor.executar("decodificar_pix", {"codigo": codigo})
    assert executor.achados.pix[0][1] == "texto"


def test_codigo_ja_analisado_nao_se_repete():
    codigo = montar_pix()
    texto = "Pix: " + codigo
    executor = Executor(texto, levantar_achados(texto), tem_imagem=False)
    executor.executar("decodificar_pix", {"codigo": codigo})
    executor.executar("decodificar_pix", {"codigo": codigo})
    assert len(executor.achados.pix) == 1


def test_boleto_do_print():
    linha = montar_bancario(banco="237", centavos=15000)
    executor = Executor("olha esse boleto", Achados(), tem_imagem=True)
    resposta = executor.executar("validar_boleto", {"linha_digitavel": linha})
    assert resposta["nome_banco"] == "Bradesco"
    assert resposta["valor"] == "150.00"
    assert executor.achados.boletos[0][1] == "imagem"


def test_boleto_com_pontos_conta_como_ja_visto():
    linha = montar_bancario()
    formatada = f"{linha[:5]}.{linha[5:10]} {linha[10:]}"
    texto = "Boleto: " + formatada
    executor = Executor(texto, levantar_achados(texto), tem_imagem=False)
    executor.executar("validar_boleto", {"linha_digitavel": linha})
    assert len(executor.achados.boletos) == 1


def test_link():
    executor = Executor("", Achados(), tem_imagem=True)
    resposta = executor.executar("analisar_link", {"url": "http://itau-acesso.top"})
    assert resposta["marca_imitada"] == "Itaú"
    assert len(executor.achados.links) == 1


def test_ferramenta_desconhecida():
    assert "erro" in Executor("", Achados(), tem_imagem=False).executar("apagar_tudo", {})


def test_argumento_ausente():
    assert "erro" in Executor("", Achados(), tem_imagem=False).executar("decodificar_pix", {})


def test_achados_em_json_e_serializavel():
    texto = "Pix " + montar_pix() + " boleto " + montar_bancario() + " link bit.ly/x"
    dados = achados_em_json(levantar_achados(texto))
    json.dumps(dados)
    assert dados["pix"][0]["origem"] == "texto"
    assert len(dados["boletos"]) == 1
    assert dados["links"][0]["encurtador"] is True
