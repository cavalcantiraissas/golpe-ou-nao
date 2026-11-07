import ast

import pytest

from agente.analise import analisar_mensagem
from interface.exemplos import PASTA_EXEMPLOS, carregar_exemplos
from verificadores import decodificar_pix, extrair_pix

EXEMPLOS = carregar_exemplos()
DE_TEXTO = [e for e in EXEMPLOS if e.texto]
DE_PRINT = [e for e in EXEMPLOS if e.imagem]


@pytest.fixture(autouse=True)
def sem_chaves(monkeypatch):
    for variavel in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_SAFE_BROWSING_KEY"):
        monkeypatch.delenv(variavel, raising=False)


def test_ids_sao_unicos():
    ids = [e.id for e in EXEMPLOS]
    assert len(ids) == len(set(ids))


def test_tem_golpes_e_mensagens_legitimas():
    niveis = {e.nivel_esperado for e in EXEMPLOS}
    assert {"provavel_golpe", "sem_sinais"} <= niveis


@pytest.mark.parametrize("exemplo", DE_TEXTO, ids=lambda e: e.id)
def test_exemplo_de_texto_da_o_nivel_esperado_sem_ia(exemplo):
    # Sem IA, só as provas e as regras decidem: os exemplos não dependem do Gemini.
    assert analisar_mensagem(exemplo.texto).nivel == exemplo.nivel_esperado


@pytest.mark.parametrize("exemplo", DE_PRINT, ids=lambda e: e.id)
def test_print_do_exemplo_existe_e_e_png(exemplo):
    assert exemplo.caminho_imagem.exists()
    assert exemplo.tipo_imagem == "image/png"
    assert exemplo.ler_imagem().startswith(b"\x89PNG")


def test_pix_desenhados_nos_prints_sao_validos():
    # Lê as constantes do gerador sem importá-lo (ele precisa do Pillow, que não é dependência do projeto).
    arvore = ast.parse((PASTA_EXEMPLOS / "gerar_prints.py").read_text(encoding="utf-8"))
    codigos = {
        alvo.id: ast.literal_eval(no.value)
        for no in arvore.body
        if isinstance(no, ast.Assign)
        for alvo in no.targets
        if isinstance(alvo, ast.Name) and alvo.id.startswith("PIX_")
    }
    assert set(codigos) == {"PIX_ENEL", "PIX_FILHO"}
    assert all(decodificar_pix(c).valido for c in codigos.values())


def test_pix_adulterado_do_exemplo_falha_na_conferencia():
    exemplo = next(e for e in EXEMPLOS if e.id == "pix-alterado")
    (codigo,) = extrair_pix(exemplo.texto)
    assert not decodificar_pix(codigo).crc_ok
