"""Acerto dos candidatos reais por item E por posição no caderno -> dados/acerto_real.csv

Com isso, analisar_prova.py compara agentes e candidatos com o MESMO estimador:
  - acerto por item (agente × candidatos) e a correlação entre eles;
  - inclinação por posição dentro do item, calculada igual para os dois.

Duas fontes (use a primeira que tiver):
  --longo-config pipeline/v92.json   exportação longa do v9.2 (auditada; único caminho para LC, que mistura idiomas)
  --microdados D:/microdados          MICRODADOS_ENEM_<ano>.csv (CN, CH e MT; LC fica de fora com aviso)

Uso (na raiz do ENEMWise, com o pipeline instalado):
  python tools/modo-prova/extrair_acerto_real.py --longo-config pipeline/v92.json --cadernos dados/cadernos.json
  python tools/modo-prova/extrair_acerto_real.py --microdados "C:/.../enem" --cadernos dados/cadernos.json
Saída: ano, area, co_item, pos, acertos, n (uma linha por item × posição em que ele apareceu).
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")   # Windows: saída redirecionada (| Select-String) usa cp1252

import numpy as np
import pandas as pd

try:
    from enemwise_pipeline import leitura as io
    from enemwise_pipeline.schema import RESP_ALIASES
except ImportError:
    sys.exit("Rode com o pipeline no PYTHONPATH (o rodar-prova.ps1 já faz isso).")


def mapas(cad):
    """(ano, co_prova, co_item) -> pos  e  (ano, co_prova, pos_area) -> (co_item, pos), só língua inglês/sem língua"""
    p_item, p_rank = {}, {}
    for ano, A in cad["anos"].items():
        for cs in A["cadernos"].values():
            for c in cs:
                for it in c["itens"]:
                    if it["lingua"] == "espanhol":
                        continue
                    p_item[(int(ano), it["co_prova"], it["co_item"])] = (it["area"], it["pos"])
                    p_rank[(int(ano), it["co_prova"], it["pos_area"])] = (it["area"], it["co_item"], it["pos"])
    return p_item, p_rank


def por_longo(cfgp, anos, areas, p_item, acc):
    from enemwise_pipeline import longo
    cfg = longo.ConfigLongo.ler(cfgp)
    for ano in anos:
        for area in areas:
            try:
                lotes = longo.lotes(cfg, ano, area)
                n0 = 0
                for df in lotes:
                    df = df.assign(correct=pd.to_numeric(df["correct"], errors="coerce"),
                                   co_item=pd.to_numeric(df["co_item"], errors="coerce")).dropna(subset=["correct", "co_item"])
                    if "posicao" in df and df["posicao"].notna().any():
                        df["pos"] = pd.to_numeric(df["posicao"], errors="coerce")
                    else:
                        cp = pd.to_numeric(df["co_prova"], errors="coerce")
                        df["pos"] = [p_item.get((ano, int(a), int(b)), (None, np.nan))[1] if a == a else np.nan
                                     for a, b in zip(cp, df["co_item"])]
                    g = df.dropna(subset=["pos"]).groupby(["co_item", "pos"])["correct"].agg(["sum", "count"])
                    for (it, pos), r in g.iterrows():
                        k = (ano, area, int(it), int(pos)); acc[k][0] += int(r["sum"]); acc[k][1] += int(r["count"])
                    n0 += len(df)
                print(f"  {ano} {area}: {n0:,} respostas", file=sys.stderr)
            except FileNotFoundError as e:
                print(f"  {ano} {area}: {e}", file=sys.stderr)


def por_microdados(raiz, anos, areas, p_rank, acc):
    for ano in anos:
        path = io.find_microdados(raiz, ano)
        if path is None:
            print(f"  {ano}: microdados não encontrados", file=sys.stderr); continue
        cols = io.columns(path)
        for area in areas:
            if area == "LC":
                print(f"  {ano} LC: use --longo-config (a string de LC mistura os idiomas)", file=sys.stderr); continue
            nm = {k: io.resolve(cols, v, area) for k, v in RESP_ALIASES.items()}
            if not (nm["prova"] and nm["respostas"]):
                print(f"  {ano} {area}: colunas ausentes", file=sys.stderr); continue
            usar = [nm["prova"], nm["respostas"]] + [c for c in [nm.get("presenca")] if c]
            gab_col = io.resolve(cols, ["TX_GABARITO_{a}"], area)
            n0 = 0
            for df in pd.read_csv(path, usecols=usar, chunksize=500_000, **io.sniff(path)):
                df = df.dropna(subset=[nm["prova"], nm["respostas"]])
                for cp, g in df.groupby(nm["prova"]):
                    cp = int(cp)
                    R = np.array([list(s[:45].ljust(45)) for s in g[nm["respostas"]].astype(str)])
                    for k in range(45):
                        m = p_rank.get((ano, cp, k + 1))
                        if not m or m[1] < 0:
                            continue
                        _, it, pos = m
                        gab = gabarito(ano, cp, k + 1)
                        if gab is None:
                            continue
                        hits = int((R[:, k] == gab).sum())
                        key = (ano, area, it, pos); acc[key][0] += hits; acc[key][1] += len(R)
                    n0 += len(g)
            print(f"  {ano} {area}: {n0:,} candidatos", file=sys.stderr)


GAB = {}


def gabarito(ano, cp, pos_area):
    return GAB.get((ano, cp, pos_area))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cadernos", default="dados/cadernos.json")
    ap.add_argument("--longo-config"); ap.add_argument("--microdados")
    ap.add_argument("--anos", default="2009-2025"); ap.add_argument("--areas", default="LC,CH,CN,MT")
    ap.add_argument("--saida", default="dados/acerto_real.csv")
    a = ap.parse_args()
    anos = []
    for p in a.anos.split(","):
        lo, _, hi = p.partition("-"); anos += list(range(int(lo), int(hi or lo) + 1))
    areas = a.areas.split(",")
    cad = json.load(open(a.cadernos, encoding="utf-8"))
    for ano, A in cad["anos"].items():
        for cs in A["cadernos"].values():
            for c in cs:
                for it in c["itens"]:
                    if it["lingua"] != "espanhol":
                        GAB[(int(ano), it["co_prova"], it["pos_area"])] = it["gab"] if it["gab"] in list("ABCDE") else None
    p_item, p_rank = mapas(cad)
    acc = defaultdict(lambda: [0, 0])
    if a.longo_config:
        por_longo(a.longo_config, anos, areas, p_item, acc)
    elif a.microdados:
        por_microdados(a.microdados, anos, areas, p_rank, acc)
    else:
        sys.exit("informe --longo-config ou --microdados")
    out = pd.DataFrame([(k[0], k[1], k[2], k[3], v[0], v[1]) for k, v in acc.items()],
                       columns=["ano", "area", "co_item", "pos", "acertos", "n"]).sort_values(["ano", "area", "co_item", "pos"])
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.saida, index=False)
    print(f"{len(out)} linhas (item × posição), {out.n.sum():,} respostas -> {a.saida}", file=sys.stderr)


if __name__ == "__main__":
    main()
