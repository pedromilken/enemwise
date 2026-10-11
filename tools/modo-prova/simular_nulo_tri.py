"""Candidatos sintéticos pela TRI do INEP: o NULO estatístico do modo prova (categoria 1 da literatura de alunos simulados).

Cada candidato tem uma proficiência θ ~ Normal(média, dp), sorteia uma cor de caderno por dia (como os agentes) e responde a
TODAS as questões com P = c + (1-c)/(1+e^{-1,7a(θ-b)}), usando os parâmetros do INEP. Não há aprendizagem, cansaço, relógio
nem efeito de ordem — a menos que se injete um com --efeito-posicao (logit somado por posição dentro da área), o que serve
para medir se as análises RECUPERAM um efeito conhecido (teste de poder e de viés).

A saída tem o mesmo formato de uma rodada do modo prova (respostas.jsonl + config.json), então analisar_prova.py e
kt_prova.py rodam sem mudança.

Uso:
  python simular_nulo_tri.py --cadernos dados/cadernos.json --saida agentes/saida/prova-nulo-tri --candidatos 20
  python simular_nulo_tri.py ... --saida agentes/saida/prova-nulo-tri-efeito --efeito-posicao -0.01
"""
import argparse, json, os
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cadernos", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--candidatos", type=int, default=20, help="por edição (os agentes usam 20)")
    ap.add_argument("--anos", default="2009-2025")
    ap.add_argument("--media", type=float, default=0.0)
    ap.add_argument("--dp", type=float, default=1.0)
    ap.add_argument("--efeito-posicao", type=float, default=0.0, help="logit por posição dentro da área (ex.: -0.01)")
    ap.add_argument("--lingua", default="ingles")
    ap.add_argument("--semente", type=int, default=2027)
    a = ap.parse_args()
    anos = []
    for p in a.anos.split(","):
        lo, _, hi = p.partition("-"); anos += list(range(int(lo), int(hi or lo) + 1))
    cad = json.load(open(a.cadernos, encoding="utf-8"))["anos"]
    rng = np.random.default_rng(a.semente)
    os.makedirs(a.saida, exist_ok=True)
    nome = "nulo-tri" + (f"-efeito{a.efeito_posicao:+g}" if a.efeito_posicao else "")
    cfg = {"versao": "nulo-1", "cerebro": nome, "rodada": os.path.basename(a.saida.rstrip("/\\")), "inicio": "simulado",
           "memoria": "-", "esgotado": "-", "retorno": "-", "theta": f"N({a.media},{a.dp})", "efeito_posicao": a.efeito_posicao,
           "candidatos": a.candidatos, "semente": a.semente}
    json.dump(cfg, open(os.path.join(a.saida, "config.json"), "w", encoding="utf-8"), indent=2)
    n = 0
    with open(os.path.join(a.saida, "respostas.jsonl"), "w", encoding="utf-8") as f:
        for ano in anos:
            A = cad.get(str(ano))
            if not A:
                continue
            for k in range(1, a.candidatos + 1):
                uid = f"{nome}-{ano}-{k:03d}"; th = rng.normal(a.media, a.dp)
                for dia in A["dias"]:
                    cs = A["cadernos"].get(str(dia["dia"])) or []
                    if not cs:
                        continue
                    c1 = cs[rng.integers(len(cs))]
                    linhas = []
                    for it in sorted((i for i in c1["itens"] if not i["lingua"] or i["lingua"] == a.lingua), key=lambda i: i["pos"]):
                        if it["a"] is None or it["co_item"] < 0:
                            linhas.append(dict(co_item=it["co_item"], area=it["area"], pos=it["pos"], pos_area=it["pos_area"],
                                               co_prova=it["co_prova"], lingua=it["lingua"], gab=it["gab"], resposta=None, correct=None,
                                               acao="anulado_sem_item", tempo=0, relogio=0, fmt="-", anulado=True, a=None, b=None, c=None,
                                               habilidade=it["habilidade"]))
                            continue
                        z = 1.7 * it["a"] * (th - it["b"]) + a.efeito_posicao * (it["pos_area"] - 1)
                        p = it["c"] + (1 - it["c"]) / (1 + np.exp(-z))
                        y = int(rng.random() < p)
                        resp = it["gab"] if y else rng.choice([L for L in "ABCDE" if L != it["gab"]])
                        correct = None if it["anulado"] else y
                        linhas.append(dict(co_item=it["co_item"], area=it["area"], pos=it["pos"], pos_area=it["pos_area"], co_prova=it["co_prova"],
                                           lingua=it["lingua"], gab=it["gab"], resposta=resp, correct=correct, acao="resposta", tempo=0,
                                           relogio=0, fmt="-", anulado=bool(it["anulado"]), a=it["a"], b=it["b"], c=it["c"],
                                           habilidade=it["habilidade"]))
                    f.write(json.dumps(dict(uid=uid, ano=ano, dia=dia["dia"], cor=c1["cor"], lingua=a.lingua, ritmo=1, cerebro=nome,
                                            theta=round(float(th), 3), tempoUsado=0, tempoUtil=dia["duracao_min"], linhas=linhas),
                                       ensure_ascii=False) + "\n")
                n += 1
    print(f"{n} candidatos sintéticos -> {a.saida}  (rode: node tools/modo-prova/modo-prova.js --consolidar --saida {a.saida})")


if __name__ == "__main__":
    main()
