"""Gera os dados do Simulado (modo prova do app) em web/public/data/prova/.

  prova/index.json   edições, dias, duração oficial, áreas e cores de caderno
  prova/<ano>.json   cadernos (ordem de cada cor), gabarito, parâmetros TRI e o texto das questões

Fonte: dados/cadernos.json (ITENS_PROVA) e dados/provas-inep-visao.jsonl (+ -espanhol), os mesmos do modo prova dos agentes:
o estudante e o agente fazem exatamente a mesma prova.

Uso (na raiz do ENEMWise):  python tools/modo-prova/exportar_web.py
"""
import argparse, json
from pathlib import Path


def ler_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").split("\n") if l.strip()] if Path(p).exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default="dados")
    ap.add_argument("--saida", default="web/public/data/prova")
    a = ap.parse_args()
    dados, out = Path(a.dados), Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    cad = json.loads((dados / "cadernos.json").read_text(encoding="utf-8"))["anos"]
    txt = {}
    for nome in ("provas-inep", "provas-inep-espanhol"):
        f = dados / f"{nome}-visao.jsonl"
        if not f.exists():
            f = dados / f"{nome}.jsonl"
        for r in ler_jsonl(f):
            ano, num = r["id"].split("_")
            txt[(int(ano), int(num), r.get("lingua") or "")] = r
    idx = {"versao": 1, "anos": []}
    total = sem = 0
    for ano_s, A in sorted(cad.items()):
        ano = int(ano_s)
        itens, cadernos = {}, {}
        # texto pelo caderno Amarelo (posição -> co_item)
        for dia, cs in A["cadernos"].items():
            am = next((c for c in cs if "AMAREL" in c["cor"]), None)
            if am:
                for it in am["itens"]:
                    lg = it["lingua"] or ""
                    r = txt.get((ano, it["pos"], lg)) or txt.get((ano, it["pos"], "")) or txt.get((ano, it["pos"], "ingles"))
                    if it["co_item"] > 0 and r and r.get("alternatives") and len(r["alternatives"]) == 5:
                        itens[str(it["co_item"])] = {"enunciado": r["question"], "alternativas": r["alternatives"],
                                                     "descricao": r.get("description") or []}
            cadernos[dia] = [{"cor": c["cor"], "itens": [
                {"pos": i["pos"], "area": i["area"], "co_item": i["co_item"], "co_prova": i["co_prova"], "lingua": i["lingua"],
                 "gab": i["gab"], "anulado": bool(i["anulado"]), "hab": i["habilidade"], "a": i["a"], "b": i["b"], "c": i["c"]}
                for i in c["itens"]]} for c in cs]
        for cs in cadernos.values():
            for c in cs:
                for i in c["itens"]:
                    if i["co_item"] > 0:
                        total += 1; sem += str(i["co_item"]) not in itens
        (out / f"{ano}.json").write_text(json.dumps({"ano": ano, "dias": A["dias"], "cadernos": cadernos, "itens": itens},
                                                    ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        idx["anos"].append({"ano": ano, "dias": [{**d, "cores": [c["cor"] for c in cadernos.get(str(d["dia"]), [])]} for d in A["dias"]]})
    (out / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(idx['anos'])} edições -> {out}  ({sem} de {total} posições de caderno sem texto)")


if __name__ == "__main__":
    main()
