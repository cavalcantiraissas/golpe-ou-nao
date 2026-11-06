import pytest

from agente.__main__ import main


@pytest.fixture(autouse=True)
def sem_chaves(monkeypatch):
    for variavel in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_SAFE_BROWSING_KEY"):
        monkeypatch.delenv(variavel, raising=False)


def test_texto_pelo_argumento(capsys):
    assert main(["Correios: pague a taxa de liberação em http://correios-taxa.top"]) == 0
    saida = capsys.readouterr().out
    assert saida.startswith("== PROVÁVEL GOLPE ==")
    assert "!! O link correios-taxa.top imita Correios" in saida
    assert "[prova]" in saida
    assert "O que fazer:\n  1. Não pague" in saida


def test_mensagem_comum(capsys):
    main(["Chego às 19h para o jantar"])
    assert capsys.readouterr().out.startswith("== SEM SINAIS DE GOLPE ==")


def test_sem_mensagem_mostra_erro(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    with pytest.raises(SystemExit):
        main([])
    assert "Cole o texto" in capsys.readouterr().err
