"""Contas da avaliação e o relatório em Markdown.

Cada mensagem tem uma classe (golpe ou legítima) e recebe um dos três níveis
do veredito. As medidas seguem o que importa para quem usa:

* **Golpes pegos**: golpes que receberam "provável golpe" ou "atenção". Um
  golpe com "atenção" já faz a pessoa parar e conferir antes de pagar.
* **Golpes com "provável golpe"**: a parte dos golpes em que o aviso é forte.
* **Alarme falso**: legítimas marcadas como "provável golpe". É o erro que
  mais desgasta a confiança no aviso.
* **Legítimas com "atenção"**: pedem cautela sem acusar golpe; custam pouco,
  mas também são contadas.
"""

from __future__ import annotations

from collections import Counter, defaultdict

NIVEIS = ("provavel_golpe", "atencao", "sem_sinais")
ROTULOS = {"provavel_golpe": "Provável golpe", "atencao": "Atenção", "sem_sinais": "Sem sinais"}


def contar(mensagens: list[dict], niveis: dict[str, str]) -> dict:
    """Junta as classes do conjunto com os níveis obtidos. Mensagens sem resultado ficam de fora."""
    matriz = {classe: Counter() for classe in ("golpe", "legitima")}
    por_categoria: dict[str, Counter] = defaultdict(Counter)
    erros = {"golpes_sem_sinais": [], "legitimas_provavel_golpe": [], "legitimas_atencao": []}
    for m in mensagens:
        nivel = niveis.get(m["id"])
        if nivel is None:
            continue
        matriz[m["classe"]][nivel] += 1
        if m["classe"] == "golpe":
            por_categoria[m["categoria"]][nivel] += 1
            if nivel == "sem_sinais":
                erros["golpes_sem_sinais"].append(m["id"])
        elif nivel == "provavel_golpe":
            erros["legitimas_provavel_golpe"].append(m["id"])
        elif nivel == "atencao":
            erros["legitimas_atencao"].append(m["id"])

    golpes, legitimas = matriz["golpe"], matriz["legitima"]
    total_golpes, total_legitimas = sum(golpes.values()), sum(legitimas.values())
    return {
        "avaliadas": total_golpes + total_legitimas,
        "matriz": {c: {n: matriz[c][n] for n in NIVEIS} for c in matriz},
        "golpes_pegos": golpes["provavel_golpe"] + golpes["atencao"],
        "golpes_provavel": golpes["provavel_golpe"],
        "total_golpes": total_golpes,
        "alarmes_falsos": legitimas["provavel_golpe"],
        "legitimas_atencao": legitimas["atencao"],
        "total_legitimas": total_legitimas,
        "por_categoria": {c: {n: por_categoria[c][n] for n in NIVEIS} for c in sorted(por_categoria)},
        "erros": erros,
    }


def _pct(parte: int, total: int) -> str:
    return f"{100 * parte / total:.0f}%" if total else "-"


def _linha_resumo(nome: str, c: dict) -> str:
    return (
        f"| {nome} | {c['golpes_pegos']}/{c['total_golpes']} ({_pct(c['golpes_pegos'], c['total_golpes'])}) "
        f"| {c['golpes_provavel']}/{c['total_golpes']} ({_pct(c['golpes_provavel'], c['total_golpes'])}) "
        f"| {c['alarmes_falsos']}/{c['total_legitimas']} ({_pct(c['alarmes_falsos'], c['total_legitimas'])}) "
        f"| {c['legitimas_atencao']}/{c['total_legitimas']} ({_pct(c['legitimas_atencao'], c['total_legitimas'])}) |"
    )


def relatorio(mensagens: list[dict], modos: dict[str, dict]) -> str:
    """Relatório em Markdown. ``modos`` mapeia o nome do modo para o resultado gravado (com 'niveis')."""
    textos = {m["id"]: m["texto"] for m in mensagens}
    contas = {nome: contar(mensagens, r["niveis"]) for nome, r in modos.items()}

    linhas = [
        "# Resultados da avaliação",
        "",
        "Gerado por `python -m avaliacao`. O conjunto e o método estão em [avaliacao/README.md](README.md).",
        "",
        "| Modo | Golpes pegos | Golpes com \"provável golpe\" | Alarme falso | Legítimas com \"atenção\" |",
        "| --- | --- | --- | --- | --- |",
    ]
    linhas += [_linha_resumo(nome, c) for nome, c in contas.items()]
    for nome, r in modos.items():
        if r.get("modelo"):
            linhas += ["", f"{nome}: modelo `{r['modelo']}`, rodado em {r.get('data', '?')}."]

    for nome, c in contas.items():
        linhas += ["", f"## {nome}", "", "| Classe | Provável golpe | Atenção | Sem sinais |", "| --- | --- | --- | --- |"]
        for classe, rotulo in (("golpe", "Golpes"), ("legitima", "Legítimas")):
            m = c["matriz"][classe]
            linhas.append(f"| {rotulo} | {m['provavel_golpe']} | {m['atencao']} | {m['sem_sinais']} |")
        linhas += ["", "Golpes por tipo:", "", "| Tipo | Pegos | Provável golpe | Sem sinais |", "| --- | --- | --- | --- |"]
        for categoria, m in c["por_categoria"].items():
            total = sum(m.values())
            pegos = m["provavel_golpe"] + m["atencao"]
            linhas.append(f"| {categoria} | {pegos}/{total} | {m['provavel_golpe']} | {m['sem_sinais']} |")
        for chave, titulo in (
            ("golpes_sem_sinais", "Golpes que passaram sem sinais"),
            ("legitimas_provavel_golpe", "Legítimas marcadas como provável golpe"),
            ("legitimas_atencao", "Legítimas marcadas com atenção"),
        ):
            ids = c["erros"][chave]
            linhas += ["", f"{titulo} ({len(ids)}):"]
            if not ids:
                linhas.append("nenhuma.")
            for i in ids:
                resumo = textos[i].split("\n")[0]
                resumo = resumo if len(resumo) <= 110 else resumo[:107] + "..."
                linhas.append(f"- `{i}`: {resumo}")
    return "\n".join(linhas) + "\n"
