"""Roda o agente sobre o conjunto de avaliação e grava os resultados.

    python -m avaliacao --sem-ia            # só verificadores e regras, sem chave
    GEMINI_API_KEY=... python -m avaliacao  # com a IA (pode parar e continuar depois)
    python -m avaliacao --relatorio         # só refaz o RESULTADOS.md

A rodada com IA grava cada resposta assim que ela chega. Se a cota gratuita
do Gemini acabar no meio, rode de novo outro dia: as mensagens já avaliadas
são puladas. A consulta ao Safe Browsing fica desligada nas duas rodadas, para
o resultado depender só do código e do modelo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from agente.analise import analisar_mensagem, veredito_sem_ia
from agente.cruzamento import levantar_achados
from agente.gemini import obter_chave, obter_modelo
from avaliacao.conjunto import carregar
from avaliacao.metricas import relatorio

PASTA = Path(__file__).parent
SEM_IA = PASTA / "resultados" / "sem_ia.json"
COM_IA = PASTA / "resultados" / "com_ia.json"
RELATORIO = PASTA / "RESULTADOS.md"
FALHAS_SEGUIDAS_PARA_PARAR = 3


def niveis_sem_ia(mensagens: list[dict]) -> dict[str, str]:
    return {m["id"]: veredito_sem_ia(m["texto"], levantar_achados(m["texto"])).nivel for m in mensagens}


def ler(arquivo: Path) -> dict | None:
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None


def gravar(arquivo: Path, dados: dict) -> None:
    arquivo.parent.mkdir(exist_ok=True)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def rodar_com_ia(mensagens: list[dict], chave: str, modelo: str, pausa: float, limite: int | None) -> dict:
    dados = ler(COM_IA) or {"modelo": modelo, "niveis": {}, "ferramentas": {}}
    if dados["modelo"] != modelo:
        sys.exit(f"{COM_IA} tem resultados do modelo {dados['modelo']}. Apague o arquivo para trocar de modelo.")
    pendentes = [m for m in mensagens if m["id"] not in dados["niveis"]]
    if limite is not None:
        pendentes = pendentes[:limite]
    print(f"{len(dados['niveis'])} já avaliadas, {len(pendentes)} agora, modelo {modelo}.")

    falhas = 0
    for n, m in enumerate(pendentes, start=1):
        v = analisar_mensagem(m["texto"], chave=chave, modelo=modelo)
        if not v.usou_ia:  # cota, rede ou modelo sem resposta: não conta como resultado
            falhas += 1
            print(f"[{n}/{len(pendentes)}] {m['id']}: falhou ({v.avisos[0] if v.avisos else 'sem detalhe'})")
            if falhas >= FALHAS_SEGUIDAS_PARA_PARAR:
                print("Várias falhas seguidas; parando. Rode de novo mais tarde para continuar.")
                break
        else:
            falhas = 0
            dados["niveis"][m["id"]] = v.nivel
            dados["ferramentas"][m["id"]] = v.ferramentas_chamadas
            dados["data"] = date.today().isoformat()
            gravar(COM_IA, dados)
            print(f"[{n}/{len(pendentes)}] {m['id']} ({m['classe']}): {v.nivel}")
        time.sleep(pausa)
    return dados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m avaliacao", description=__doc__.split("\n")[0])
    parser.add_argument("--sem-ia", action="store_true", help="roda só a parte determinística")
    parser.add_argument("--relatorio", action="store_true", help="só regrava o RESULTADOS.md")
    parser.add_argument("--pausa", type=float, default=7.0, help="segundos entre mensagens (padrão: 7)")
    parser.add_argument("--limite", type=int, help="avalia no máximo N mensagens nesta rodada")
    args = parser.parse_args(argv)

    os.environ.pop("GOOGLE_SAFE_BROWSING_KEY", None)
    mensagens = carregar()

    if args.sem_ia:
        gravar(SEM_IA, {"niveis": niveis_sem_ia(mensagens)})
    elif not args.relatorio:
        chave = obter_chave()
        if not chave:
            parser.error("defina GEMINI_API_KEY para a rodada com IA, ou use --sem-ia")
        rodar_com_ia(mensagens, chave, obter_modelo(), args.pausa, args.limite)

    modos = {}
    if (r := ler(SEM_IA)) is not None:
        modos["Sem IA (verificadores e regras)"] = r
    if (r := ler(COM_IA)) is not None:
        faltam = len(mensagens) - len(r["niveis"])
        modos["Com IA" + (f" ({faltam} ainda sem resultado)" if faltam else "")] = r
    RELATORIO.write_text(relatorio(mensagens, modos), encoding="utf-8")
    print(f"Relatório em {RELATORIO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
