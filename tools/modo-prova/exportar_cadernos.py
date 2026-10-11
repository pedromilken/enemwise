"""ITENS_PROVA -> cadernos.json: a ordem real de cada caderno regular, por edição e dia, para o modo prova.

Como achar os cadernos regulares sem depender dos microdados dos participantes:
 1. o caderno Amarelo oficial (PDF) dá o gabarito na ordem impressa;
 2. o CO_PROVA de cada área cujo gabarito, na ordem do CO_POSICAO, bate com o do PDF é a referência;
 3. regulares = todos os CO_PROVA não adaptados com o MESMO conjunto de itens da referência
    (a reaplicação/PPL usa outros itens e fica de fora); ordens repetidas (ex.: caderno ampliado) contam uma vez.
Os cadernos de um dia são pareados pela cor (as duas áreas do dia vêm no mesmo caderno).

Uso (na pasta do pipeline, com os microdados extraídos):
  python exportar_cadernos.py --raiz D:/microdados --textos dados/provas-inep.jsonl --saida dados/cadernos.json
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")   # Windows: saída redirecionada (| Select-String) usa cp1252

import pandas as pd

try:
    from enemwise_pipeline import items as itm, leitura
except ImportError:
    sys.exit("Rode dentro do ambiente do pipeline (pip install -e pipeline).")

AQUI = Path(__file__).parent
COR_NORM = {"AMARELA": "AMARELO", "BRANCA": "BRANCO"}


def cor(v):
    s = str(v).strip().upper()
    return COR_NORM.get(s, s) if s and s != "NAN" else None


def gab_pdf(textos):
    """{ano: {posicao: letra}} do caderno Amarelo (inglês nas posições de língua)."""
    g = defaultdict(dict)
    if not textos:
        return g
    for l in Path(textos).read_text(encoding="utf-8").split("\n"):
        if l.strip():
            r = json.loads(l)
            ano, num = r["id"].split("_")
            if r.get("label"):
                g[int(ano)][int(num)] = r["label"]
    return g


def ordem_area(df, lingua):
    d = df if "TP_LINGUA" not in df else df[df["TP_LINGUA"].isna() | (df["TP_LINGUA"] == lingua)]
    return d.sort_values("CO_POSICAO")


def exportar_ano(ano, path, crono, gpdf, log):
    df = itm.load_itens(path)
    if "IN_ITEM_ADAPTADO" in df:
        df = df[df["IN_ITEM_ADAPTADO"].fillna(0).astype(int) != 1]
    # 2009: em cada cor de LC há uma linha sem CO_ITEM (item retirado). Ela ainda ocupa a posição no caderno:
    # vira um item-fantasma anulado (código negativo, sem texto), para não desalinhar a ordem.
    sem_pos = df["CO_POSICAO"].isna()
    df = df[~sem_pos].copy()
    sem = df["CO_ITEM"].isna()
    if sem.any():
        print(f"  {ano}: {int(sem.sum())} posições sem CO_ITEM viram item anulado sem texto "
              f"(CO_PROVA {sorted(df.loc[sem, 'CO_PROVA'].dropna().astype(int).unique().tolist())[:8]})", file=log)
        df.loc[sem, "CO_ITEM"] = -(df.loc[sem, "CO_PROVA"].astype(int) * 1000 + df.loc[sem, "CO_POSICAO"].astype(int))
        df.loc[sem, "IN_ITEM_ABAN"] = 1
        df.loc[sem, "TX_GABARITO"] = "X"
    df["CO_ITEM"] = df["CO_ITEM"].astype(int)
    df["CO_POSICAO"] = df["CO_POSICAO"].astype(int)
    out = {"dias": crono["dias"], "cadernos": {}, "auditoria": []}
    por_area = {}
    for dia in crono["dias"]:
        for k, area in enumerate(dia["areas"]):
            ini = (dia["dia"] - 1) * 90 + 45 * k + 1
            sub = df[df["SG_AREA"] == area]
            cand = []
            for co_prova, g in sub.groupby("CO_PROVA"):
                o = ordem_area(g, 0)
                if len(o) != 45:
                    continue
                gab = o["TX_GABARITO"].tolist()
                ref = [gpdf.get(ano, {}).get(ini + i) for i in range(45)]
                comp = [(a, b) for a, b in zip(gab, ref) if b and b != "X" and a not in ("X", "*")]
                match = sum(a == b for a, b in comp) / len(comp) if comp else None
                cand.append({"co_prova": int(co_prova), "cor": cor(g["TX_COR"].dropna().iloc[0]) if "TX_COR" in g and g["TX_COR"].notna().any() else None,
                             "ordem": tuple(o["CO_ITEM"].astype(int)), "conj": frozenset(i for i in o["CO_ITEM"].astype(int) if i > 0), "match": match})
            if not cand:
                out["auditoria"].append({"area": area, "erro": "sem cadernos de 45 itens"}); continue
            comm = [c for c in cand if c["match"] is not None]
            if comm:
                ref = max(comm, key=lambda c: c["match"])
                if ref["match"] < 0.9:
                    out["auditoria"].append({"area": area, "erro": f"gabarito do PDF não bate (melhor {ref['match']:.2f}); "
                                             f"cadernos de 45 itens: {[c['co_prova'] for c in cand]}; "
                                             f"todos: {dict(sub.groupby('CO_PROVA').size().astype(int))}"}); continue
            else:  # sem PDF: o Amarelo de maior frequência de conjunto
                freq = defaultdict(int)
                for c in cand: freq[c["conj"]] += 1
                ref = max((c for c in cand if c["cor"] == "AMARELO"), default=max(cand, key=lambda c: freq[c["conj"]]))
            regs, vistos = [], set()
            for c in sorted(cand, key=lambda c: c["co_prova"]):
                if c["conj"] == ref["conj"] and c["ordem"] not in vistos:  # mesmo conjunto (o item-fantasma de 2009 fica fora do conjunto); cadernos adaptados trocam itens e ficam de fora
                    vistos.add(c["ordem"]); regs.append(c)
            por_area[area] = (regs, ini, sub)
            out["auditoria"].append({"area": area, "co_prova_ref": ref["co_prova"], "match_pdf": None if ref["match"] is None else round(ref["match"], 3),
                                     "cadernos": [(c["co_prova"], c["cor"]) for c in regs]})
        # pareia as áreas do dia pela cor
        a1, a2 = dia["areas"]
        if a1 not in por_area or a2 not in por_area:
            continue
        cads = []
        r2 = {c["cor"]: c for c in por_area[a2][0]}
        for i, c1 in enumerate(por_area[a1][0]):
            c2 = r2.get(c1["cor"]) or (por_area[a2][0][i] if i < len(por_area[a2][0]) else None)
            if c2 is None:
                continue
            itens = []
            for area, c in ((a1, c1), (a2, c2)):
                regs, ini, sub = por_area[area]
                g = sub[sub["CO_PROVA"] == c["co_prova"]]
                for lingua in ((0, 1) if area == "LC" else (0,)):
                    o = ordem_area(g, lingua).reset_index(drop=True)
                    for rank, row in o.iterrows():
                        tl = row.get("TP_LINGUA")
                        if lingua == 1 and not (pd.notna(tl) and int(tl) == 1):
                            continue
                        itens.append({"pos": ini + rank, "pos_area": rank + 1, "area": area, "co_prova": c["co_prova"],
                                      "co_item": int(row["CO_ITEM"]), "gab": str(row["TX_GABARITO"]),
                                      "lingua": None if pd.isna(tl) else ("espanhol" if int(tl) == 1 else "ingles"),
                                      "anulado": bool(int(row.get("IN_ITEM_ABAN", 0) or 0)),
                                      "a": None if pd.isna(row.get("NU_PARAM_A")) else float(row["NU_PARAM_A"]),
                                      "b": None if pd.isna(row.get("NU_PARAM_B")) else float(row["NU_PARAM_B"]),
                                      "c": None if pd.isna(row.get("NU_PARAM_C")) else float(row["NU_PARAM_C"]),
                                      "habilidade": None if pd.isna(row.get("CO_HABILIDADE")) else int(row["CO_HABILIDADE"])})
            cads.append({"cor": c1["cor"] or f"caderno{i + 1}", "co_prova": {a1: c1["co_prova"], a2: c2["co_prova"]}, "itens": itens})
        out["cadernos"][str(dia["dia"])] = cads
        print(f"  {ano} D{dia['dia']}: {len(cads)} cadernos ({', '.join(c['cor'] for c in cads)})", file=log)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", required=True, help="pasta com os microdados do INEP extraídos (ITENS_PROVA_<ano>.csv)")
    ap.add_argument("--textos", help="provas-inep.jsonl (gabarito do caderno Amarelo, para achar os cadernos regulares)")
    ap.add_argument("--cronograma", default=str(AQUI / "cronograma.json"))
    ap.add_argument("--anos", default="2009-2025")
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    crono = json.loads(Path(a.cronograma).read_text(encoding="utf-8"))["anos"]
    anos = []
    for parte in a.anos.split(","):
        lo, _, hi = parte.partition("-"); anos += list(range(int(lo), int(hi or lo) + 1))
    gpdf = gab_pdf(a.textos)
    res = {"versao": 1, "anos": {}}
    for ano in anos:
        p = leitura.find_file(a.raiz, "ITENS_PROVA", ano)
        if p is None:
            print(f"{ano}: ITENS_PROVA não encontrado", file=sys.stderr); continue
        if str(ano) not in crono:
            print(f"{ano}: fora do cronograma", file=sys.stderr); continue
        res["anos"][str(ano)] = exportar_ano(ano, p, crono[str(ano)], gpdf, sys.stderr)
        for au in res["anos"][str(ano)]["auditoria"]:
            if "erro" in au:
                print(f"  ATENÇÃO {ano} {au['area']}: {au['erro']}", file=sys.stderr)
    Path(a.saida).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(f"cadernos -> {a.saida}", file=sys.stderr)


if __name__ == "__main__":
    main()
