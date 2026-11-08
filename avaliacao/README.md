# Avaliação

Este é o conjunto de 150 mensagens que mede o Golpe ou Não: 75 golpes e 75 mensagens legítimas. Ele é usado para rodar o agente e contar os acertos e os erros. Os números estão em [RESULTADOS.md](RESULTADOS.md).

## O conjunto

As mensagens foram **escritas para o teste**. Elas imitam golpes e avisos comuns no Brasil por SMS, WhatsApp e e-mail, mas não foram coletadas de pessoas reais. Nomes, CPFs, chaves Pix e endereços são inventados. Os códigos Pix e as linhas de boleto são montados por [conjunto.py](conjunto.py) com os dígitos verificadores corretos. Os 4 Pix adulterados, de propósito, não passam na conferência.

O conjunto inclui casos difíceis nos dois lados:

- **Golpes sem nenhuma pista automática.** São mensagens sem código, sem link suspeito e sem frase típica: vaga de emprego que cobra taxa, investimento que promete dobrar o dinheiro, "valores a receber" do Banco Central. As regras não pegam esses casos, e servem para medir o que a IA acrescenta.
- **Legítimas com palavras de golpe.** "Último dia da oferta", "troquei de celular mas o número é o mesmo" e "o fornecimento será suspenso para manutenção" são exemplos. Servem para medir o alarme falso.

| Golpes (75) | | Legítimas (75) | |
| --- | --- | --- | --- |
| Falso parente | 12 | Cobrança da própria empresa ou pessoa | 8 |
| Banco e falsa central | 10 | Boletos e contas de consumo | 6 |
| Conta de luz e água | 8 | Códigos de verificação pedidos pela pessoa | 8 |
| Entrega e taxa | 7 | Avisos de entrega | 8 |
| Governo (Receita, Detran, INSS) | 7 | Lembretes de consulta e serviço | 6 |
| Pedido de código | 6 | Família, sem pedido de dinheiro | 8 |
| Prêmio | 6 | Família pedindo Pix, do número de sempre | 5 |
| Emprego e tarefas | 5 | Avisos de banco | 6 |
| Loja falsa | 5 | Promoções pelo site oficial | 5 |
| Pix adulterado | 4 | Condomínio, escola e trabalho | 6 |
| Dívida e renegociação | 3 | Pix entre amigos | 5 |
| Investimento | 2 | Avisos oficiais com palavras de golpe | 4 |

## As medidas

O veredito tem três níveis: "provável golpe", "atenção" e "sem sinais".

- **Golpes pegos** conta os golpes que receberam "provável golpe" ou "atenção". As duas respostas fazem a pessoa parar e conferir antes de pagar. É a medida mais importante, porque deixar passar um golpe custa dinheiro.
- **Golpes com "provável golpe"** conta os golpes que receberam o aviso forte.
- **Alarme falso** conta as mensagens legítimas marcadas como "provável golpe". Alarme demais faz a pessoa parar de confiar no aviso.
- **Legítimas com "atenção"** conta as mensagens legítimas que receberam um pedido de cautela. Esse erro custa pouco, mas também entra na conta.

## Como rodar

```bash
python -m avaliacao --sem-ia            # só verificadores e regras, não precisa de chave
GEMINI_API_KEY=... python -m avaliacao  # com a IA
```

- **Rodada com IA.** Ela faz pelo menos uma chamada ao Gemini por mensagem, com 7 segundos de pausa entre as mensagens (dá para mudar com `--pausa`). Cada resposta é gravada em `resultados/com_ia.json` assim que chega.
- **Se a cota gratuita acabar no meio.** O script para depois de 3 falhas seguidas. Rode de novo mais tarde: as mensagens já avaliadas são puladas. Uma falha de cota nunca é contada como resultado.
- **Safe Browsing.** A consulta fica desligada nas duas rodadas, para o resultado depender só do código e do modelo.
- **Depois de mudar regras ou verificadores.** Rode `python -m avaliacao --sem-ia` de novo. Um teste confere se `resultados/sem_ia.json` está de acordo com o código atual.
- **Depois de editar o conjunto.** Rode `python -m avaliacao.conjunto` para regravar `mensagens.json`.

## Limites

- **As regras não foram ajustadas a este conjunto.** Ele foi escrito depois delas, e nenhuma regra mudou para acertar as mensagens dele. Se as regras forem melhoradas olhando para estes erros, os próximos números ficam otimistas. O certo é medir com mensagens novas.
- **Só há texto.** Os prints ficam de fora: a leitura de imagem é testada com os exemplos prontos do app.
- **150 mensagens é pouco para porcentagens precisas.** Cada mensagem de golpe vale pouco mais de 1 ponto percentual.
