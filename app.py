"""Golpe ou Não? — interface web.

    streamlit run app.py

A chave do Gemini pode ser digitada na barra lateral (fica só na sessão de
quem está usando) ou vir do servidor: variável de ambiente GEMINI_API_KEY ou
.streamlit/secrets.toml. A chave digitada tem prioridade. Sem nenhuma, o app
continua funcionando só com as verificações automáticas.
"""

from __future__ import annotations

import os

import streamlit as st

from agente.analise import analisar_mensagem
from agente.modelos import Veredito
from interface.apresentacao import (
    ESTILO,
    html_avisos,
    html_cabecalho,
    html_cartoes,
    html_passos,
    html_secao,
    html_sinais,
    html_veredito,
)
from interface.exemplos import Exemplo, carregar_exemplos

TIPOS_DE_IMAGEM = ["png", "jpg", "jpeg", "webp"]
LINK_CHAVE = "https://aistudio.google.com/apikey"


def segredo(nome: str) -> str | None:
    """Lê uma chave do ambiente ou do secrets.toml (que pode não existir)."""
    if os.environ.get(nome):
        return os.environ[nome]
    try:
        return st.secrets.get(nome)
    except Exception:  # sem secrets.toml o Streamlit levanta erro ao acessar
        return None


def escolher_exemplo(por_id: dict[str, Exemplo]) -> None:
    exemplo = por_id.get(st.session_state.exemplo_escolhido or "")
    if exemplo is None:  # clicou de novo no exemplo já marcado
        return
    st.session_state.texto = exemplo.texto
    st.session_state.exemplo = exemplo.id if exemplo.imagem else None
    st.session_state.veredito = None


def limpar() -> None:
    st.session_state.texto = ""
    st.session_state.exemplo = None
    st.session_state.exemplo_escolhido = None
    st.session_state.veredito = None
    st.session_state.envio += 1  # recria o campo de upload vazio


def barra_lateral(chave_servidor: str | None) -> str | None:
    """Desenha a barra lateral e devolve a chave do Gemini que vai ser usada."""
    with st.sidebar:
        st.subheader("Chave do Gemini")
        st.text_input(
            "Sua chave da API",
            key="chave_usuario",
            type="password",
            placeholder="Cole aqui a sua chave",
            help="Com a chave, a IA lê prints e explica o veredito. Sem ela, só as verificações automáticas rodam.",
        )
        st.caption(
            f"Crie uma chave gratuita no [Google AI Studio]({LINK_CHAVE}). "
            "Ela é usada só nesta sessão e não fica salva."
        )
        chave_usuario = st.session_state.chave_usuario.strip()
        if chave_usuario:
            st.html('<p class="gn-status gn-status-on">IA ligada com a sua chave</p>')
        elif chave_servidor:
            st.html('<p class="gn-status gn-status-on">IA ligada</p>')
        else:
            st.html(
                '<p class="gn-status gn-status-off">IA desligada</p>'
                '<p class="gn-status-ajuda">Sem chave, o texto colado é analisado normalmente, '
                "mas prints não podem ser lidos.</p>"
            )

        st.divider()
        st.subheader("Como funciona")
        st.markdown(
            "1. Códigos Pix, boletos e links são **abertos e conferidos** sem IA: quem recebe o dinheiro, "
            "de qual banco é o boleto, para onde o link leva.\n"
            "2. A IA lê a mensagem e o print e procura táticas de manipulação.\n"
            "3. O veredito nunca fica mais leve do que as provas dos códigos."
        )
        st.caption("Nenhuma mensagem é guardada. Links nunca são abertos.")
    return chave_usuario or chave_servidor


def mostrar_veredito(v: Veredito) -> None:
    partes = [html_veredito(v)]
    if v.sinais:
        partes += [html_secao("Por quê"), html_sinais(v.sinais)]
    partes += [html_secao("O que fazer"), html_passos(v.o_que_fazer)]
    if v.pix or v.boletos or v.links:
        partes += [html_secao("O que os códigos revelam"), html_cartoes(v)]
    partes.append(html_avisos(v.avisos))
    st.html("".join(partes))

    if v.texto_do_print:
        with st.expander("Texto lido do print"):
            st.text(v.texto_do_print)
    if v.usou_ia and v.ferramentas_chamadas:
        st.caption("Ferramentas usadas pela IA: " + ", ".join(v.ferramentas_chamadas))


def main() -> None:
    st.set_page_config(page_title="Golpe ou Não?", layout="centered")
    for nome, inicial in (
        ("texto", ""),
        ("exemplo", None),
        ("exemplo_escolhido", None),
        ("veredito", None),
        ("envio", 0),
        ("chave_usuario", ""),
    ):
        st.session_state.setdefault(nome, inicial)
    st.html(ESTILO)

    exemplos = carregar_exemplos()
    por_id = {e.id: e for e in exemplos}
    chave = barra_lateral(segredo("GEMINI_API_KEY") or segredo("GOOGLE_API_KEY"))

    st.html(html_cabecalho())

    st.pills(
        "Experimente um exemplo",
        options=list(por_id),
        format_func=lambda i: por_id[i].titulo,
        key="exemplo_escolhido",
        on_change=escolher_exemplo,
        args=(por_id,),
    )

    st.text_area(
        "Texto da mensagem",
        key="texto",
        height=150,
        placeholder="Cole aqui a mensagem do WhatsApp, SMS ou e-mail, com o código Pix, o boleto ou o link.",
    )
    st.caption("Com a IA ligada, a mensagem é enviada ao Google. Apague dados pessoais antes de colar.")
    enviado = st.file_uploader(
        "Ou envie um print da conversa", type=TIPOS_DE_IMAGEM, key=f"print-{st.session_state.envio}"
    )

    imagem, tipo_imagem = None, "image/png"
    if enviado is not None:
        imagem, tipo_imagem = enviado.getvalue(), enviado.type or "image/png"
    elif st.session_state.exemplo in por_id:
        exemplo = por_id[st.session_state.exemplo]
        imagem, tipo_imagem = exemplo.ler_imagem(), exemplo.tipo_imagem
        st.image(imagem, caption=f"Print do exemplo: {exemplo.titulo}", width=300)

    col_analisar, col_limpar, _ = st.columns([1, 1, 2])
    clicou = col_analisar.button("Analisar", type="primary", width="stretch")
    col_limpar.button("Limpar", on_click=limpar, width="stretch")

    if clicou:
        if not st.session_state.texto.strip() and imagem is None:
            st.warning("Cole o texto da mensagem ou envie um print.")
        else:
            with st.spinner("Conferindo os códigos e lendo a mensagem..."):
                st.session_state.veredito = analisar_mensagem(
                    st.session_state.texto,
                    imagem=imagem,
                    tipo_imagem=tipo_imagem,
                    chave=chave,
                    chave_safe_browsing=segredo("GOOGLE_SAFE_BROWSING_KEY"),
                )

    if st.session_state.veredito is not None:
        st.divider()
        mostrar_veredito(st.session_state.veredito)

    st.html(
        '<p class="gn-rodape">Golpe ou Não? é um projeto de estudo. Na dúvida, não pague e confirme '
        "pelo aplicativo oficial do banco ou da empresa.</p>"
    )


main()
