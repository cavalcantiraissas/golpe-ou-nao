"""A tela inteira rodada pelo AppTest do Streamlit (sem navegador e sem IA)."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def sem_chaves(monkeypatch):
    for variavel in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_SAFE_BROWSING_KEY"):
        monkeypatch.delenv(variavel, raising=False)


@pytest.fixture
def app():
    tela = AppTest.from_file(APP, default_timeout=30).run()
    assert not tela.exception
    return tela


def botao(tela, rotulo):
    return next(b for b in tela.button if b.label == rotulo)


def test_tela_inicial_mostra_exemplos_e_avisa_que_a_ia_esta_desligada(app):
    rotulos = {b.label for b in app.button}
    assert {"Conta de luz atrasada", "Taxa dos Correios", "Analisar", "Limpar"} <= rotulos
    assert any("IA desligada" in w.value for w in app.sidebar.warning)


def test_exemplo_preenche_o_texto(app):
    app.button(key="exemplo-conta-de-luz").click().run()
    assert app.text_area[0].value.startswith("ENEL INFORMA")


def test_analisa_golpe_e_mostra_a_prova(app):
    app.button(key="exemplo-conta-de-luz").click().run()
    botao(app, "Analisar").click().run()
    assert not app.exception
    (faixa,) = app.error
    assert faixa.value.startswith("### Provável golpe\nA mensagem fala em nome de Enel")
    textos = [m.value for m in app.markdown]
    assert any(":blue-badge[prova]" in t and "pessoa física" in t for t in textos)
    assert any("**Quem recebe:** RODRIGO A FERREIRA" in t for t in textos)
    assert any("Análise feita sem IA" in i.value for i in app.info)


def test_mensagem_legitima(app):
    app.button(key="exemplo-mensalidade-academia").click().run()
    botao(app, "Analisar").click().run()
    (faixa,) = app.success
    assert faixa.value.startswith("### Sem sinais de golpe")


def test_texto_digitado(app):
    app.text_area[0].input("Pague a taxa de liberação: http://correios-taxa.top").run()
    botao(app, "Analisar").click().run()
    (faixa,) = app.error
    assert "correios-taxa.top imita Correios" in faixa.value
    assert any("**Imita:** Correios" in m.value for m in app.markdown)


def test_sem_mensagem_pede_texto_ou_print(app):
    botao(app, "Analisar").click().run()
    assert any("Cole o texto" in w.value for w in app.warning)
    assert not app.error and not app.success


def test_exemplo_de_print_envia_a_imagem(app):
    app.button(key="exemplo-print-filho").click().run()
    assert app.text_area[0].value == ""
    botao(app, "Analisar").click().run()
    assert not app.exception
    # Este aviso só aparece quando a análise recebeu uma imagem.
    assert any("o print não pôde ser lido" in i.value for i in app.info)


def test_limpar_apaga_texto_e_resultado(app):
    app.button(key="exemplo-conta-de-luz").click().run()
    botao(app, "Analisar").click().run()
    botao(app, "Limpar").click().run()
    assert app.text_area[0].value == ""
    assert not app.error
