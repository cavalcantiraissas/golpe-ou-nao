"""Como cada parte do veredito aparece na tela.

Funções puras (sem Streamlit) para poderem ser testadas. Os blocos do
resultado são HTML próprio, desenhado com o CSS de ``ESTILO``. Todo texto que
vem da mensagem, dos códigos ou da IA passa por ``html.escape``: um golpista
não consegue injetar link, imagem ou formatação no veredito.
"""

from __future__ import annotations

from html import escape

from agente.cruzamento import reais
from agente.modelos import Fonte, Gravidade, Nivel, Sinal, Veredito
from verificadores.modelos import ResultadoBoleto, ResultadoLink, ResultadoPix

ROTULO_GRAVIDADE: dict[Gravidade, str] = {"alta": "Grave", "media": "Suspeito", "baixa": "Leve", "info": "Informação"}

ROTULO_FONTE: dict[Fonte, str] = {
    "verificador": "Prova",
    "regra": "Padrão de golpe",
    "ia": "Análise da IA",
}

EXPLICACAO_FONTE: dict[Fonte, str] = {
    "verificador": "conferido dentro do código Pix, do boleto ou do link",
    "regra": "frase típica de golpes conhecidos",
    "ia": "interpretação do modelo",
}

ROTULO_RECEBEDOR = {"pessoa_fisica": "Pessoa física", "pessoa_juridica": "Empresa", "indefinido": "Não dá para saber"}

ROTULO_CHAVE = {
    "cpf": "CPF",
    "cnpj": "CNPJ",
    "telefone": "Telefone",
    "email": "E-mail",
    "aleatoria": "Chave aleatória",
    "desconhecida": "Desconhecida",
}

ROTULO_SAFE_BROWSING = {
    "nao_consultado": "Não consultado",
    "limpo": "Nenhum alerta",
    "perigoso": "Marcado como perigoso",
    "erro": "Não foi possível consultar",
}

CONFERE = "Confere"
NAO_CONFERE = "Não confere"


# --- Linhas dos cartões de prova -------------------------------------------


def _conferencia(valido: bool) -> str:
    return CONFERE if valido else NAO_CONFERE


def linhas_pix(pix: ResultadoPix) -> list[tuple[str, str]]:
    linhas = [("Quem recebe", pix.nome_recebedor or "—")]
    linhas.append(("Tipo", ROTULO_RECEBEDOR[pix.tipo_recebedor]))
    if pix.cidade:
        linhas.append(("Cidade", pix.cidade.title()))
    linhas.append(("Valor", reais(pix.valor) if pix.valor is not None else "Em aberto"))
    if pix.chave:
        linhas.append((f"Chave ({ROTULO_CHAVE[pix.tipo_chave]})", pix.chave))
    if pix.url_cobranca:
        linhas.append(("Cobrança dinâmica", pix.url_cobranca))
    linhas.append(("Conferência do código", _conferencia(pix.valido)))
    return linhas


def linhas_boleto(boleto: ResultadoBoleto) -> list[tuple[str, str]]:
    if boleto.tipo == "arrecadacao":
        linhas = [("Tipo", "Conta de consumo ou tributo"), ("Segmento", boleto.segmento or "—")]
    else:
        banco = f"{boleto.nome_banco} ({boleto.codigo_banco})" if boleto.nome_banco else boleto.codigo_banco or "—"
        linhas = [("Tipo", "Boleto bancário"), ("Banco", banco)]
    linhas.append(("Valor", reais(boleto.valor) if boleto.valor is not None else "Em aberto"))
    if boleto.vencimento:
        linhas.append(("Vencimento", f"{boleto.vencimento:%d/%m/%Y}"))
    linhas.append(("Dígitos verificadores", _conferencia(boleto.valido)))
    return linhas


def linhas_link(link: ResultadoLink) -> list[tuple[str, str]]:
    linhas = [("Endereço do site", link.dominio or link.host or link.url)]
    if link.marca_imitada:
        linhas.append(("Imita", link.marca_imitada))
    linhas.append(("Cadeado (HTTPS)", "Sim" if link.https else "Não"))
    if link.encurtador:
        linhas.append(("Encurtador", "Sim, esconde o destino real"))
    linhas.append(("Lista de sites perigosos do Google", ROTULO_SAFE_BROWSING[link.safe_browsing]))
    return linhas


def titulo_do_pix(pix: ResultadoPix, indice: int) -> str:
    return f"Pix {indice}: {pix.nome_recebedor}" if pix.nome_recebedor else f"Pix {indice}"


def titulo_do_boleto(boleto: ResultadoBoleto, indice: int) -> str:
    return f"Boleto {indice}: {boleto.nome_banco or boleto.segmento or 'não identificado'}"


def titulo_do_link(link: ResultadoLink, indice: int) -> str:
    return f"Link {indice}: {link.dominio or link.host or link.url}"


def resumo_sem_rotulo(rotulo: str, resumo: str) -> str:
    """Tira o rótulo do começo do resumo, já que ele aparece no título do veredito."""
    if resumo.lower().startswith(rotulo.lower()):
        return resumo[len(rotulo) :].lstrip(" .:").strip() or resumo
    return resumo


# --- Blocos em HTML ---------------------------------------------------------


def html_veredito(v: Veredito) -> str:
    resumo = escape(resumo_sem_rotulo(v.rotulo, v.resumo))
    marca = f'<p class="gn-marca">Diz ser: {escape(v.marca_alegada)}</p>' if v.marca_alegada else ""
    return (
        f'<div class="gn-veredito gn-{v.nivel}">'
        f'<p class="gn-nivel">{escape(v.rotulo)}</p>'
        f'<p class="gn-resumo">{resumo}</p>{marca}</div>'
    )


def html_sinais(sinais: list[Sinal]) -> str:
    itens = "".join(
        f'<li class="gn-sinal gn-{s.gravidade}">'
        f'<span class="gn-gravidade">{ROTULO_GRAVIDADE[s.gravidade]}</span>'
        f'<span class="gn-descricao">{escape(s.descricao)}</span>'
        f'<span class="gn-fonte gn-fonte-{s.fonte}">{ROTULO_FONTE[s.fonte]}</span></li>'
        for s in sinais
    )
    fontes = sorted({s.fonte for s in sinais}, key=list(ROTULO_FONTE).index)
    legenda = " · ".join(f"<b>{ROTULO_FONTE[f]}</b>: {EXPLICACAO_FONTE[f]}" for f in fontes)
    return f'<ul class="gn-sinais">{itens}</ul><p class="gn-legenda">{legenda}</p>'


def html_passos(passos: list[str]) -> str:
    return '<ol class="gn-passos">' + "".join(f"<li>{escape(p)}</li>" for p in passos) + "</ol>"


def html_cartao(titulo: str, linhas: list[tuple[str, str]], nota: str | None = None) -> str:
    celulas = []
    for rotulo, valor in linhas:
        classe = ""
        if valor == CONFERE:
            classe = ' class="gn-ok"'
        elif valor == NAO_CONFERE:
            classe = ' class="gn-falha"'
        celulas.append(f"<dt>{escape(rotulo)}</dt><dd><span{classe}>{escape(valor)}</span></dd>")
    rodape = f'<p class="gn-nota">{escape(nota)}</p>' if nota else ""
    return f'<div class="gn-cartao"><p class="gn-cartao-titulo">{escape(titulo)}</p><dl>{"".join(celulas)}</dl>{rodape}</div>'


def html_cartoes(v: Veredito) -> str:
    cartoes = [html_cartao(titulo_do_pix(p, i), linhas_pix(p)) for i, p in enumerate(v.pix, start=1)]
    cartoes += [html_cartao(titulo_do_boleto(b, i), linhas_boleto(b)) for i, b in enumerate(v.boletos, start=1)]
    cartoes += [
        html_cartao(titulo_do_link(l, i), linhas_link(l), "O link não foi aberto: a análise usa só o endereço.")
        for i, l in enumerate(v.links, start=1)
    ]
    return '<div class="gn-cartoes">' + "".join(cartoes) + "</div>"


def html_avisos(avisos: list[str]) -> str:
    return "".join(f'<p class="gn-aviso">{escape(a)}</p>' for a in avisos)


def html_secao(titulo: str) -> str:
    return f'<p class="gn-secao">{escape(titulo)}</p>'


def html_cabecalho() -> str:
    return (
        '<div class="gn-cabecalho">'
        '<p class="gn-sobretitulo">Verificador de mensagens suspeitas</p>'
        '<h1 class="gn-titulo">Golpe ou Não?</h1>'
        '<p class="gn-subtitulo">Cole a mensagem ou envie o print. O sistema abre os códigos Pix, '
        "boletos e links para mostrar para quem o dinheiro iria de verdade.</p></div>"
    )


ESTILO = """
<style>
:root {
  --gn-tinta: #1d2433;
  --gn-suave: #5b6475;
  --gn-linha: #e3e6ec;
  --gn-fundo: #f6f7f9;
  --gn-marca: #0b6e4f;
  --gn-golpe: #b42318;   --gn-golpe-fundo: #fef3f2;
  --gn-atencao: #a15c07; --gn-atencao-fundo: #fffaeb;
  --gn-ok: #067647;      --gn-ok-fundo: #ecfdf3;
  --gn-info: #475467;
}
.block-container { padding-top: 2.5rem; max-width: 760px; }
.gn-cabecalho { margin-bottom: .5rem; }
.gn-sobretitulo { color: var(--gn-marca); font-size: .78rem; font-weight: 600; letter-spacing: .08em;
  text-transform: uppercase; margin: 0 0 .25rem; }
.gn-titulo { color: var(--gn-tinta); font-size: 2.4rem; font-weight: 700; letter-spacing: -.02em;
  margin: 0; padding: 0; line-height: 1.1; }
.gn-subtitulo { color: var(--gn-suave); font-size: 1.02rem; line-height: 1.5; margin: .6rem 0 0; }
.gn-secao { color: var(--gn-suave); font-size: .78rem; font-weight: 600; letter-spacing: .08em;
  text-transform: uppercase; margin: 1.6rem 0 .6rem; }

.gn-veredito { border-left: 5px solid; border-radius: 8px; padding: 1.1rem 1.3rem; }
.gn-veredito p { margin: 0; }
.gn-nivel { font-size: .8rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.gn-resumo { color: var(--gn-tinta); font-size: 1.12rem; line-height: 1.5; margin-top: .35rem !important; }
.gn-marca { color: var(--gn-suave); font-size: .88rem; margin-top: .5rem !important; }
.gn-provavel_golpe { border-color: var(--gn-golpe); background: var(--gn-golpe-fundo); }
.gn-provavel_golpe .gn-nivel { color: var(--gn-golpe); }
.gn-atencao { border-color: var(--gn-atencao); background: var(--gn-atencao-fundo); }
.gn-atencao .gn-nivel { color: var(--gn-atencao); }
.gn-sem_sinais { border-color: var(--gn-ok); background: var(--gn-ok-fundo); }
.gn-sem_sinais .gn-nivel { color: var(--gn-ok); }

.gn-sinais { list-style: none; margin: 0; padding: 0; border: 1px solid var(--gn-linha); border-radius: 8px; }
.gn-sinal { display: grid; grid-template-columns: 6.5rem 1fr auto; gap: .75rem; align-items: baseline;
  padding: .7rem .9rem; border-top: 1px solid var(--gn-linha); margin: 0; }
.gn-sinal:first-child { border-top: none; }
.gn-sinais, .gn-sinal, .gn-cartao dl, .gn-cartao dt, .gn-cartao dd { margin-left: 0 !important; padding-left: 0 !important; }
.gn-sinal { padding-left: .9rem !important; }
.gn-gravidade { font-size: .74rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.gn-alta .gn-gravidade { color: var(--gn-golpe); }
.gn-media .gn-gravidade { color: var(--gn-atencao); }
.gn-baixa .gn-gravidade, .gn-info .gn-gravidade { color: var(--gn-info); }
.gn-descricao { color: var(--gn-tinta); line-height: 1.45; }
.gn-fonte { font-size: .72rem; color: var(--gn-suave); border: 1px solid var(--gn-linha); border-radius: 999px;
  padding: .1rem .55rem; white-space: nowrap; }
.gn-fonte-verificador { color: var(--gn-marca); border-color: #b7dccd; background: #f0f8f4; }
.gn-legenda { color: var(--gn-suave); font-size: .8rem; margin: .5rem 0 0; }

.gn-passos { margin: 0; padding-left: 1.3rem; color: var(--gn-tinta); }
.gn-passos li { margin: .35rem 0; line-height: 1.5; }

.gn-cartoes { display: grid; gap: .8rem; }
.gn-cartao { border: 1px solid var(--gn-linha); border-radius: 8px; padding: .9rem 1.1rem; background: #fff; }
.gn-cartao-titulo { color: var(--gn-tinta); font-weight: 600; margin: 0 0 .6rem; }
.gn-cartao dl { display: grid; grid-template-columns: minmax(9rem, 40%) 1fr; gap: .35rem 1rem; margin: 0; }
.gn-cartao dt { color: var(--gn-suave); font-size: .9rem; }
.gn-cartao dd { color: var(--gn-tinta); margin: 0; overflow-wrap: anywhere; }
.gn-ok, .gn-falha { font-size: .82rem; font-weight: 600; border-radius: 999px; padding: .1rem .6rem; }
.gn-ok { color: var(--gn-ok); background: var(--gn-ok-fundo); }
.gn-falha { color: var(--gn-golpe); background: var(--gn-golpe-fundo); }
.gn-nota { color: var(--gn-suave); font-size: .8rem; margin: .6rem 0 0; }

.gn-aviso { color: var(--gn-suave); font-size: .88rem; background: var(--gn-fundo); border-radius: 8px;
  padding: .6rem .9rem; margin: .8rem 0 0; }
.gn-status { display: inline-flex; align-items: center; gap: .45rem; font-size: .88rem; font-weight: 600;
  margin: .2rem 0 0; }
.gn-status::before { content: ""; width: .55rem; height: .55rem; border-radius: 50%; }
.gn-status-on { color: var(--gn-ok); }
.gn-status-on::before { background: var(--gn-ok); }
.gn-status-off { color: var(--gn-suave); }
.gn-status-off::before { background: #98a2b3; }
.gn-status-ajuda { color: var(--gn-suave); font-size: .82rem; line-height: 1.45; margin: .3rem 0 0; }
.gn-rodape { color: var(--gn-suave); font-size: .8rem; margin-top: 2.5rem; border-top: 1px solid var(--gn-linha);
  padding-top: .8rem; }

@media (max-width: 640px) {
  .gn-titulo { font-size: 1.9rem; }
  .gn-sinal { grid-template-columns: 1fr; gap: .25rem; }
  .gn-fonte { justify-self: start; }
  .gn-cartao dl { grid-template-columns: 1fr; gap: .1rem; }
  .gn-cartao dd { margin-bottom: .45rem; }
}
</style>
"""
