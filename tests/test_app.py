"""A tela inteira rodada pelo AppTest do Streamlit (sem navegador e sem IA)."""

import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from agente import analise  # noqa: E402

APP = Path(__file__).resolve().parent.parent / "app.py"
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")


@pytest.fixture(autouse=True)
def sem_chaves(monkeypatch):
    for variavel in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_SAFE_BROWSING_KEY"):
        monkeypatch.delenv(variavel, raising=False)


@pytest.fixture
def app():
    tela = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not tela.exception
    return tela


def html(tela) -> str:
    return "\n".join(h.value for h in tela.get("html"))


def escolher(tela, exemplo_id):
    tela.button_group(key="exemplo_escolhido").set_value(exemplo_id).run()


def botao(tela, rotulo):
    return next(b for b in tela.button if b.label == rotulo)


def test_tela_inicial_mostra_exemplos_e_ia_desligada(app):
    opcoes = app.button_group(key="exemplo_escolhido").options
    assert len(opcoes) == 9
    assert {"Analisar", "Limpar"} <= {b.label for b in app.button}
    assert "IA desligada" in html(app)


def test_aviso_de_privacidade_perto_da_mensagem(app):
    assert any("a mensagem é enviada ao Google" in c.value for c in app.caption)


def test_exemplo_preenche_o_texto(app):
    escolher(app, "conta-de-luz")
    assert app.text_area(key="texto").value.startswith("ENEL INFORMA")


def test_analisa_golpe_e_mostra_a_prova(app):
    escolher(app, "conta-de-luz")
    botao(app, "Analisar").click().run()
    assert not app.exception
    pagina = html(app)
    assert '<p class="gn-nivel">Provável golpe</p>' in pagina
    assert "A mensagem fala em nome de Enel" in pagina
    assert '<span class="gn-fonte gn-fonte-verificador">Prova</span>' in pagina
    assert "<dt>Quem recebe</dt><dd><span>RODRIGO A FERREIRA</span></dd>" in pagina
    assert "Análise feita sem IA" in pagina


def test_mensagem_legitima(app):
    escolher(app, "mensalidade-academia")
    botao(app, "Analisar").click().run()
    assert '<p class="gn-nivel">Sem sinais de golpe</p>' in html(app)


def test_texto_digitado(app):
    app.text_area(key="texto").input("Pague a taxa de liberação: http://correios-taxa.top").run()
    botao(app, "Analisar").click().run()
    pagina = html(app)
    assert "correios-taxa.top imita Correios" in pagina
    assert "<dt>Imita</dt><dd><span>Correios</span></dd>" in pagina


def test_sem_mensagem_pede_texto_ou_print(app):
    botao(app, "Analisar").click().run()
    assert any("Cole o texto" in w.value for w in app.warning)
    assert 'class="gn-veredito' not in html(app)


def test_exemplo_de_print_envia_a_imagem(app):
    escolher(app, "print-filho")
    assert app.text_area(key="texto").value == ""
    botao(app, "Analisar").click().run()
    assert not app.exception
    # Este aviso só aparece quando a análise recebeu uma imagem.
    assert "o print não pôde ser lido" in html(app)


def test_limpar_apaga_texto_exemplo_e_resultado(app):
    escolher(app, "conta-de-luz")
    botao(app, "Analisar").click().run()
    botao(app, "Limpar").click().run()
    assert app.text_area(key="texto").value == ""
    assert app.button_group(key="exemplo_escolhido").value is None
    assert 'class="gn-veredito' not in html(app)


def test_nenhum_emoji_na_tela(app):
    escolher(app, "taxa-correios")
    botao(app, "Analisar").click().run()
    textos = [html(app), *(m.value for m in app.markdown), *(c.value for c in app.caption)]
    textos += [b.label for b in app.button]
    assert not any(EMOJI.search(t) for t in textos)


# --- Chave do Gemini na barra lateral ---------------------------------------


@pytest.fixture
def chave_recebida(monkeypatch):
    """Troca a análise por uma que só anota a chave recebida (nenhuma chamada à API)."""
    recebidas = []
    original = analise.analisar_mensagem

    def falsa(texto="", **kwargs):
        recebidas.append(kwargs.get("chave"))
        return original(texto, **{**kwargs, "chave": None})

    monkeypatch.setattr(analise, "analisar_mensagem", falsa)
    return recebidas


def test_chave_digitada_na_barra_lateral_e_usada(app, chave_recebida):
    app.sidebar.text_input(key="chave_usuario").input("  AIza-chave-do-visitante  ").run()
    assert "IA ligada com a sua chave" in html(app)
    escolher(app, "conta-de-luz")
    botao(app, "Analisar").click().run()
    assert chave_recebida == ["AIza-chave-do-visitante"]


def test_chave_digitada_tem_prioridade_sobre_a_do_servidor(monkeypatch, chave_recebida):
    monkeypatch.setenv("GEMINI_API_KEY", "chave-do-servidor")
    tela = AppTest.from_file(str(APP), default_timeout=30).run()
    assert "IA ligada" in html(tela)
    escolher(tela, "conta-de-luz")
    botao(tela, "Analisar").click().run()
    tela.sidebar.text_input(key="chave_usuario").input("chave-do-visitante").run()
    botao(tela, "Analisar").click().run()
    assert chave_recebida == ["chave-do-servidor", "chave-do-visitante"]


def test_chave_nunca_aparece_na_pagina(app):
    app.sidebar.text_input(key="chave_usuario").input("AIza-segredo-123").run()
    campo = app.sidebar.text_input(key="chave_usuario")
    assert type(campo.proto).Type.Name(campo.proto.type) == "PASSWORD"
    textos = [html(app), *(m.value for m in app.markdown), *(c.value for c in app.caption)]
    assert not any("AIza-segredo-123" in t for t in textos)
