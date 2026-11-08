"""Conjunto de avaliação: 75 golpes e 75 mensagens legítimas.

As mensagens foram escritas para o teste, imitando golpes e avisos comuns no
Brasil (SMS, WhatsApp, e-mail). Não são mensagens coletadas de pessoas reais.
Nomes, CPFs, chaves e endereços são inventados. Os códigos Pix e boletos são
montados aqui, com dígitos verificadores corretos (ou adulterados de
propósito), para que os verificadores tenham o que conferir.

Parte dos golpes não tem código, link nem frase típica: são os casos que as
regras não pegam e que mostram se a IA acrescenta alguma coisa. Parte das
legítimas usa palavras que as regras associam a golpe ("último dia",
"troquei de celular", "será suspenso"), para medir o alarme falso.

    python -m avaliacao.conjunto     # regrava avaliacao/mensagens.json
"""

from __future__ import annotations

import json
from pathlib import Path

from verificadores.boleto import modulo10, modulo11_bancario
from verificadores.pix import crc16_ccitt

ARQUIVO = Path(__file__).with_name("mensagens.json")


# --- Montagem dos códigos --------------------------------------------------


def _campo(ident: str, valor: str) -> str:
    return f"{ident}{len(valor):02d}{valor}"


def pix(nome: str, cidade: str, chave: str, valor: str | None = None, txid: str = "***") -> str:
    """Pix copia e cola estático, com CRC correto."""
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave)
    corpo = _campo("00", "01") + _campo("26", conta) + _campo("52", "0000") + _campo("53", "986")
    if valor:
        corpo += _campo("54", valor)
    corpo += _campo("58", "BR") + _campo("59", nome) + _campo("60", cidade)
    corpo += _campo("62", _campo("05", txid)) + "6304"
    return corpo + crc16_ccitt(corpo)


def pix_adulterado(nome_original: str, nome_trocado: str, cidade: str, chave: str, valor: str | None = None) -> str:
    """Pix em que alguém trocou o nome do recebedor à mão: o CRC deixa de conferir."""
    assert len(nome_original) == len(nome_trocado)
    return pix(nome_original, cidade, chave, valor).replace(nome_original, nome_trocado)


def boleto(banco: str, centavos: int, fator: int = 1636, livre: str = "1234567890123456789012345") -> str:
    """Linha digitável de boleto bancário (47 dígitos). Fator 1636 = 20/11/2026."""
    sem_dv = banco + "9" + f"{fator:04d}" + f"{centavos:010d}" + livre
    barras = sem_dv[:4] + str(modulo11_bancario(sem_dv)) + sem_dv[4:]
    c1, c2, c3 = barras[0:4] + barras[19:24], barras[24:34], barras[34:44]
    return (
        f"{c1[:5]}.{c1[5:]}{modulo10(c1)} {c2[:5]}.{c2[5:]}{modulo10(c2)} "
        f"{c3[:5]}.{c3[5:]}{modulo10(c3)} {barras[4]} {barras[5:19]}"
    )


def conta_de_consumo(segmento: str, centavos: int, empresa: str = "0048") -> str:
    """Linha de conta de consumo (48 dígitos, começa com 8), valor em reais e DV módulo 10."""
    sem_dv = ("8" + segmento + "6" + f"{centavos:011d}" + empresa + "2026111500001234567890123")
    barras = sem_dv[:3] + str(modulo10(sem_dv)) + sem_dv[3:]
    return " ".join(b + str(modulo10(b)) for b in (barras[i : i + 11] for i in range(0, 44, 11)))



# --- Mensagens -------------------------------------------------------------

GOLPES: list[tuple[str, str]] = [
    # Falso parente
    ("falso_parente", "Oi mãe, troquei de número, salva esse aí. O outro celular caiu na água."),
    ("falso_parente", "Pai, sou eu. Tô com número novo. Consegue me fazer um Pix de R$ 600,00? Pago amanhã sem falta.\n"
     + pix("MARCOS V OLIVEIRA", "CAMPINAS", "marcos.oliveira.pg@gmail.com", "600.00")),
    ("falso_parente", "Oi tia, aqui é a Ju, esse é meu novo número. Tô no mercado e meu cartão não passou, "
     "me empresta R$ 230 no Pix? A chave é 11987654321, tá no nome da minha amiga."),
    ("falso_parente", "Vó, perdi meu celular, tô usando o da minha colega. Preciso pagar a passagem pra voltar, "
     "manda R$ 150,00 nesse Pix aqui:\n" + pix("DAIANE S MOURA", "GOIANIA", "40518273611", "150.00")),
    ("falso_parente", "Amor, esse é meu número novo do trabalho. Faz uma transferência de R$ 1.200 pra essa conta "
     "que depois te explico, é urgente. Agência 0001 conta 88213-4."),
    ("falso_parente", "Oi, é o Rafa! Mudei de número. Tem como me ajudar com um boleto que vence hoje? Te devolvo sexta.\n"
     + boleto("237", 78450)),
    ("falso_parente", "Mãe, tô sem crédito no outro chip, me chama por aqui. Preciso de um favor mas não conta pro pai ainda."),
    ("falso_parente", "Filha, aqui é a mamãe. Esse é o número novo do trabalho. Me manda o código de 6 dígitos que chegou "
     "no seu WhatsApp, eu mandei sem querer."),
    ("falso_parente", "Mano, tô num aperto. O app do banco travou e preciso pagar o aluguel hoje. Faz esse Pix e amanhã "
     "te passo de volta, beleza?\n" + pix("JEFERSON A LIMA", "OSASCO", "71234509876", "980.00")),
    ("falso_parente", "Oi pai, número novo! Me adiciona aí que depois te mando uma coisa."),
    ("falso_parente", "Oi filho, é a mãe, celular novo. Preciso pagar o remédio na farmácia e esqueci a senha do app. "
     "Paga pra mim? R$ 340,00\n" + pix("ROSANGELA T VIEIRA", "SAO PAULO", "38912764501", "340.00")),
    ("falso_parente", "Dinda, sou eu, o Lucas, esse é meu novo número. Tô precisando de R$ 80 pro Uber, me empresta? "
     "Chave Pix: lucas.pagamentos2026@gmail.com"),
    # Conta de consumo falsa
    ("conta_de_consumo", "ENEL INFORMA: identificamos 2 faturas em atraso no valor de R$ 247,30. Seu fornecimento será "
     "suspenso HOJE às 18h. Para evitar o corte, pague pelo Pix copia e cola:\n"
     + pix("RODRIGO A FERREIRA", "MANAUS", "12345678909", "247.30")),
    ("conta_de_consumo", "SABESP: débito pendente de R$ 186,40. Regularize nas próximas 24 horas para evitar o corte. "
     "Pague via Pix:\n" + pix("PAULO R SANTOS", "GUARULHOS", "paulo.rsantos88@gmail.com", "186.40")),
    ("conta_de_consumo", "CEMIG: sua fatura venceu. Para evitar a suspensão do fornecimento, pague o boleto abaixo:\n"
     + boleto("237", 21390)),
    ("conta_de_consumo", "Copasa informa: fatura de outubro em aberto, R$ 98,20. Pague pelo código abaixo:\n"
     + conta_de_consumo("3", 9820)),
    ("conta_de_consumo", "CPFL: você tem direito a 30% de desconto na conta de luz pagando hoje pelo Pix:\n"
     + pix("PAGFACIL SERVICOS LTDA", "SAO PAULO", "34567890000155", "152.60")),
    ("conta_de_consumo", "Neoenergia Coelba: sua energia será cortada amanhã. Acesse coelba-segundavia.site e pague a segunda via."),
    ("conta_de_consumo", "Enel: identificamos consumo irregular no seu medidor. Multa de R$ 1.450,00. Para não ter o nome "
     "negativado, pague:\n" + pix("ANDERSON L COSTA", "FORTALEZA", "60238417590", "1450.00")),
    ("conta_de_consumo", "Embasa: conta de água atrasada. Evite o corte pagando agora pelo Pix, chave 71988776655."),
    # Entrega
    ("entrega", "Correios: sua encomenda está retida na fiscalização. Pague a taxa de liberação de R$ 4,90 em até "
     "24 horas: http://correios-rastreio.top/taxa"),
    ("entrega", "Seu pacote não pôde ser entregue por endereço incompleto. Atualize em https://entregas-br.click/atualizar"),
    ("entrega", "CORREIOS: objeto BR482917345BR taxado. Taxa de desembaraço R$ 12,67. Pague via Pix:\n"
     + pix("CLAUDIO M REIS", "CURITIBA", "51839027461", "12.67")),
    ("entrega", "Sua encomenda da Shopee está retida na alfândega. Pague a taxa de liberação: https://bit.ly/3xR7taxa"),
    ("entrega", "Jadlog: tentativa de entrega sem sucesso. Reagende pelo link: http://jadlog-reentrega.com/r/8812"),
    ("entrega", "Receita Federal: sua encomenda internacional foi taxada (R$ 56,33). Regularize em até 48h ou ela será "
     "devolvida: receita-encomendas.online"),
    ("entrega", "Correios: última tentativa de entrega. Confirme seus dados e pague o frete de R$ 7,90 em "
     "correios.entrega-rapida.xyz"),
    # Banco
    ("banco", "Itaú: compra não reconhecida de R$ 2.389,00 no seu cartão. Se não foi você, ligue agora para a central "
     "de segurança: 0800 591 2047."),
    ("banco", "Bradesco: seu cartão será bloqueado. Atualize seus dados em https://bradesco-atualizacao.com"),
    ("banco", "Nubank: detectamos um acesso suspeito. Confirme sua senha em nubank-seguro.app/login"),
    ("banco", "Caixa Econômica: seu FGTS de R$ 1.890 está disponível para saque. Resgate seu valor em caixa-fgts-liberado.online"),
    ("banco", "Banco do Brasil: seu token expirou. Valide seu token pelo link para continuar usando o app: bit.ly/bb-token26"),
    ("banco", "Santander informa: pendência no seu cadastro. Evite o bloqueio da conta acessando http://177.54.12.9/santander"),
    ("banco", "Olá, aqui é do setor de segurança do seu banco. Identificamos uma transação suspeita de R$ 4.500. Para "
     "cancelar, vou precisar que você faça um Pix de teste para a conta segura que vou te passar."),
    ("banco", "Mercado Pago: seu saldo foi retido. Para liberar, pague a taxa de verificação pelo boleto:\n"
     + boleto("033", 6790)),
    ("banco", "Prezado cliente, seu Internet Banking será desativado hoje. Reative em www.reativa-cadastro.com.br"),
    ("banco", "PicPay: você recebeu R$ 500,00 de cashback! Resgate seu saldo em https://picpay.premios-br.shop"),
    # Pedido de código
    ("pedido_de_codigo", "Olá! Aqui é da equipe do WhatsApp. Para manter sua conta ativa, me passa o código de 6 dígitos "
     "que enviamos por SMS."),
    ("pedido_de_codigo", "Oi, mandei um código pro seu número sem querer, pode me enviar? É do meu cadastro na OLX."),
    ("pedido_de_codigo", "Sou da pesquisa do Mercado Livre, você ganhou um cupom de R$ 200. Para ativar, informe o código "
     "que vai chegar no seu celular."),
    ("pedido_de_codigo", "Seu código de acesso do iFood chegou? Repasse ele aqui pra gente confirmar seu cadastro na promoção."),
    ("pedido_de_codigo", "Oi, sou a Carla, mãe do Enzo da escola. Vamos criar um grupo novo da turma, vai chegar um código "
     "no seu WhatsApp, me manda ele pra eu te adicionar."),
    ("pedido_de_codigo", "Banco Inter: para concluir o desbloqueio, digite aqui o token que enviamos por SMS."),
    # Prêmio
    ("premio", "Parabéns! Você foi sorteado na promoção Magalu 2026 e ganhou uma TV de 55 polegadas. Pague só o frete "
     "de R$ 29,90 no Pix:\n" + pix("FABIANA C NUNES", "BELO HORIZONTE", "29384756102", "29.90")),
    ("premio", "Você ganhou 1.500 pontos Livelo que expiram hoje! Troque agora em livelo-pontos.club"),
    ("premio", "Resgate seu prêmio de R$ 5.000 da Tele Sena. Acesse telesena-premio.com e informe seus dados bancários."),
    ("premio", "Sua chave Pix foi sorteada no programa Nota Fiscal Paulista. Para receber R$ 1.200, pague a taxa de "
     "R$ 45,00 pelo código:\n" + pix("WAGNER D ROCHA", "SANTOS", "81726354901", "45.00")),
    ("premio", "Valores a receber: o Banco Central identificou R$ 870,50 esquecidos no seu CPF. Saque em valores-receber-bc.com"),
    ("premio", "Shopee 10 anos: você ganhou um vale-compras de R$ 300! Resgate em https://shopee-presentes.live"),
    # Emprego e tarefas
    ("emprego", "Olá! Sou recrutadora da Amazon. Temos vaga home office: você ganha de R$ 200 a R$ 800 por dia "
     "curtindo vídeos. Tem interesse?"),
    ("emprego", "Vaga de digitador em casa, R$ 3.500 por mês. Para garantir a vaga, pague o kit de cadastro de R$ 89,90:\n"
     + pix("LEANDRO P SILVA", "RECIFE", "90817263544", "89.90")),
    ("emprego", "Oi! Vi seu currículo. Trabalho simples avaliando hotéis pelo celular, comissão na hora. Me chama no "
     "Telegram: t.me/vagas_avaliacao"),
    ("emprego", "Tarefa 3 concluída! Para liberar suas comissões de R$ 1.240, faça um depósito de R$ 300 na conta da plataforma."),
    ("emprego", "Programa Jovem Aprendiz 2026: inscrições até hoje. Taxa de inscrição de R$ 35,00 via Pix:\n"
     + pix("MAICON R ALMEIDA", "SALVADOR", "72635418900", "35.00")),
    # Governo
    ("governo", "Receita Federal: seu CPF será suspenso por pendência na declaração. Regularize em gov-regulariza.online"),
    ("governo", "DETRAN: multa de trânsito com 40% de desconto até hoje. Pague pelo Pix:\n"
     + pix("JOSE C PEREIRA", "BRASILIA", "18273645590", "195.23")),
    ("governo", "INSS: seu benefício será bloqueado se não fizer a prova de vida. Atualize em https://inss-provadevida.site"),
    ("governo", "Gov.br: você tem uma restituição de R$ 2.140,00. Para receber, confirme seus dados bancários em restituicao-gov.com"),
    ("governo", "Detran: licenciamento atrasado. Pague o boleto para evitar a apreensão do veículo:\n" + boleto("001", 16245)),
    ("governo", "Receita Federal: DARF em atraso. Pague ainda hoje via Pix para evitar multa:\n"
     + pix("RF ARRECADACAO DIGITAL LTDA", "BRASILIA", "45678901000122", "318.40")),
    ("governo", "Seu título de eleitor será cancelado. Regularize em tse-regulariza.xyz"),
    # Pix adulterado
    ("pix_adulterado", "Bella Moda: obrigada pela compra! Segue o Pix para finalizar o pedido:\n"
     + pix_adulterado("JULIANA M PRADO", "LOJA BELLA MODA", "RIO DE JANEIRO", "+5521988887777", "89.90")),
    ("pix_adulterado", "Segue o Pix do sinal da reforma, como combinado:\n"
     + pix_adulterado("EDSON F BATISTA", "CONSTRUTORA SOL", "CAMPINAS", "41234567890", "1500.00")),
    ("pix_adulterado", "Imobiliária Central: segue o Pix do aluguel de novembro.\n"
     + pix_adulterado("RONALDO S MELO JR", "IMOBILIARIA CENTR", "LONDRINA", "imobiliaria.pg@gmail.com", "1350.00")),
    ("pix_adulterado", "Campanha do Hospital da Criança: doe qualquer valor pelo Pix abaixo e ajude a reformar a ala infantil.\n"
     + pix_adulterado("PATRICIA G LOPES", "HOSPITAL CRIANCA", "PORTO ALEGRE", "51988123344")),
    # Loja falsa
    ("loja_falsa", "Liquidação Magazine Luiza: iPhone 15 por R$ 1.999 só hoje! Compre em magaluofertas.shop"),
    ("loja_falsa", "Olá, vi seu anúncio na OLX. Já fiz o pagamento, só falta você confirmar no link: olx-pagamento-seguro.com"),
    ("loja_falsa", "Oi! Sou do Mercado Livre. Sua venda foi aprovada, mas você precisa pagar a taxa de liberação de "
     "R$ 49,90 para receber:\n" + pix("THIAGO B SOUZA", "SAO PAULO", "62738495011", "49.90")),
    ("loja_falsa", "Air fryer de R$ 600 por R$ 97 com frete grátis, últimas unidades! Pague no Pix e ganhe 10% de desconto:\n"
     + pix("MARIA E ALVES", "JOINVILLE", "ofertas.mariaalves@gmail.com", "87.30")),
    ("loja_falsa", "Aluguel de temporada em Porto Seguro, casa com piscina por R$ 250 a diária. Para reservar, mande 50% "
     "do valor adiantado no Pix:\n" + pix("GILBERTO N SANTANA", "PORTO SEGURO", "83746519200", "750.00")),
    # Dívida e renegociação
    ("divida", "Itaú: sua proposta de acordo foi aprovada com 80% de desconto. Pague o boleto abaixo ainda hoje para "
     "garantir a condição:\n" + boleto("237", 58940)),
    ("divida", "Serasa Limpa Nome: sua dívida de R$ 3.400 pode ser quitada por R$ 199,00. Oferta válida só hoje:\n"
     + pix("RENATO A CARDOSO", "SAO PAULO", "27364519088", "199.00")),
    ("divida", "Feirão Limpa Nome: seu nome será negativado amanhã. Pague o acordo em acordo-serasa.top"),
    # Investimento
    ("investimento", "Invista R$ 500 hoje e receba R$ 5.000 em 24 horas. Plataforma garantida, vagas limitadas. Chama no zap!"),
    ("investimento", "Oi, sou gerente de investimentos. Nosso robô de criptomoedas rende 3% ao dia. Faça o primeiro "
     "depósito pelo Pix:\n" + pix("ADRIANO F MATOS", "FLORIANOPOLIS", "36475820911", "1000.00")),
]

LEGITIMAS: list[tuple[str, str]] = [
    # Cobrança para a própria empresa ou pessoa
    ("cobranca", "Academia Forma Viva: olá! Sua mensalidade de novembro (R$ 129,90) vence dia 10. Se preferir, pague pelo Pix:\n"
     + pix("ACADEMIA FORMA VIVA LTDA", "RECIFE", "11222333000181", "129.90", "MENS112026")),
    ("cobranca", "Escola Pequeno Saber: a mensalidade de novembro (R$ 890,00) vence dia 10. Pix da escola:\n"
     + pix("ESCOLA PEQUENO SABER LTDA", "NATAL", "22333444000172", "890.00", "NOV26")),
    ("cobranca", "Condomínio Residencial Ipê: a taxa de dezembro é R$ 520,00. Pix do condomínio:\n"
     + pix("CONDOMINIO RESIDENCIAL IPE", "SOROCABA", "33444555000163", "520.00")),
    ("cobranca", "Clínica Sorriso: obrigado pela visita! O valor da consulta foi R$ 180,00. Pix:\n"
     + pix("CLINICA SORRISO LTDA", "VITORIA", "44555666000154", "180.00")),
    ("cobranca", "Pet Shop Amigo Fiel: o banho e tosa do Thor ficou R$ 75,00. Pode pagar pelo Pix:\n"
     + pix("PET SHOP AMIGO FIEL ME", "MACEIO", "55666777000145", "75.00")),
    ("cobranca", "Oi, aqui é a Dona Célia das marmitas. A semana deu R$ 140,00. Meu Pix:\n"
     + pix("CELIA M DOS SANTOS", "JUIZ DE FORA", "19283746500", "140.00")),
    ("cobranca", "Oi, dona Ana, a faxina de hoje ficou R$ 200,00. Segue o Pix no meu nome:\n"
     + pix("JOSEFA R LIMA", "TERESINA", "28374655019", "200.00")),
    ("cobranca", "Speak Up Idiomas: sua matrícula foi confirmada. Primeira parcela de R$ 249,00:\n"
     + pix("SPEAK UP IDIOMAS LTDA", "CUIABA", "66777888000136", "249.00", "MAT2026")),
    # Boletos
    ("boleto", "Enel: sua fatura de novembro, de R$ 187,40, vence em 15/11. Código de barras:\n" + conta_de_consumo("3", 18740)),
    ("boleto", "Sabesp: sua conta de R$ 96,50 já está disponível. Linha digitável:\n" + conta_de_consumo("2", 9650)),
    ("boleto", "Itaú: o boleto do seu cartão, de R$ 1.320,55, vence dia 20:\n" + boleto("341", 132055)),
    ("boleto", "Unimed: segue o boleto da mensalidade de dezembro (R$ 612,00):\n" + boleto("001", 61200)),
    ("boleto", "Faculdade Horizonte: boleto da rematrícula, vencimento 20/11, R$ 1.050,00:\n" + boleto("237", 105000)),
    ("boleto", "Cemig: segunda via da sua conta, R$ 143,22:\n" + conta_de_consumo("3", 14322)),
    # Códigos de verificação que a pessoa pediu
    ("codigo_pedido", "Seu código de acesso é 482913. Ele vale por 5 minutos. Não compartilhe este código com ninguém."),
    ("codigo_pedido", "Nubank: 731594 é o seu código de verificação. Não compartilhe com ninguém."),
    ("codigo_pedido", "WhatsApp: o seu código é 284-617. Não compartilhe este código."),
    ("codigo_pedido", "iFood: use 5821 para entrar na sua conta."),
    ("codigo_pedido", "Mercado Livre: 093412 é o seu código de segurança. Se não foi você, ignore esta mensagem."),
    ("codigo_pedido", "Gov.br: seu código de validação é 663108. Válido por 10 minutos."),
    ("codigo_pedido", "Uber: o seu código é 4417. Nunca o compartilhe."),
    ("codigo_pedido", "Itaú: código 908172 para liberar seu novo celular. Não diga a ninguém, nem a funcionários do banco."),
    # Entregas
    ("entrega", "Correios: seu objeto QB123456789BR saiu para entrega. Acompanhe em https://rastreamento.correios.com.br"),
    ("entrega", "Mercado Livre: seu pacote chega amanhã entre 8h e 18h. Detalhes em https://www.mercadolivre.com.br/minhas-compras"),
    ("entrega", "Amazon: seu pedido 402-1189 foi entregue. Avalie em https://www.amazon.com.br/your-orders"),
    ("entrega", "Shopee: pedido 2611ABCD enviado! Acompanhe pelo app da Shopee."),
    ("entrega", "Magalu: seu pedido foi aprovado e deve chegar até 14/11."),
    ("entrega", "Loggi: sua entrega da Natura chega hoje. Acompanhe: https://www.loggi.com/rastreador/NT8812"),
    ("entrega", "Total Express: seu pedido está em rota de entrega. Se possível, deixe alguém no endereço."),
    ("entrega", "iFood: seu pedido saiu para entrega! O entregador chega em cerca de 15 minutos."),
    # Lembretes
    ("lembrete", "Lembrete: sua consulta com a Dra. Paula (dermatologia) é amanhã às 14h. Responda 1 para confirmar ou 2 para desmarcar."),
    ("lembrete", "Laboratório Fleury: seus exames estão prontos. Veja em https://www.fleury.com.br/resultados"),
    ("lembrete", "Barbearia do Zé: horário confirmado para sábado às 10h. Até lá!"),
    ("lembrete", "Secretaria de Saúde: dose de reforço disponível na UBS do seu bairro, de segunda a sexta, das 8h às 17h."),
    ("lembrete", "Oi, aqui é do consultório da Dra. Lívia. Lembrando da sua limpeza dia 22/11 às 9h30."),
    ("lembrete", "Oficina Avenida: seu carro está pronto, pode buscar até as 18h."),
    # Família, sem pedido de dinheiro
    ("familia", "Mãe, cheguei bem. Amanhã te ligo."),
    ("familia", "Vó, a festa do Pedro é domingo às 15h, lá em casa. Leva aquele bolo?"),
    ("familia", "Pai, me manda a foto daquele documento do carro, por favor."),
    ("familia", "Amor, compra pão quando voltar? E vê se ainda tem leite."),
    ("familia", "Filho, seu tio mandou um abraço. Liga pra ele quando puder."),
    ("familia", "Gente, o almoço de domingo vai ser na casa da tia Lu. Cada um leva um prato!"),
    ("familia", "Mãe, me liga urgente quando vir, é sobre a escola do Davi."),
    ("familia", "Pai, troquei de celular mas o número é o mesmo, tá? Só pra você não estranhar a foto nova."),
    # Família pedindo dinheiro, do número de sempre
    ("familia_pix", "Mãe, me empresta R$ 50,00 pro lanche da excursão? Te pago quando receber a mesada kkk\n"
     + pix("BEATRIZ C SOUZA", "SAO PAULO", "47382910566", "50.00")),
    ("familia_pix", "Pai, a conta do dentista deu R$ 120,00. Pode mandar pro meu Pix? A chave é meu CPF."),
    ("familia_pix", "Mano, paguei a pizza e depois a gente divide. Deu R$ 96,00, manda R$ 48,00 no Pix."),
    ("familia_pix", "Tia, aqui é a Bia, mesmo número de sempre rs. Consegue me ajudar com R$ 100,00 pro material da faculdade? Meu Pix:\n"
     + pix("BIANCA R TEIXEIRA", "SALVADOR", "56473829100", "100.00")),
    ("familia_pix", "Filha, deposita o aluguel desse mês na minha conta, pode ser até sexta."),
    # Avisos de banco
    ("banco", "Itaú: compra aprovada de R$ 89,90 em SUPERMERCADO BOM PRECO no cartão final 4421."),
    ("banco", "Nubank: você recebeu um Pix de R$ 250,00 de JOAO P MARTINS."),
    ("banco", "Bradesco: sua fatura fecha amanhã. Valor parcial de R$ 1.204,33. Veja no app Bradesco."),
    ("banco", "Caixa: seu benefício foi creditado. Consulte o extrato no app Caixa Tem."),
    ("banco", "Santander: você fez uma transferência de R$ 300,00 às 14:32. Se não reconhece, ligue para o número do verso do seu cartão."),
    ("banco", "Banco do Brasil: seu cartão final 8810 foi desbloqueado com sucesso."),
    # Promoções de lojas, pelo site oficial
    ("promocao", "Magalu: a Black Friday começou! Até 70% off em https://www.magazineluiza.com.br/black-friday"),
    ("promocao", "Netflix: novos episódios da sua série favorita já estão disponíveis."),
    ("promocao", "Renner: cupom de 15% válido até domingo na loja ou em https://www.lojasrenner.com.br"),
    ("promocao", "Amazon: último dia da oferta relâmpago, aproveite em https://www.amazon.com.br/deals"),
    ("promocao", "Mercado Livre: você ganhou frete grátis na próxima compra! Use até 30/11 no app."),
    # Condomínio, escola, trabalho
    ("comunicado", "Condomínio: a água será interrompida amanhã das 9h às 12h para manutenção."),
    ("comunicado", "Escola Municipal Monteiro Lobato: reunião de pais quinta às 19h. Contamos com sua presença!"),
    ("comunicado", "RH: o holerite de outubro já está disponível no portal do funcionário."),
    ("comunicado", "Equipe, a reunião de amanhã passou para as 10h. O link da sala está no calendário."),
    ("comunicado", "Síndico: lembrando que a assembleia é dia 20. A pauta está no mural do prédio."),
    ("comunicado", "Prefeitura: campanha de vacinação antirrábica neste sábado, na praça central."),
    # Pix entre amigos e vendas entre pessoas
    ("amigos", "Valeu pelo bolo! Te mandei os R$ 60,00 no Pix agora há pouco."),
    ("amigos", "Oi, sobre o sofá do anúncio: fechado por R$ 450,00. Te mando o Pix assim que ele for entregue."),
    ("amigos", "Pessoal do futebol, a quadra deu R$ 15 pra cada. Pix do Diego:\n"
     + pix("DIEGO F RAMOS", "UBERLANDIA", "65748392011")),
    ("amigos", "Rifa da formatura da Laura: o número 37 é seu! Valor de R$ 10,00. Pix:\n"
     + pix("LAURA M CAMPOS", "MARINGA", "74859302155", "10.00")),
    ("amigos", "Amiga, a sua parte do presente da professora ficou R$ 25,00. Meu Pix:\n"
     + pix("ANA L RIBEIRO", "ARACAJU", "ana.ribeiro.lr@gmail.com", "25.00")),
    # Legítimas com palavras que lembram golpe
    ("aviso_oficial", "Enel: devido a uma manutenção programada, o fornecimento será suspenso no dia 14/11, das 8h às 12h, na sua rua."),
    ("aviso_oficial", "Itaú: sua senha foi alterada. Se não foi você, ligue para o número do verso do cartão."),
    ("aviso_oficial", "Detran-SP: seu licenciamento 2026 vence em dezembro. Pague pelo app do seu banco ou em https://www.detran.sp.gov.br"),
    ("aviso_oficial", "Correios: sua encomenda internacional aguarda o pagamento do imposto de importação. Pague somente pelo "
     "app dos Correios ou em https://www.correios.com.br/minhas-importacoes"),
]


def gerar() -> list[dict]:
    mensagens = []
    for prefixo, classe, lista in (("golpe", "golpe", GOLPES), ("legitima", "legitima", LEGITIMAS)):
        for n, (categoria, texto) in enumerate(lista, start=1):
            mensagens.append({"id": f"{prefixo}-{n:03d}", "classe": classe, "categoria": categoria, "texto": texto})
    return mensagens


def carregar(arquivo: Path = ARQUIVO) -> list[dict]:
    return json.loads(arquivo.read_text(encoding="utf-8"))


def salvar(arquivo: Path = ARQUIVO) -> None:
    arquivo.write_text(json.dumps(gerar(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    salvar()
    print(f"{len(gerar())} mensagens gravadas em {ARQUIVO}")
