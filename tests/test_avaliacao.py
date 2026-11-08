import json
from collections import Counter

import pytest

import avaliacao.__main__ as rodada
from agente.cruzamento import levantar_achados
from agente.modelos import Veredito
from avaliacao.conjunto import ARQUIVO, carregar, gerar
from avaliacao.metricas import contar, relatorio

MENSAGENS = carregar()


# --- Conjunto --------------------------------------------------------------


def test_conjunto_tem_150_mensagens_meio_a_meio():
    assert len(MENSAGENS) == 150
    assert Counter(m["classe"] for m in MENSAGENS) == {"golpe": 75, "legitima": 75}


def test_ids_unicos_e_campos_preenchidos():
    assert len({m["id"] for m in MENSAGENS}) == 150
    for m in MENSAGENS:
        assert m["texto"].strip() and m["categoria"]
        assert m["id"].startswith(m["classe"])


def test_arquivo_esta_igual_ao_gerador():
    # Se falhar, rode: python -m avaliacao.conjunto
    assert json.loads(ARQUIVO.read_text(encoding="utf-8")) == gerar()


@pytest.mark.parametrize("m", MENSAGENS, ids=lambda m: m["id"])
def test_codigos_conferem_menos_os_adulterados(m):
    achados = levantar_achados(m["texto"])
    if "000201" in m["texto"]:
        assert achados.pix, "o Pix escrito na mensagem não foi encontrado"
    for pix, _ in achados.pix:
        assert pix.valido == (m["categoria"] != "pix_adulterado")
    for boleto, _ in achados.boletos:
        assert boleto.valido


def test_resultado_sem_ia_gravado_esta_atualizado(monkeypatch):
    # Se falhar depois de mudar regras ou verificadores, rode: python -m avaliacao --sem-ia
    monkeypatch.delenv("GOOGLE_SAFE_BROWSING_KEY", raising=False)
    gravado = json.loads(rodada.SEM_IA.read_text(encoding="utf-8"))
    assert gravado["niveis"] == rodada.niveis_sem_ia(MENSAGENS)


# --- Métricas --------------------------------------------------------------

MINI = [
    {"id": "golpe-001", "classe": "golpe", "categoria": "banco", "texto": "a"},
    {"id": "golpe-002", "classe": "golpe", "categoria": "banco", "texto": "b"},
    {"id": "golpe-003", "classe": "golpe", "categoria": "emprego", "texto": "c"},
    {"id": "legitima-001", "classe": "legitima", "categoria": "x", "texto": "d"},
    {"id": "legitima-002", "classe": "legitima", "categoria": "x", "texto": "e"},
]


def test_contar():
    c = contar(MINI, {
        "golpe-001": "provavel_golpe", "golpe-002": "atencao", "golpe-003": "sem_sinais",
        "legitima-001": "provavel_golpe", "legitima-002": "sem_sinais",
    })
    assert (c["golpes_pegos"], c["golpes_provavel"], c["total_golpes"]) == (2, 1, 3)
    assert (c["alarmes_falsos"], c["legitimas_atencao"], c["total_legitimas"]) == (1, 0, 2)
    assert c["por_categoria"]["banco"] == {"provavel_golpe": 1, "atencao": 1, "sem_sinais": 0}
    assert c["erros"]["golpes_sem_sinais"] == ["golpe-003"]
    assert c["erros"]["legitimas_provavel_golpe"] == ["legitima-001"]


def test_contar_ignora_mensagens_sem_resultado():
    c = contar(MINI, {"golpe-001": "atencao"})
    assert c["avaliadas"] == 1
    assert c["total_legitimas"] == 0


def test_relatorio_tem_tabela_e_erros():
    texto = relatorio(MINI, {"Sem IA": {"niveis": {"golpe-001": "sem_sinais", "legitima-001": "atencao"}}})
    assert "| Sem IA | 0/1 (0%)" in texto
    assert "`golpe-001`" in texto and "`legitima-001`" in texto


# --- Rodada com IA (sem rede) ----------------------------------------------


def _veredito(nivel, usou_ia=True):
    return Veredito(nivel=nivel, resumo="r", usou_ia=usou_ia, avisos=[] if usou_ia else ["Limite atingido."])


def test_rodada_com_ia_grava_e_continua_de_onde_parou(tmp_path, monkeypatch):
    monkeypatch.setattr(rodada, "COM_IA", tmp_path / "com_ia.json")
    monkeypatch.setattr(rodada.time, "sleep", lambda s: None)
    chamadas = []

    def falso(texto, chave, modelo):
        chamadas.append(texto)
        return _veredito("atencao")

    monkeypatch.setattr(rodada, "analisar_mensagem", falso)
    rodada.rodar_com_ia(MINI, "chave", "modelo-x", pausa=0, limite=2)
    assert len(chamadas) == 2
    dados = rodada.rodar_com_ia(MINI, "chave", "modelo-x", pausa=0, limite=None)
    assert len(chamadas) == 5  # as duas primeiras não foram repetidas
    assert set(dados["niveis"]) == {m["id"] for m in MINI}
    assert json.loads((tmp_path / "com_ia.json").read_text())["modelo"] == "modelo-x"


def test_rodada_com_ia_para_depois_de_falhas_seguidas(tmp_path, monkeypatch):
    monkeypatch.setattr(rodada, "COM_IA", tmp_path / "com_ia.json")
    monkeypatch.setattr(rodada.time, "sleep", lambda s: None)
    chamadas = []

    def sem_cota(texto, chave, modelo):
        chamadas.append(texto)
        return _veredito("sem_sinais", usou_ia=False)

    monkeypatch.setattr(rodada, "analisar_mensagem", sem_cota)
    dados = rodada.rodar_com_ia(MINI, "chave", "modelo-x", pausa=0, limite=None)
    assert len(chamadas) == rodada.FALHAS_SEGUIDAS_PARA_PARAR
    assert dados["niveis"] == {}  # falha não vira resultado


def test_rodada_com_ia_recusa_misturar_modelos(tmp_path, monkeypatch):
    arquivo = tmp_path / "com_ia.json"
    arquivo.write_text(json.dumps({"modelo": "outro", "niveis": {}, "ferramentas": {}}))
    monkeypatch.setattr(rodada, "COM_IA", arquivo)
    with pytest.raises(SystemExit):
        rodada.rodar_com_ia(MINI, "chave", "modelo-x", pausa=0, limite=None)
