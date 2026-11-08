# Resultados da avaliação

Gerado por `python -m avaliacao`. O conjunto e o método estão em [avaliacao/README.md](README.md).

| Modo | Golpes pegos | Golpes com "provável golpe" | Alarme falso | Legítimas com "atenção" |
| --- | --- | --- | --- | --- |
| Sem IA (verificadores e regras) | 58/75 (77%) | 32/75 (43%) | 0/75 (0%) | 6/75 (8%) |

## Sem IA (verificadores e regras)

| Classe | Provável golpe | Atenção | Sem sinais |
| --- | --- | --- | --- |
| Golpes | 32 | 26 | 17 |
| Legítimas | 0 | 6 | 69 |

Golpes por tipo:

| Tipo | Pegos | Provável golpe | Sem sinais |
| --- | --- | --- | --- |
| banco | 9/10 | 5 | 1 |
| conta_de_consumo | 8/8 | 3 | 0 |
| divida | 3/3 | 2 | 0 |
| emprego | 0/5 | 0 | 5 |
| entrega | 5/7 | 3 | 2 |
| falso_parente | 10/12 | 7 | 2 |
| governo | 6/7 | 1 | 1 |
| investimento | 0/2 | 0 | 2 |
| loja_falsa | 4/5 | 2 | 1 |
| pedido_de_codigo | 4/6 | 3 | 2 |
| pix_adulterado | 4/4 | 4 | 0 |
| premio | 5/6 | 2 | 1 |

Golpes que passaram sem sinais (17):
- `golpe-009`: Mano, tô num aperto. O app do banco travou e preciso pagar o aluguel hoje. Faz esse Pix e amanhã te passo d...
- `golpe-011`: Oi filho, é a mãe, celular novo. Preciso pagar o remédio na farmácia e esqueci a senha do app. Paga pra mim...
- `golpe-022`: Seu pacote não pôde ser entregue por endereço incompleto. Atualize em https://entregas-br.click/atualizar
- `golpe-025`: Jadlog: tentativa de entrega sem sucesso. Reagende pelo link: http://jadlog-reentrega.com/r/8812
- `golpe-036`: Prezado cliente, seu Internet Banking será desativado hoje. Reative em www.reativa-cadastro.com.br
- `golpe-039`: Oi, mandei um código pro seu número sem querer, pode me enviar? É do meu cadastro na OLX.
- `golpe-041`: Seu código de acesso do iFood chegou? Repasse ele aqui pra gente confirmar seu cadastro na promoção.
- `golpe-048`: Valores a receber: o Banco Central identificou R$ 870,50 esquecidos no seu CPF. Saque em valores-receber-bc...
- `golpe-050`: Olá! Sou recrutadora da Amazon. Temos vaga home office: você ganha de R$ 200 a R$ 800 por dia curtindo víde...
- `golpe-051`: Vaga de digitador em casa, R$ 3.500 por mês. Para garantir a vaga, pague o kit de cadastro de R$ 89,90:
- `golpe-052`: Oi! Vi seu currículo. Trabalho simples avaliando hotéis pelo celular, comissão na hora. Me chama no Telegra...
- `golpe-053`: Tarefa 3 concluída! Para liberar suas comissões de R$ 1.240, faça um depósito de R$ 300 na conta da platafo...
- `golpe-054`: Programa Jovem Aprendiz 2026: inscrições até hoje. Taxa de inscrição de R$ 35,00 via Pix:
- `golpe-059`: Detran: licenciamento atrasado. Pague o boleto para evitar a apreensão do veículo:
- `golpe-067`: Olá, vi seu anúncio na OLX. Já fiz o pagamento, só falta você confirmar no link: olx-pagamento-seguro.com
- `golpe-074`: Invista R$ 500 hoje e receba R$ 5.000 em 24 horas. Plataforma garantida, vagas limitadas. Chama no zap!
- `golpe-075`: Oi, sou gerente de investimentos. Nosso robô de criptomoedas rende 3% ao dia. Faça o primeiro depósito pelo...

Legítimas marcadas como provável golpe (0):
nenhuma.

Legítimas marcadas com atenção (6):
- `legitima-022`: Itaú: código 908172 para liberar seu novo celular. Não diga a ninguém, nem a funcionários do banco.
- `legitima-043`: Mãe, me liga urgente quando vir, é sobre a escola do Davi.
- `legitima-044`: Pai, troquei de celular mas o número é o mesmo, tá? Só pra você não estranhar a foto nova.
- `legitima-059`: Amazon: último dia da oferta relâmpago, aproveite em https://www.amazon.com.br/deals
- `legitima-060`: Mercado Livre: você ganhou frete grátis na próxima compra! Use até 30/11 no app.
- `legitima-072`: Enel: devido a uma manutenção programada, o fornecimento será suspenso no dia 14/11, das 8h às 12h, na sua ...
