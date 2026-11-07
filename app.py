"""Golpe ou Não? — interface web.

    streamlit run app.py

As chaves vêm das variáveis de ambiente (GEMINI_API_KEY e, opcional,
GOOGLE_SAFE_BROWSING_KEY) ou de .streamlit/secrets.toml. Sem a chave do
Gemini o app continua funcionando, só com as verificações automáticas.
"""

from __future__ import annotations

import os

import streamlit as st

from agente.analise import analisar_mensagem
from agente.modelos import Veredito
from interface.apresentacao import (
    ESTILO_NIVEL,
    EXPLICACAO_FONTE,
    em_markdown,
    escapar,
    linha_do_sinal,
    linhas_boleto,
    linhas_link,
    linhas_pix,
    resumo_sem_rotulo,
    titulo_do_boleto,
    titulo_do_link,
    titulo_do_pix,
)
from interface.exemplos import Exemplo, carregar_exemplos

TIPOS_DE_IMAGEM = ["png", "jpg", "jpeg", "webp"]


def segredo(nome: str) -> str | None:
    """Lê uma chave do ambiente ou do secrets.toml (que pode não existir)."""
    if os.environ.get(nome):
        return os.environ[nome]
    try:
        return st.secrets.get(nome)
    except Exception:  # sem secrets.toml o Streamlit levanta erro ao acessar
        return None


def escolher_exemplo(exemplo: Exemplo) -> None:
    st.session_state.texto = exemplo.texto
    st.session_state.exemplo = exemplo.id if exemplo.imagem else None
    st.session_state.veredito = None


def limpar() -> None:
    st.session_state.texto = ""
    st.session_state.exemplo = None
    st.session_state.veredito = None
    st.session_state.envio = st.session_state.get("envio", 0) + 1  # recria o campo de upload vazio


def mostrar_tabela(linhas: list[tuple[str, str]]) -> None:
    st.markdown(em_markdown(linhas))


def mostrar_veredito(v: Veredito) -> None:
    tipo, icone = ESTILO_NIVEL[v.nivel]
    getattr(st, tipo)(f"### {v.rotulo}\n{escapar(resumo_sem_rotulo(v.rotulo, v.resumo))}", icon=icone)

    if v.sinais:
        st.subheader("Por quê")
        st.markdown("\n".join(f"- {linha_do_sinal(s.gravidade, s.fonte, s.descricao)}" for s in v.sinais))
        st.caption(EXPLICACAO_FONTE)

    st.subheader("O que fazer")
    st.markdown("\n".join(f"{i}. {escapar(passo)}" for i, passo in enumerate(v.o_que_fazer, start=1)))

    if v.pix or v.boletos or v.links:
        st.subheader("O que os códigos revelam")
        for i, pix in enumerate(v.pix, start=1):
            with st.expander(titulo_do_pix(pix, i), expanded=True):
                mostrar_tabela(linhas_pix(pix))
        for i, boleto in enumerate(v.boletos, start=1):
            with st.expander(titulo_do_boleto(boleto, i), expanded=True):
                mostrar_tabela(linhas_boleto(boleto))
        for i, link in enumerate(v.links, start=1):
            with st.expander(titulo_do_link(link, i), expanded=True):
                mostrar_tabela(linhas_link(link))
                st.caption("O link não foi aberto: a análise usa só o endereço.")

    if v.texto_do_print:
        with st.expander("Texto lido do print"):
            st.text(v.texto_do_print)

    for aviso in v.avisos:
        st.info(aviso, icon="ℹ️")
    if v.usou_ia:
        st.caption("Ferramentas usadas pela IA: " + (", ".join(v.ferramentas_chamadas) or "nenhuma"))


def main() -> None:
    st.set_page_config(page_title="Golpe ou Não?", page_icon="🕵️", layout="centered")
    for chave, inicial in (("texto", ""), ("exemplo", None), ("veredito", None), ("envio", 0)):
        st.session_state.setdefault(chave, inicial)

    exemplos = carregar_exemplos()
    por_id = {e.id: e for e in exemplos}
    chave_gemini = segredo("GEMINI_API_KEY") or segredo("GOOGLE_API_KEY")

    with st.sidebar:
        st.header("Como funciona")
        st.markdown(
            "1. Os códigos Pix, boletos e links são **abertos e conferidos** sem IA: "
            "quem recebe o dinheiro, de qual banco é o boleto, para onde o link leva.\n"
            "2. A IA lê a mensagem (e o print) e procura táticas de manipulação.\n"
            "3. O veredito nunca fica mais leve do que as provas dos códigos."
        )
        if chave_gemini:
            st.success("IA ligada (Gemini)", icon="🤖")
        else:
            st.warning(
                "IA desligada: sem a chave GEMINI_API_KEY, só o texto é analisado e prints não são lidos.",
                icon="🔌",
            )
        st.caption("Nada é guardado. Links nunca são abertos.")

    st.title("🕵️ Golpe ou Não?")
    st.write("Recebeu uma mensagem estranha? Cole o texto ou envie o print e descubra se é golpe.")

    st.markdown("**Experimente um exemplo:**")
    colunas = st.columns(3)
    for i, exemplo in enumerate(exemplos):
        colunas[i % 3].button(
            exemplo.titulo,
            key=f"exemplo-{exemplo.id}",
            help=exemplo.descricao,
            on_click=escolher_exemplo,
            args=(exemplo,),
            width="stretch",
        )

    st.text_area(
        "Texto da mensagem",
        key="texto",
        height=160,
        placeholder="Cole aqui a mensagem do WhatsApp, SMS ou e-mail, com o código Pix, boleto ou link.",
    )
    enviado = st.file_uploader(
        "Ou envie um print da conversa", type=TIPOS_DE_IMAGEM, key=f"print-{st.session_state.envio}"
    )

    imagem, tipo_imagem = None, "image/png"
    if enviado is not None:
        imagem, tipo_imagem = enviado.getvalue(), enviado.type or "image/png"
    elif st.session_state.exemplo in por_id:
        exemplo = por_id[st.session_state.exemplo]
        imagem, tipo_imagem = exemplo.ler_imagem(), exemplo.tipo_imagem
        st.image(imagem, caption=f"Print do exemplo: {exemplo.titulo}", width=320)

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
                    chave=chave_gemini,
                    chave_safe_browsing=segredo("GOOGLE_SAFE_BROWSING_KEY"),
                )

    if st.session_state.veredito is not None:
        st.divider()
        mostrar_veredito(st.session_state.veredito)


main()
