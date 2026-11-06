"""Decodificador do Pix copia e cola (BR Code, padrão EMV QRCPS-MPM).

O código é uma sequência de campos TLV: 2 dígitos de identificador, 2 dígitos
de tamanho e o valor. Os campos que interessam para detectar golpe:

    26  Informações da conta (subcampos 00 = br.gov.bcb.pix, 01 = chave,
        02 = descrição, 25 = URL do QR dinâmico)
    54  Valor
    59  Nome do recebedor
    60  Cidade do recebedor
    62  Dados adicionais (subcampo 05 = txid)
    63  CRC16 de todo o código, incluindo o próprio "6304"
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from verificadores.modelos import ResultadoPix, TipoChavePix, TipoRecebedor

GUI_PIX = "br.gov.bcb.pix"

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SUFIXOS_EMPRESA = re.compile(
    r"\b(LTDA|S/?A|S\.A\.?|EIRELI|EPP|ME|MEI|CIA|COMERCIO|SERVICOS|PAGAMENTOS|"
    r"INSTITUICAO|BANCO|DISTRIBUIDORA|ENERGIA|TELECOM)\b",
    re.I,
)


def crc16_ccitt(dados: str) -> str:
    """CRC16-CCITT-FALSE (polinômio 0x1021, valor inicial 0xFFFF) em 4 hexadecimais."""
    crc = 0xFFFF
    for byte in dados.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def _ler_tlv(texto: str) -> tuple[list[tuple[str, str]], int, str | None]:
    """Lê campos TLV em sequência.

    Devolve os campos lidos, até onde a leitura chegou e uma mensagem de erro
    (ou None). Para logo depois do campo 63 (CRC), que encerra o código.
    """
    campos: list[tuple[str, str]] = []
    i = 0
    while i < len(texto):
        cabecalho = texto[i : i + 4]
        if len(cabecalho) < 4 or not cabecalho.isdigit():
            return campos, i, f"Campo malformado na posição {i}"
        ident, tamanho = cabecalho[:2], int(cabecalho[2:])
        valor = texto[i + 4 : i + 4 + tamanho]
        if len(valor) < tamanho:
            return campos, i, f"Campo {ident} termina antes do tamanho informado"
        campos.append((ident, valor))
        i += 4 + tamanho
        if ident == "63":
            break
    return campos, i, None


def classificar_chave(chave: str) -> TipoChavePix:
    chave = chave.strip()
    if chave.startswith("+"):
        return "telefone"
    if _EMAIL.match(chave):
        return "email"
    if _UUID.match(chave):
        return "aleatoria"
    if chave.isdigit() and len(chave) == 11:
        return "cpf"
    if chave.isdigit() and len(chave) == 14:
        return "cnpj"
    return "desconhecida"


def _tipo_recebedor(tipo_chave: TipoChavePix, nome: str | None) -> TipoRecebedor:
    if tipo_chave == "cpf":
        return "pessoa_fisica"
    if tipo_chave == "cnpj":
        return "pessoa_juridica"
    if nome and _SUFIXOS_EMPRESA.search(nome):
        return "pessoa_juridica"
    return "indefinido"


def extrair_pix(texto: str) -> list[str]:
    """Encontra códigos Pix copia e cola dentro de um texto qualquer.

    Quebras de linha são removidas antes, porque aplicativos de mensagem
    costumam quebrar códigos longos.
    """
    corrido = re.sub(r"[\r\n]+", "", texto)
    codigos = []
    for inicio in re.finditer(r"000201", corrido):
        campos, fim, erro = _ler_tlv(corrido[inicio.start() :])
        if erro is None and campos and campos[-1][0] == "63":
            codigos.append(corrido[inicio.start() : inicio.start() + fim])
    return codigos


# Trocas comuns ao ler texto de uma imagem.
CONFUSOES_DE_LEITURA = {
    "0": "Oo", "O": "0", "o": "0",
    "1": "Il", "I": "1l", "l": "1I",
    "5": "S", "S": "5",
    "8": "B", "B": "8",
    "2": "Z", "Z": "2",
    "6": "G", "G": "6",
}


def corrigir_leitura_pix(codigo: str) -> str | None:
    """Tenta consertar um código lido de imagem usando o próprio CRC.

    Testa cada troca comum de leitura (0/O, 1/I/l, 5/S, 8/B...) em uma posição
    por vez. Devolve o código corrigido só se exatamente uma variante passar
    na conferência completa; com mais de uma, a correção seria um chute.

    Só uma troca é tentada de propósito: são cerca de 100 variantes para um
    código típico, e a chance de alguma passar no CRC por acaso fica perto de
    0,2%. Com duas trocas seriam milhares, e um falso acerto ficaria provável.
    """
    codigo = re.sub(r"[\r\n]+", "", codigo).strip()
    if decodificar_pix(codigo).valido:
        return codigo
    corrigidos = []
    for i, caractere in enumerate(codigo):
        for troca in CONFUSOES_DE_LEITURA.get(caractere, ""):
            candidato = codigo[:i] + troca + codigo[i + 1 :]
            if decodificar_pix(candidato).valido:
                corrigidos.append(candidato)
    return corrigidos[0] if len(corrigidos) == 1 else None


def decodificar_pix(codigo: str) -> ResultadoPix:
    """Abre um Pix copia e cola e devolve quem recebe o dinheiro de verdade."""
    codigo = re.sub(r"[\r\n]+", "", codigo).strip()
    erros: list[str] = []

    campos, fim, erro_tlv = _ler_tlv(codigo)
    if erro_tlv:
        return ResultadoPix(valido=False, erros=[erro_tlv])
    if fim < len(codigo):
        erros.append("Há texto sobrando depois do CRC")

    mapa = dict(campos)

    # CRC: calculado sobre tudo até o "6304", inclusive.
    crc_ok = False
    if campos and campos[-1][0] == "63" and len(campos[-1][1]) == 4:
        crc_informado = campos[-1][1].upper()
        crc_calculado = crc16_ccitt(codigo[: fim - 4])
        crc_ok = crc_informado == crc_calculado
        if not crc_ok:
            erros.append(
                f"CRC não confere (informado {crc_informado}, calculado {crc_calculado}): "
                "o código foi alterado ou está incompleto"
            )
    else:
        erros.append("Código sem o campo de CRC no final")

    if mapa.get("00") != "01":
        erros.append("Não começa como um BR Code (campo 00 deveria ser 01)")
    if mapa.get("53", "986") != "986":
        erros.append("Moeda diferente do real")
    if mapa.get("58", "BR") != "BR":
        erros.append("País do recebedor diferente de BR")

    # A conta Pix pode vir em qualquer campo de 26 a 51; procura o que tem o GUI do Pix.
    conta: dict[str, str] | None = None
    for ident, valor in campos:
        if "26" <= ident <= "51":
            sub, _, erro_sub = _ler_tlv(valor)
            if erro_sub is None and dict(sub).get("00", "").lower() == GUI_PIX:
                conta = dict(sub)
                break
    if conta is None:
        erros.append("Não há informações de conta Pix (br.gov.bcb.pix)")
        conta = {}

    chave = conta.get("01")
    url = conta.get("25")
    if not chave and not url:
        erros.append("Não há chave Pix nem URL de cobrança")

    valor: Decimal | None = None
    if "54" in mapa:
        try:
            valor = Decimal(mapa["54"])
        except InvalidOperation:
            erros.append(f"Valor ilegível: {mapa['54']!r}")

    adicionais, _, _ = _ler_tlv(mapa.get("62", ""))
    txid = dict(adicionais).get("05")

    nome = mapa.get("59")
    if not nome:
        erros.append("Sem nome do recebedor")
    tipo_chave = classificar_chave(chave) if chave else "desconhecida"

    return ResultadoPix(
        valido=not erros,
        crc_ok=crc_ok,
        erros=erros,
        dinamico=url is not None,
        chave=chave,
        tipo_chave=tipo_chave,
        url_cobranca=url,
        nome_recebedor=nome,
        cidade=mapa.get("60"),
        valor=valor,
        identificador=txid,
        descricao=conta.get("02"),
        tipo_recebedor=_tipo_recebedor(tipo_chave, nome),
    )
