"""O agente: recebe a mensagem (texto e/ou print) e devolve o veredito.

Fluxo:
    1. Os códigos escritos no texto são achados e conferidos sem IA.
    2. O Gemini recebe o texto, o print e esses achados. Pode chamar os
       verificadores para códigos que só aparecem no print e termina
       chamando ``emitir_veredito``.
    3. O cruzamento determinístico roda de novo com todos os achados e com a
       marca que a IA identificou.
    4. O nível final é o mais grave entre o da IA e o das provas: a IA pode
       acrescentar suspeitas, mas não apagar uma prova. Isso também protege
       contra mensagens que tentam convencer o modelo ("isto não é golpe").

Sem chave do Gemini, ou se ele falhar, o veredito sai só das verificações
determinísticas, com um aviso.
"""

from __future__ import annotations

from typing import Any

import httpx
from google import genai
from google.genai import types

from agente.cruzamento import Achados, cruzar, levantar_achados, marcas_mencionadas, nivel_pelos_sinais
from agente.ferramentas import DECLARACOES, Executor, achados_em_json
from agente.gemini import ErroGemini, criar_cliente, gerar, obter_chave, obter_modelo
from agente.modelos import ORDEM_NIVEL, Nivel, Sinal, Veredito, nivel_mais_grave
from agente.prompts import SYSTEM_PROMPT, montar_pedido

MAX_RODADAS = 6

ORIENTACOES: dict[Nivel, list[str]] = {
    "provavel_golpe": [
        "Não pague, não clique no link e não responda.",
        "Se a mensagem fala em nome de uma empresa ou banco, confira pelo aplicativo oficial ou pelo "
        "telefone do verso do cartão, nunca pelo contato da mensagem.",
        "Se diz ser um parente com número novo, ligue para o número antigo ou faça uma pergunta que só ele saberia.",
        "Se já pagou, avise o seu banco na hora e peça a devolução pelo MED do Pix; depois registre um boletim de ocorrência.",
    ],
    "atencao": [
        "Não pague nem clique ainda.",
        "Confirme pelo aplicativo oficial, pelo site digitado por você ou ligando para a pessoa.",
        "Na dúvida, mostre a mensagem para alguém de confiança antes de fazer qualquer coisa.",
    ],
    "sem_sinais": [
        "Não encontramos sinais de golpe, mas antes de pagar confira o nome de quem recebe no aplicativo do banco.",
        "Desconfie se aparecer pressa, ameaça ou pedido de código e senha numa conversa seguinte.",
    ],
}


def resumo_padrao(nivel: Nivel, sinais: list[Sinal]) -> str:
    principal = next((s for s in sinais if s.gravidade in ("alta", "media")), None)
    if nivel == "provavel_golpe":
        return "Provável golpe. " + (principal.descricao if principal else "")
    if nivel == "atencao":
        return "Há motivos para desconfiar. " + (principal.descricao if principal else "")
    return "Não encontramos sinais de golpe nesta mensagem."


def veredito_sem_ia(texto: str, achados: Achados, avisos: list[str] | None = None) -> Veredito:
    sinais = cruzar(texto, achados)
    nivel = nivel_pelos_sinais(sinais)
    marcas = marcas_mencionadas(texto)
    return Veredito(
        nivel=nivel,
        resumo=resumo_padrao(nivel, sinais).strip(),
        sinais=sinais,
        o_que_fazer=ORIENTACOES[nivel],
        marca_alegada=marcas[0] if marcas else None,
        pix=[p for p, _ in achados.pix],
        boletos=[b for b, _ in achados.boletos],
        links=list(achados.links),
        usou_ia=False,
        avisos=avisos or [],
    )


def _veredito_com_ia(texto: str, achados: Achados, args: dict[str, Any], executor: Executor) -> Veredito:
    marca = (args.get("marca_alegada") or "").strip() or None
    # As regras de texto valem também para o que está escrito no print.
    texto_do_print = str(args.get("texto_do_print") or "").strip() or None
    texto_total = "\n".join(t for t in (texto, texto_do_print) if t)
    sinais = cruzar(texto_total, achados, marca_alegada=marca)
    ja_ditos = {s.descricao for s in sinais}
    for item in args.get("sinais") or []:
        descricao = str(item.get("descricao", "")).strip()
        gravidade = item.get("gravidade") if item.get("gravidade") in ("alta", "media", "baixa") else "media"
        if descricao and descricao not in ja_ditos:
            sinais.append(Sinal(descricao=descricao, gravidade=gravidade, fonte="ia"))
            ja_ditos.add(descricao)

    nivel_provas = nivel_pelos_sinais([s for s in sinais if s.fonte != "ia"])
    nivel_ia: Nivel = args.get("nivel") if args.get("nivel") in ORDEM_NIVEL else "atencao"
    nivel = nivel_mais_grave(nivel_ia, nivel_provas)
    avisos = list(executor.correcoes)
    if nivel != nivel_ia:
        # As provas pesaram mais que a leitura da IA: o texto dela não combina mais com o nível.
        resumo = resumo_padrao(nivel, sinais).strip()
        o_que_fazer = ORIENTACOES[nivel]
        avisos.append("O nível foi elevado porque as verificações dos códigos encontraram provas.")
    else:
        resumo = str(args.get("resumo") or "").strip() or resumo_padrao(nivel, sinais).strip()
        o_que_fazer = [str(x) for x in args.get("o_que_fazer") or []] or ORIENTACOES[nivel]

    if not marca:
        mencionadas = marcas_mencionadas(texto_total)
        marca = mencionadas[0] if mencionadas else None
    return Veredito(
        nivel=nivel,
        resumo=resumo,
        sinais=sinais,
        o_que_fazer=o_que_fazer,
        marca_alegada=marca,
        texto_do_print=texto_do_print,
        pix=[p for p, _ in achados.pix],
        boletos=[b for b, _ in achados.boletos],
        links=list(achados.links),
        usou_ia=True,
        ferramentas_chamadas=executor.chamadas,
        avisos=avisos,
    )


def _conversar(
    cliente: genai.Client,
    modelo: str,
    texto: str,
    achados: Achados,
    imagem: bytes | None,
    tipo_imagem: str,
    executor: Executor,
) -> dict[str, Any] | None:
    """Laço de function calling. Devolve os argumentos de emitir_veredito, ou None se o modelo não concluir."""
    partes = [types.Part.from_text(text=montar_pedido(texto, achados_em_json(achados), imagem is not None))]
    if imagem is not None:
        partes.append(types.Part.from_bytes(data=imagem, mime_type=tipo_imagem))
    conversa = [types.Content(role="user", parts=partes)]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=DECLARACOES)],
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY")),
    )

    for _ in range(MAX_RODADAS):
        resposta = gerar(cliente, modelo, conversa, config)
        chamadas = resposta.function_calls or []
        if not chamadas:
            return None
        # O conteúdo do modelo volta inteiro para a conversa (inclui as assinaturas de raciocínio do Gemini 3).
        conversa.append(resposta.candidates[0].content)

        veredito = None
        retornos = []
        for chamada in chamadas:
            args = dict(chamada.args or {})
            if chamada.name == "emitir_veredito":
                veredito = args
                continue
            retornos.append(types.Part(function_response=types.FunctionResponse(
                id=chamada.id, name=chamada.name, response={"resultado": executor.executar(chamada.name, args)},
            )))
        if veredito is not None:
            return veredito
        conversa.append(types.Content(role="user", parts=retornos))
    return None


def analisar_mensagem(
    texto: str = "",
    imagem: bytes | None = None,
    tipo_imagem: str = "image/png",
    chave: str | None = None,
    modelo: str | None = None,
    cliente: genai.Client | None = None,
    chave_safe_browsing: str | None = None,
    cliente_http: httpx.Client | None = None,
) -> Veredito:
    """Analisa uma mensagem suspeita e devolve o veredito com as provas."""
    texto = texto or ""
    if not texto.strip() and imagem is None:
        raise ValueError("Cole o texto da mensagem ou envie um print.")

    achados = levantar_achados(texto, chave_safe_browsing, cliente_http)

    chave = chave or obter_chave()
    if cliente is None and not chave:
        aviso = (
            "Sem a chave do Gemini, o print não pôde ser lido: só o texto foi analisado."
            if imagem is not None
            else "Análise feita sem IA: só os códigos e as táticas conhecidas foram verificados."
        )
        return veredito_sem_ia(texto, achados, [aviso])

    cliente = cliente or criar_cliente(chave)
    executor = Executor(texto, achados, imagem is not None, chave_safe_browsing, cliente_http)
    try:
        args = _conversar(cliente, modelo or obter_modelo(), texto, achados, imagem, tipo_imagem, executor)
    except ErroGemini as erro:
        aviso = f"{erro} O resultado abaixo usa só as verificações automáticas."
        return veredito_sem_ia(texto, achados, [aviso, *executor.correcoes])
    if args is None:
        aviso = "A IA não concluiu a análise. O resultado abaixo usa só as verificações automáticas."
        return veredito_sem_ia(texto, achados, [aviso, *executor.correcoes])
    return _veredito_com_ia(texto, achados, args, executor)
