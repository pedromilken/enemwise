"""Tabela 1 do pôster a partir das rodadas (lê os ANALISE.md e KT*.md de cada pasta).

Uso (na raiz do ENEMWise):  python tools/modo-prova/tabela1.py [--saida agentes/saida] [--rodada completo-v13]
Grava TABELA1.md e tabela1.csv em agentes/saida. Agentes = LLMs da rodada; referências = nulo TRI, nulo com efeito,
aleatório e candidatos reais (da seção "Agentes × candidatos reais").
"""
import argparse, glob, os, re, sys
import numpy as np
import pandas as pd
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

AREAS = ["LC", "CH", "CN", "MT"]


def num(s):
    s = s.strip().replace("−", "-")
    m = re.match(r"^[+-]?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else np.nan


def secoes(md):
    """Devolve {título da seção: linhas da 1ª tabela da seção}."""
    out, cab, linhas = {}, "#", []
    for l in md.split("\n"):
        if l.startswith("#"):
            cab = l.strip("# ").strip(); continue
        if l.startswith("| ") and not l.startswith("| área") and not l.startswith("|---"):
            out.setdefault(cab, []).append([c.strip() for c in l.strip().strip("|").split("|")])
    return out


def ler(pasta):
    f = os.path.join(pasta, "ANALISE.md")
    if not os.path.exists(f):
        return None
    S = secoes(open(f, encoding="utf-8").read())
    r = {}
    for k, rows in S.items():
        for c in rows:
            a = c[0]
            if a not in AREAS:
                continue
            d = r.setdefault(a, {})
            if k.startswith("Análise por área"):
                d.update(acerto=num(c[2]), incl=num(c[3]), concord=num(c[10]) if len(c) > 10 else np.nan)
            elif k.startswith("Relógio"):
                d.update(incl_total=num(c[1]), incl_resolv=num(c[2]), gama_resolv_p=num(c[4]))
            elif k.startswith("Agentes × candidatos"):
                rho = re.findall(r"[+-]?\d\.\d+", c[3].replace("−", "-"))
                d.update(acerto_real=num(c[2]), rho=float(rho[-1]) if rho else np.nan, incl_real=num(c[5]))
    for kt, suf in (("KT.md", ""), ("KT-resolvidas.md", "_resolv")):
        f = os.path.join(pasta, kt)
        if os.path.exists(f):
            for k, rows in secoes(open(f, encoding="utf-8").read()).items():
                if k.startswith("Parâmetros"):
                    for c in rows:
                        if c[0] in AREAS:
                            r.setdefault(c[0], {}).update({f"bkt_T{suf}": num(c[1]), f"pfa_itens{suf}": num(c[3]),
                                                           f"pos_itens{suf}": num(c[5])})
    for d in r.values():
        if "incl_total" not in d:   # sem relógio (nulos): total = só resolvidas
            d.update(incl_total=d.get("incl"), incl_resolv=d.get("incl"))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="agentes/saida")
    ap.add_argument("--rodada", default="completo-v13")
    a = ap.parse_args()
    R = {}
    for p in sorted(glob.glob(os.path.join(a.saida, "prova-*"))):
        n = os.path.basename(p)
        if "piloto" in n:
            continue
        x = ler(p)
        if x:
            R[n] = x
    llm = [n for n in R if n.endswith(a.rodada) and "aleatorio" not in n]
    if not llm:
        sys.exit(f"nenhuma rodada de LLM '{a.rodada}' com ANALISE.md em {a.saida}")
    ref = lambda key: next((R[n] for n in R if key(n)), {})
    nulo, efeito, alea = ref(lambda n: n == "prova-nulo-tri"), ref(lambda n: n == "prova-nulo-tri-efeito"), ref(lambda n: "aleatorio" in n)
    pers = [n for n in R if "persona" in n]
    linhas = []
    for area in AREAS:
        g = lambda k: [R[n][area].get(k, np.nan) for n in llm if area in R[n]]
        mm = lambda k, f="{:+.3f}": (f.format(np.nanmedian(g(k))) + " [" + f.format(np.nanmin(g(k))) + ", " + f.format(np.nanmax(g(k))) + "]")
        rg = lambda k, f="{:.2f}": f.format(np.nanmin(g(k))) + "–" + f.format(np.nanmax(g(k)))
        cand = next((R[n][area].get("incl_real") for n in llm if area in R[n] and "incl_real" in R[n][area]), np.nan)
        lin = {"área": area, "candidatos (pp/pos)": f"{cand:+.3f}",
               "nulo TRI + efeito": f"{efeito.get(area, {}).get('incl', np.nan):+.3f}",
               "nulo TRI": f"{nulo.get(area, {}).get('incl', np.nan):+.3f}",
               "aleatório": f"{alea.get(area, {}).get('incl_total', np.nan):+.3f}",
               "agentes: todos os itens": mm("incl_total"), "agentes: só resolvidas": mm("incl_resolv"),
               "menor p γ só resolvidas": f"{np.nanmin(g('gama_resolv_p')):.3f}",
               "concordância agentes / nulo": rg("concord") + f" / {nulo.get(area, {}).get('concord', np.nan):.2f}",
               "ρ com candidatos agentes / nulo": rg("rho") + f" / {nulo.get(area, {}).get('rho', np.nan):.2f}",
               "acerto agentes / candidatos": rg("acerto") + f" / {next((R[n][area].get('acerto_real') for n in llm if area in R[n]), np.nan):.2f}",
               "BKT p̂(T) agentes (mediana) / nulo / aleatório": f"{np.nanmedian(g('bkt_T_resolv')):.2f} / {nulo.get(area, {}).get('bkt_T', np.nan):.2f} / {alea.get(area, {}).get('bkt_T', np.nan):.2f}",
               "ΔAUC PFA−Itens agentes (máx) / nulo": f"{np.nanmax(g('pfa_itens_resolv')):+.4f} / {nulo.get(area, {}).get('pfa_itens', np.nan):+.4f}",
               "ΔAUC posição−Itens agentes (máx, sem relógio)": f"{np.nanmax(g('pos_itens_resolv')):+.4f}"}
        for p in pers:
            d = R[p].get(area, {})
            lin[f"persona ({p.replace('prova-', '')}): só resolvidas / concordância"] = f"{d.get('incl_resolv', np.nan):+.3f} / {d.get('concord', np.nan):.2f}"
        linhas.append(lin)
    T = pd.DataFrame(linhas)
    os.makedirs(a.saida, exist_ok=True)
    T.to_csv(os.path.join(a.saida, "tabela1.csv"), index=False, encoding="utf-8")
    md = ["# Tabela 1 (modo prova, rodada " + a.rodada + ")", "", "Agentes: " + ", ".join(n.replace("prova-", "").replace("-" + a.rodada, "") for n in llm) +
          " (mediana [mín, máx] entre os modelos). Inclinações dentro do item, pp por posição, mediana das 17 edições.", ""]
    for _, r in T.iterrows():
        md.append(f"## {r['área']}")
        md += [f"- {k}: {v}" for k, v in r.items() if k != "área"] + [""]
    open(os.path.join(a.saida, "TABELA1.md"), "w", encoding="utf-8").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
