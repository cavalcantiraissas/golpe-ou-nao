"""Ferramentas oferecidas ao Gemini por function calling.

Três são os verificadores determinísticos. A quarta, ``emitir_veredito``,
é como o modelo entrega a resposta final: com o modo de chamada "ANY", ele
sempre responde chamando uma função, o que garante uma saída estruturada
mesmo depois de usar as outras ferramentas.

O executor registra a origem de cada código: se o texto colado contém o
código, ele veio do texto; se não, foi transcrito do print pela IA, e uma
falha na conferência pode ser só erro de leitura.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from google.genai import types

from agente.cruzamento import Achados, Origem
from verificadores import analisar_link, decodificar_pix, validar_boleto
from verificadores.pix import corrigir_leitura_pix

DECLARACOES = [
    types.FunctionDeclaration(
        name="decodificar_pix",
        description=(
            "Abre um código Pix copia e cola (começa com 000201) e devolve o nome e a cidade de quem "
            "recebe, o valor, o tipo da chave e se o código passa na conferência (CRC). Use para cada "
            "código Pix que aparecer no print e ainda não estiver nos achados."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "codigo": {
                    "type": "string",
                    "description": "O código completo, transcrito exatamente, caractere por caractere.",
                }
            },
            "required": ["codigo"],
        },
    ),
    types.FunctionDeclaration(
        name="validar_boleto",
        description=(
            "Confere os dígitos verificadores da linha digitável de um boleto (47 ou 48 números) e "
            "devolve o banco ou o tipo de conta, o valor e o vencimento."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "linha_digitavel": {
                    "type": "string",
                    "description": "A linha digitável completa, com ou sem pontos e espaços.",
                }
            },
            "required": ["linha_digitavel"],
        },
    ),
    types.FunctionDeclaration(
        name="analisar_link",
        description=(
            "Analisa um link sem abri-lo: domínio que imita marca, encurtador, falta de HTTPS e a "
            "lista de sites perigosos do Google."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "O link exatamente como aparece."}},
            "required": ["url"],
        },
    ),
    types.FunctionDeclaration(
        name="emitir_veredito",
        description="Entrega o veredito final. Chame uma única vez, depois de conferir todos os códigos.",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "nivel": {
                    "type": "string",
                    "enum": ["provavel_golpe", "atencao", "sem_sinais"],
                    "description": "provavel_golpe: há prova ou vários sinais fortes; atencao: há motivo "
                    "para desconfiar; sem_sinais: nada indica golpe.",
                },
                "resumo": {
                    "type": "string",
                    "description": "Uma ou duas frases simples, para alguém que não entende de tecnologia.",
                },
                "texto_do_print": {
                    "type": "string",
                    "description": "Se houver print, o texto da mensagem que aparece nele, transcrito "
                    "fielmente, sem os códigos Pix e boletos. Vazio se não houver print.",
                },
                "marca_alegada": {
                    "type": "string",
                    "description": "Empresa, banco, órgão ou pessoa que a mensagem diz ser. Vazio se nenhuma.",
                },
                "sinais": {
                    "type": "array",
                    "description": "Sinais de manipulação percebidos no texto ou no print que os achados "
                    "não cobrem. Não repita os sinais dos achados.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "descricao": {"type": "string"},
                            "gravidade": {"type": "string", "enum": ["alta", "media", "baixa"]},
                        },
                        "required": ["descricao", "gravidade"],
                    },
                },
                "o_que_fazer": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "De 2 a 4 orientações práticas, em ordem de importância.",
                },
            },
            "required": ["nivel", "resumo", "sinais", "o_que_fazer"],
        },
    ),
]

NOMES_VERIFICADORES = {"decodificar_pix", "validar_boleto", "analisar_link"}


def _so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


class Executor:
    """Executa as chamadas do modelo e acumula os achados, sem repetir códigos."""

    def __init__(
        self,
        texto: str,
        achados: Achados,
        tem_imagem: bool,
        chave_safe_browsing: str | None = None,
        cliente_http: httpx.Client | None = None,
    ):
        self.texto = texto
        self.texto_corrido = re.sub(r"\s+", "", texto)
        self.digitos_do_texto = _so_digitos(texto)
        self.achados = achados
        self.tem_imagem = tem_imagem
        self.chave_safe_browsing = chave_safe_browsing
        self.cliente_http = cliente_http
        self.chamadas: list[str] = []
        self.correcoes: list[str] = []
        self._vistos: set[tuple[str, str]] = {("link", link.url) for link in achados.links}

    def _origem(self, no_texto: bool) -> Origem:
        return "imagem" if self.tem_imagem and not no_texto else "texto"

    def executar(self, nome: str, args: dict[str, Any]) -> dict[str, Any]:
        """Roda uma ferramenta e devolve o resultado em JSON para o modelo."""
        try:
            if nome == "decodificar_pix":
                codigo = re.sub(r"\s*[\r\n]+\s*", "", str(args["codigo"])).strip()
                self.chamadas.append("decodificar_pix")
                resultado = decodificar_pix(codigo)
                origem = self._origem(re.sub(r"\s+", "", codigo) in self.texto_corrido)
                corrigido = None
                if not resultado.valido and origem == "imagem":
                    corrigido = corrigir_leitura_pix(codigo)
                    if corrigido:
                        resultado = decodificar_pix(corrigido)
                        self.correcoes.append(
                            "Um caractere do código Pix foi lido errado no print e corrigido pela "
                            "conferência do próprio código."
                        )
                if ("pix", codigo) not in self._vistos and not self._ja_tem_pix(resultado):
                    self._vistos.add(("pix", codigo))
                    self.achados.pix.append((resultado, origem))
                if corrigido:
                    return resultado.model_dump(mode="json", exclude_none=True) | {
                        "corrigido_pela_conferencia": True
                    }
            elif nome == "validar_boleto":
                linha = str(args["linha_digitavel"])
                self.chamadas.append("validar_boleto")
                resultado = validar_boleto(linha)
                chave = _so_digitos(linha)
                if ("boleto", chave) not in self._vistos and not self._ja_tem_boleto(chave):
                    self._vistos.add(("boleto", chave))
                    self.achados.boletos.append((resultado, self._origem(chave in self.digitos_do_texto)))
            elif nome == "analisar_link":
                url = str(args["url"]).strip()
                self.chamadas.append("analisar_link")
                resultado = analisar_link(url, self.chave_safe_browsing, self.cliente_http)
                if ("link", url) not in self._vistos:
                    self._vistos.add(("link", url))
                    self.achados.links.append(resultado)
            else:
                return {"erro": f"Ferramenta desconhecida: {nome}"}
        except KeyError as faltando:
            return {"erro": f"Argumento obrigatório ausente: {faltando}"}
        return resultado.model_dump(mode="json", exclude_none=True)

    def _ja_tem_pix(self, resultado) -> bool:
        return any(p.model_dump() == resultado.model_dump() for p, _ in self.achados.pix)

    def _ja_tem_boleto(self, digitos: str) -> bool:
        return any(b.linha_digitavel == digitos for b, _ in self.achados.boletos)


def achados_em_json(achados: Achados) -> dict[str, Any]:
    """Resumo dos achados do texto, enviado ao modelo antes de ele começar."""
    return {
        "pix": [p.model_dump(mode="json", exclude_none=True) | {"origem": o} for p, o in achados.pix],
        "boletos": [b.model_dump(mode="json", exclude_none=True) | {"origem": o} for b, o in achados.boletos],
        "links": [link.model_dump(mode="json", exclude_none=True) for link in achados.links],
    }
