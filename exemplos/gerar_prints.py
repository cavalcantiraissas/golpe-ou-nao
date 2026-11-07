"""Gera os prints de exemplo: conversas sintéticas com Pix falso.

Nomes, números e chaves são fictícios. Os códigos Pix têm CRC válido, então o
agente consegue conferir o recebedor depois de ler o print.

Uso (precisa do Pillow e das fontes Arial e Menlo do macOS):

    pip install pillow
    python exemplos/gerar_prints.py
"""

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
MONO = "/System/Library/Fonts/Menlo.ttc"

LARGURA = 720
PASTA = Path(__file__).resolve().parent

PIX_ENEL = (
    "00020126330014br.gov.bcb.pix0111123456789095204000053039865406247.305802BR"
    "5918RODRIGO A FERREIRA6006MANAUS62070503***630488FE"
)
PIX_FILHO = (
    "00020126520014br.gov.bcb.pix0130pagamentos.rapidos77@gmail.com52040000530398654071850.00"
    "5802BR5918WELLINGTON S COSTA6009SAO PAULO62070503***630452C0"
)

FUNDO = (236, 229, 221)
TOPO = (7, 94, 84)
BALAO = (255, 255, 255)


def desenhar(caminho, contato, numero, blocos):
    fonte = ImageFont.truetype(ARIAL, 26)
    fonte_b = ImageFont.truetype(ARIAL_B, 28)
    fonte_p = ImageFont.truetype(ARIAL, 20)
    mono = ImageFont.truetype(MONO, 21)

    # Mede a altura antes de desenhar.
    linhas = []
    for tipo, conteudo in blocos:
        if tipo == "texto":
            for par in conteudo.split("\n"):
                linhas += [("texto", l) for l in (textwrap.wrap(par, 40) or [""])]
        else:
            linhas += [("codigo", conteudo[i : i + 44]) for i in range(0, len(conteudo), 44)]
        linhas.append(("espaco", ""))
    altura_balao = sum(34 if t == "texto" else 28 if t == "codigo" else 14 for t, _ in linhas) + 60
    altura = 120 + 40 + altura_balao + 60

    img = Image.new("RGB", (LARGURA, altura), FUNDO)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, LARGURA, 110], fill=TOPO)
    d.ellipse([24, 22, 90, 88], fill=(200, 200, 200))
    d.text((110, 26), contato, font=fonte_b, fill="white")
    d.text((110, 64), numero, font=fonte_p, fill=(210, 230, 225))

    x0, y0 = 24, 150
    d.rounded_rectangle([x0, y0, LARGURA - 60, y0 + altura_balao], radius=18, fill=BALAO)
    y = y0 + 22
    for tipo, linha in linhas:
        if tipo == "texto":
            d.text((x0 + 22, y), linha, font=fonte, fill=(20, 20, 20))
            y += 34
        elif tipo == "codigo":
            d.text((x0 + 22, y), linha, font=mono, fill=(20, 20, 20))
            y += 28
        else:
            y += 14
    d.text((LARGURA - 140, y0 + altura_balao - 32), "14:32", font=fonte_p, fill=(130, 130, 130))
    img.save(caminho)


if __name__ == "__main__":
    desenhar(
        PASTA / "print-enel.png",
        "Enel Atendimento",
        "+55 92 98431-2207",
        [
            ("texto", "ENEL INFORMA: Prezado cliente, identificamos 2 faturas em atraso no valor de "
                      "R$ 247,30. Seu fornecimento será suspenso HOJE às 18h."),
            ("texto", "Para evitar o corte, pague agora pelo Pix copia e cola abaixo:"),
            ("codigo", PIX_ENEL),
            ("texto", "Após o pagamento, envie o comprovante nesta conversa."),
        ],
    )
    desenhar(
        PASTA / "print-filho.png",
        "+55 11 97720-4419",
        "online",
        [
            ("texto", "Oi mãe, esse é meu número novo, o outro deu problema. Salva aí!"),
            ("texto", "Tô precisando pagar um boleto hoje e meu app tá bloqueado. Consegue fazer esse "
                      "Pix pra mim? Amanhã te devolvo. Não comenta com o pai que ele vai brigar"),
            ("codigo", PIX_FILHO),
        ],
    )
    print("ok")
