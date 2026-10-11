"""Prepara o texto das questões a partir dos cadernos oficiais do INEP (PDF, caderno Amarelo).

Gera duas fontes de texto no formato que o pipeline aceita (`enemwise batch --questoes ...`):
  provas-inep.jsonl           questões 1-180 de cada edição (inglês nas 1-5 / 91-95)
  provas-inep-espanhol.jsonl  as cinco questões de espanhol de cada edição
Cada questão traz o gabarito oficial (para o vínculo por impressão digital com o ITENS_PROVA),
a lista `precisa_visao` (figura, gráfico, fórmula, alternativas em imagem...) e os recortes da página.

Uso:
  python preparar_textos.py --provas provas-inep --saida dados [--recortes dados/recortes] [--anos 2009 2023]
"""
import argparse, collections, json, statistics, sys
from pathlib import Path


def jsonl(r):
    """Uma linha JSON por registro, escapando separadores de linha Unicode (o splitlines() do Python quebraria neles)."""
    s = json.dumps(r, ensure_ascii=False)
    for ch in ("\u2028", "\u2029", "\x85", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"):
        s = s.replace(ch, "\\u%04x" % ord(ch))
    return s

from extrair_provas import extrair, salvar_recortes
from gabaritos import ler_todos


def montar(Q, G, saida: Path):
    base = collections.defaultdict(list)
    for q in Q:
        base[(q["ano"], q["dia"])].append(q["n_vetor"])
    lim = {k: statistics.median(v) * 2 + 10 for k, v in base.items()}
    por_lingua = {"ingles": [], "espanhol": []}
    for q in Q:
        grafico = q["n_vetor"] > lim[(q["ano"], q["dia"])]
        motivos = [m for m, c in (("imagem", q["n_img"] > 0), ("grafico", grafico), ("alternativas_figura", q["alternativas_figura"]),
                                  ("sem_alternativas", q["alternativas"] is None), ("ilegivel", q["ilegivel"] > 0.05),
                                  ("formula", q["formula"])) if c]
        lab = G.get(f"{q['ano']}|{q['numero']}|{q['lang'] or ''}") or G.get(f"{q['ano']}|{q['numero']}|")
        r = {"id": f"{q['ano']}_{q['numero']}", "exam": str(q["ano"]), "cor": "Amarelo", "dia": q["dia"],
             "lingua": q["lang"], "question": q["enunciado"], "alternatives": q["alternativas"],
             "label": lab or "", "description": [], "figures": [],
             "precisa_visao": motivos, "recortes": q["recortes"], "fonte": "provas-inep"}
        por_lingua["espanhol" if q["lang"] == "espanhol" else "ingles"].append(r)
    for k, L in por_lingua.items():
        p = saida.with_name(saida.stem + ("" if k == "ingles" else "-espanhol") + ".jsonl")
        p.write_text("\n".join(jsonl(r) for r in L) + "\n", encoding="utf-8")
        c = collections.Counter(m for r in L for m in r["precisa_visao"])
        print(p.name, len(L), "com alternativas", sum(r["alternatives"] is not None for r in L),
              "com gabarito", sum(bool(r["label"]) for r in L), "precisa visão", sum(bool(r["precisa_visao"]) for r in L), dict(c),
              file=sys.stderr)
    return por_lingua["ingles"] + por_lingua["espanhol"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provas", required=True, help="pasta provas-inep (<ano>/D1_prova.pdf, D1_gabarito.pdf...)")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--recortes", help="grava PNG das questões que precisam de visão")
    ap.add_argument("--anos", nargs="*", type=int)
    a = ap.parse_args()
    raiz, out = Path(a.provas), Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    Q = []
    for d in sorted(raiz.iterdir()):
        if not d.name.isdigit() or (a.anos and int(d.name) not in a.anos):
            continue
        for dia in (1, 2):
            pdf = d / f"D{dia}_prova.pdf"
            if pdf.exists():
                qs = extrair(pdf, int(d.name), dia)
                print(f"{d.name} D{dia}: {len(qs)} questões", file=sys.stderr)
                Q += qs
    G = ler_todos(raiz)
    regs = montar(Q, G, out / "provas-inep.jsonl")
    if a.recortes:
        precisa = {(r["exam"], r["id"], r["lingua"]) for r in regs if r["precisa_visao"]}
        for d in sorted({(q["ano"], q["dia"]) for q in Q}):
            qs = [q for q in Q if (q["ano"], q["dia"]) == d and (str(q["ano"]), f"{q['ano']}_{q['numero']}", q["lang"]) in precisa]
            salvar_recortes(raiz / str(d[0]) / f"D{d[1]}_prova.pdf", qs, Path(a.recortes), todos=True)


if __name__ == "__main__":
    main()
