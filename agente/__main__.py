"""Uso pelo terminal.

    python -m agente "texto da mensagem"
    python -m agente --imagem print.png
    pbpaste | python -m agente
"""

from __future__ import annotations

import argparse
import mimetypes
import sys
from pathlib import Path

from agente.analise import analisar_mensagem
from agente.modelos import Veredito

MARCADORES = {"alta": "!!", "media": "! ", "baixa": "- ", "info": "> "}


def formatar(v: Veredito) -> str:
    linhas = [f"== {v.rotulo.upper()} ==", "", v.resumo, ""]
    if v.sinais:
        linhas.append("Sinais encontrados:")
        for s in v.sinais:
            origem = {"verificador": "prova", "regra": "texto", "ia": "IA"}[s.fonte]
            linhas.append(f"  {MARCADORES[s.gravidade]} {s.descricao} [{origem}]")
        linhas.append("")
    linhas.append("O que fazer:")
    linhas += [f"  {i}. {passo}" for i, passo in enumerate(v.o_que_fazer, start=1)]
    if v.avisos:
        linhas += ["", *(f"Aviso: {a}" for a in v.avisos)]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agente", description="Diz se uma mensagem parece golpe.")
    parser.add_argument("texto", nargs="?", help="texto da mensagem (ou envie pela entrada padrão)")
    parser.add_argument("--imagem", type=Path, help="print da mensagem (PNG ou JPEG)")
    args = parser.parse_args(argv)

    texto = args.texto
    if texto is None and not sys.stdin.isatty():
        texto = sys.stdin.read()
    imagem = args.imagem.read_bytes() if args.imagem else None
    tipo = (mimetypes.guess_type(args.imagem.name)[0] or "image/png") if args.imagem else "image/png"

    try:
        veredito = analisar_mensagem(texto or "", imagem=imagem, tipo_imagem=tipo)
    except ValueError as erro:
        parser.error(str(erro))
    print(formatar(veredito))
    return 0


if __name__ == "__main__":
    sys.exit(main())
