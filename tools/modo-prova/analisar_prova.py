"""Análises do estudo dos confundidores aplicadas às provas dos agentes (por área, com as 17 edições pareadas).

Para cada célula ano × área (e no agregado por área):
  - inclinação de posição dentro do item: acerto ~ posição no caderno, centrado por item (as cores trocam a posição
    do mesmo item); em pontos percentuais por posição; IC 95% por bootstrap de candidatos;
  - γ do AFM: logit P = θ_candidato + β_item + γ · (oportunidades anteriores na mesma habilidade); teste por
    bootstrap paramétrico sob γ = 0;
  - acerto, nota média, chutes e tempo esgotado.
Itens anulados e sem texto ficam fora. A coluna "candidatos (INEP)" traz a referência do artigo, para comparar.

Uso: python analisar_prova.py agentes/saida/prova-<cerebro>-<rodada> [--boot 500] [--perm 200]
"""
import argparse, glob, json, os, sys, warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")   # Windows: saída redirecionada (| Select-String) usa cp1252

warnings.filterwarnings("ignore", "All-NaN slice", RuntimeWarning)   # réplica sem variação de posição numa célula pequena
REF_INCL = {"LC": -0.151, "CH": -0.082, "MT": -0.055, "CN": -0.021}   # pp/posição, mediana das 17 edições (artigo)
ESGOTADO = ["esgotado", "esgotado_na_questao", "pulou_fim"]


def inclinacao(d):
    x = d["posicao"] - d.groupby("co_item")["posicao"].transform("mean")
    y = d["correct"] - d.groupby("co_item")["correct"].transform("mean")
    v = (x * x).sum()
    return float((x * y).sum() / v * 100) if v > 0 else np.nan


def _incl_pesos(u, it, x, y, w):
    """Inclinação dentro do item com pesos por candidato (w = vezes que o candidato saiu na reamostragem)."""
    ww = w[u]
    sw = np.bincount(it, ww)
    mx = np.bincount(it, ww * x) / np.where(sw > 0, sw, 1)
    my = np.bincount(it, ww * y) / np.where(sw > 0, sw, 1)
    xc, yc = x - mx[it], y - my[it]
    v = (ww * xc * xc).sum()
    return (ww * xc * yc).sum() / v * 100 if v > 0 else np.nan


def boot_incl(d, B, rng):
    """IC 95% da MESMA estatística do ponto (mediana das inclinações das células): em cada réplica, reamostra os
    candidatos dentro de cada célula (ano) e toma a mediana das células."""
    cel = []
    for _, g in d.groupby("ano"):
        u = pd.factorize(g["uid"])[0]; it = pd.factorize(g["co_item"])[0]
        cel.append((u, it, g["posicao"].to_numpy(float), g["correct"].to_numpy(float), u.max() + 1))
    if not cel or max(c[4] for c in cel) < 3:
        return (np.nan, np.nan)
    vals = [np.nanmedian([_incl_pesos(u, it, x, y, np.bincount(rng.integers(0, n, n), minlength=n).astype(float))
                          for u, it, x, y, n in cel]) for _ in range(B)]
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def concordancia(d):
    """Diversidade entre os candidatos-agentes: probabilidade de dois candidatos marcarem a MESMA letra no mesmo item
    (média dos itens). 0,20 = acaso; 1,00 = todos os candidatos são cópias de um só respondente."""
    if "resposta" not in d:
        return np.nan
    r = d[d["resposta"].isin(list("ABCDE"))]
    vals = []
    for _, g in r.groupby(["ano", "co_item"]):
        n = len(g)
        if n < 2:
            continue
        c = g["resposta"].value_counts().to_numpy(float)
        vals.append(((c * (c - 1)).sum()) / (n * (n - 1)))
    return float(np.mean(vals)) if vals else np.nan


def opp(d):
    d = d.sort_values(["uid", "posicao"]).copy()
    d["opp"] = d.groupby(["uid", "habilidade"]).cumcount()
    return d


def afm_fit(d, y=None, lam=0.01, com_gamma=True):  # ridge quase nulo: com 1,0 o θ encolhido empurrava γ para baixo (viés −0,3 no nulo TRI)
    u = pd.factorize(d["uid"])[0]; it = pd.factorize(d["co_item"])[0]
    nu, ni = u.max() + 1, it.max() + 1
    y = d["correct"].to_numpy(float) if y is None else y
    o = d["opp"].to_numpy(float) if com_gamma else np.zeros(len(d))

    def f(w):
        th, be, g = w[:nu], w[nu:nu + ni], w[-1]
        p = 1 / (1 + np.exp(-np.clip(th[u] + be[it] + g * o, -30, 30)))
        ll = np.sum(y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12)) - lam / 2 * (np.sum(th ** 2) + np.sum(be ** 2))
        r = y - p
        gr = np.concatenate([np.bincount(u, r, nu) - lam * th, np.bincount(it, r, ni) - lam * be, [np.sum(r * o)]])
        return -ll, -gr
    w = minimize(f, np.zeros(nu + ni + 1), jac=True, method="L-BFGS-B").x
    p = 1 / (1 + np.exp(-(w[:nu][u] + w[nu:nu + ni][it] + w[-1] * o)))
    return float(w[-1]), p


def afm_gamma(d):
    return afm_fit(d)[0]


def perm_gamma(d, P, rng):
    """Teste por bootstrap paramétrico: simula respostas do modelo SEM efeito de ordem (γ = 0), com as mesmas
    sequências e itens, e reajusta γ. Calibrado mesmo quando posição e item andam juntos (poucas cores)."""
    g0, _ = afm_fit(d)
    _, p0 = afm_fit(d, com_gamma=False)
    cnt = sum(abs(afm_fit(d, y=(rng.random(len(p0)) < p0).astype(float))[0]) >= abs(g0) for _ in range(P))
    return g0, (cnt + 1) / (P + 1)


def fidelidade_persona(a):
    """Condição persona: o agente se comporta como o perfil pedido? (θ do perfil × nota; acerto domina × não domina)"""
    from scipy.stats import spearmanr
    th, nota, dom = {}, {}, []
    for l in open(os.path.join(a.rodada, "respostas.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if "theta_persona" not in r:
            return []
        th[r["uid"]] = r["theta_persona"]
        for x in r["linhas"]:
            if x.get("correct") is not None and "domina" in x:
                dom.append((x["area"], bool(x["domina"]), x["correct"]))
    L = ["", "## Fidelidade da persona", "", "| área | ρ θ do perfil × nota obtida | acerto quando domina | acerto quando NÃO domina | respostas |", "|---|---|---|---|---|"]
    fs = glob.glob(os.path.join(a.rodada, "longo", "*.csv"))
    notas = pd.concat([pd.read_csv(f, usecols=["uid", "nota"]).assign(area=os.path.basename(f)[5:7]) for f in fs]).drop_duplicates(["uid", "area"])
    D = pd.DataFrame(dom, columns=["area", "domina", "y"])
    for area in ["LC", "CH", "CN", "MT"]:
        n = notas[notas.area == area].dropna()
        rho = spearmanr(n.uid.map(th), n.nota)[0] if len(n) > 3 else np.nan
        d = D[D.area == area]
        L.append(f"| {area} | {rho:+.2f} | {d[d.domina].y.mean():.3f} | {d[~d.domina].y.mean():.3f} | {len(d)} |")
    L += ["", "Persona fiel: ρ alto e positivo, e acerto bem maior quando domina. Se o acerto não cair nas habilidades 'não dominadas',",
          "o cérebro ignora o perfil (o paradoxo da competência: um modelo que sabe muito não consegue fingir que não sabe)."]
    return L


def decompor(a, V, rng):
    """Separa o efeito do RELÓGIO (questões do fim do caderno que ficam sem tempo e viram chute ou branco, pelo modelo de
    tempo declarado, igual para qualquer cérebro) do efeito do AGENTE (o acerto cai nas questões que ele de fato resolveu?).
    O ritmo de cada candidato é sorteado sem relação com o cérebro, então tirar as esgotadas não seleciona candidatos
    melhores ou piores: a inclinação 'só resolvidas' mede só o agente."""
    if "acao" not in V or not V["acao"].isin(ESGOTADO).any():
        return []
    L = ["", "## Relógio × agente (decomposição da inclinação)", "",
         "| área | inclinação total (pp/pos) | só resolvidas (pp/pos) [IC 95%] | γ AFM só resolvidas | p | % esgotado no 1º terço / último terço |",
         "|---|---|---|---|---|---|"]
    for area in ["LC", "CH", "CN", "MT"]:
        d = V[V["area"] == area]
        if d.empty:
            continue
        r = d[~d["acao"].isin(ESGOTADO)]
        tot = np.nanmedian([inclinacao(g) for _, g in d.groupby("ano")])
        res = np.nanmedian([inclinacao(g) for _, g in r.groupby("ano")])
        lo, hi = boot_incl(r, a.boot, rng)
        rr = opp(r.assign(uid=r["ano"].astype(str) + "-" + r["uid"].astype(str)))
        g, p = perm_gamma(rr, a.perm, rng) if a.perm else (afm_gamma(rr), np.nan)
        rk = d.groupby("ano")["posicao"].rank(method="first", pct=True)
        q = np.minimum((rk * 3).astype(int) - (rk * 3 % 1 == 0).astype(int), 2)    # terço da posição na área (0, 1, 2)
        e = d["acao"].isin(ESGOTADO)
        L.append(f"| {area} | {tot:+.3f} | {res:+.3f} [{lo:+.3f}, {hi:+.3f}] | {g:+.4f} | {p:.3f} | "
                 f"{100 * e[q == 0].mean():.1f} / {100 * e[q == 2].mean():.1f} |")
    L += ["", "Total = como o ENEM pontua (o que ficou sem tempo vale como chute/branco). Só resolvidas = o agente, sem o relógio.",
          "Se a queda total some nas resolvidas, ela vem do modelo de tempo, não de cansaço ou contexto do agente."]
    return L


def comparar_real(a, V):
    """Agentes × candidatos reais com o mesmo estimador (precisa de dados/acerto_real.csv)."""
    from scipy.stats import spearmanr
    cand = [a.real] if a.real else [os.path.join(a.rodada, *([".."] * k), "dados", "acerto_real.csv") for k in (1, 2, 3)]
    f = next((c for c in cand if c and os.path.exists(c)), None)
    if not f:
        return ["", "## Agentes × candidatos reais", "", "Sem dados/acerto_real.csv: rode extrair_acerto_real.py para esta seção."]
    R = pd.read_csv(f)
    R["co_item"] = R["co_item"].astype(int)
    linhas = ["", "## Agentes × candidatos reais (mesmo estimador)", "",
              "| área | acerto agentes | acerto candidatos | ρ acerto por item (agente × candidato) | inclinação agentes (pp/pos) | inclinação candidatos (pp/pos) | itens |",
              "|---|---|---|---|---|---|---|"]
    for area in ["LC", "CH", "CN", "MT"]:
        r = R[(R.area == area) & R.ano.isin(V.ano.unique())]
        v = V[(V.area == area) & V.ano.isin(r.ano.unique())]
        if r.empty or v.empty:
            continue
        # inclinação dentro do item, ponderada pelo número de respostas em cada posição
        incl = []
        for ano, rr in r.groupby("ano"):
            g = rr.assign(p=rr.acertos / rr.n, npos=rr.n * rr.pos)
            s = g.groupby("co_item")[["n", "npos", "acertos"]].sum()
            g = g.join((s.npos / s.n).rename("mx"), on="co_item").join((s.acertos / s.n).rename("my"), on="co_item")
            x = g.pos - g.mx; y = g.p - g.my
            den = (g.n * x * x).sum()
            if den > 0:
                incl.append(float((g.n * x * y).sum() / den * 100))
        s = r.groupby(["ano", "co_item"])[["acertos", "n"]].sum()
        pr = (s.acertos / s.n).rename("p_real")
        pa = v.groupby(["ano", "co_item"]).correct.mean().rename("p_ag")
        j = pd.concat([pr, pa], axis=1, join="inner")
        rho = spearmanr(j.p_ag, j.p_real)[0] if len(j) > 5 else np.nan
        inc_ag = [inclinacao(g) for _, g in v.groupby("ano")]
        vr = v[~v["acao"].isin(ESGOTADO)] if "acao" in v else v
        inc_res = [inclinacao(g) for _, g in vr.groupby("ano")]
        pr2 = vr.groupby(["ano", "co_item"]).correct.mean().rename("p_ag")
        j2 = pd.concat([pr, pr2], axis=1, join="inner")
        rho2 = spearmanr(j2.p_ag, j2.p_real)[0] if len(j2) > 5 else np.nan
        linhas.append(f"| {area} | {v.correct.mean():.3f} | {(r.acertos.sum() / r.n.sum()):.3f} | {rho:+.2f} ({rho2:+.2f}) | "
                      f"{np.nanmedian(inc_ag):+.3f} ({np.nanmedian(inc_res):+.3f}) | {np.median(incl):+.3f} | {len(j)} |")
    linhas += ["", "Inclinações = mediana das edições; a dos candidatos usa as posições reais de cada item em cada cor de caderno.",
               "Entre parênteses: só as questões que o agente resolveu (sem as esgotadas pelo relógio)."]
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rodada")
    ap.add_argument("--boot", type=int, default=500)
    ap.add_argument("--perm", type=int, default=200)
    ap.add_argument("--real", help="dados/acerto_real.csv (extrair_acerto_real.py); padrão: procura na raiz do repositório")
    a = ap.parse_args()
    rng = np.random.default_rng(2027)
    fs = sorted(glob.glob(os.path.join(a.rodada, "longo", "*.csv")))
    if not fs:
        sys.exit("sem longo/*.csv: rode o modo prova (ou --consolidar) antes")
    todos = []
    for f in fs:
        ano, area = os.path.basename(f)[:-4].split("_")
        d = pd.read_csv(f)
        d["ano"], d["area"] = int(ano), area
        todos.append(d)
    D = pd.concat(todos, ignore_index=True)
    cfg = json.load(open(os.path.join(a.rodada, "config.json"), encoding="utf-8"))
    D["habilidade"] = D["habilidade"].fillna(0).astype(int) if "habilidade" in D else 0
    V = D[D["correct"].notna() & (D["anulado"] == 0)].copy()
    V["correct"] = V["correct"].astype(float)
    linhas = []
    for (ano, area), d in V.groupby(["ano", "area"]):
        linhas.append({"ano": ano, "area": area, "candidatos": d["uid"].nunique(), "acerto": d["correct"].mean(),
                       "incl_pp": inclinacao(d), "gamma": afm_gamma(opp(d)) if d["uid"].nunique() > 2 else np.nan})
    cel = pd.DataFrame(linhas)
    cel.to_csv(os.path.join(a.rodada, "analise-celulas.csv"), index=False)
    out = ["# Análise por área — " + cfg["cerebro"], "",
           f"Rodada {cfg['rodada']}; memória {cfg['memoria']}; tempo esgotado: {cfg['esgotado']}. Itens anulados e sem texto fora.", "",
           "| área | células | acerto | inclinação (pp/pos) [IC 95%] | células com inclinação < 0 | candidatos INEP (mediana) | γ AFM | p (bootstrap γ=0) | % chute | % esgotado | concordância entre candidatos |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for area in ["LC", "CH", "CN", "MT"]:
        d = V[V["area"] == area]
        if d.empty:
            continue
        lo, hi = boot_incl(d, a.boot, rng)
        dd = opp(d.assign(uid=d["ano"].astype(str) + "-" + d["uid"].astype(str)))
        g, p = perm_gamma(dd, a.perm, rng) if a.perm else (afm_gamma(dd), np.nan)
        c = cel[cel["area"] == area]
        tot = D[D["area"] == area]
        pc = lambda k: 100 * tot["acao"].isin(k).mean()
        out.append(f"| {area} | {len(c)} | {d['correct'].mean():.3f} | {c['incl_pp'].median():+.3f} [{lo:+.3f}, {hi:+.3f}] | "
                   f"{(c['incl_pp'] < 0).sum()}/{len(c)} | {REF_INCL[area]:+.3f} | {g:+.4f} | {p:.3f} | "
                   f"{pc(['chute']):.1f} | {pc(['esgotado', 'esgotado_na_questao', 'pulou_fim']):.1f} | "
                   f"{concordancia(d[~d['acao'].isin(ESGOTADO)] if 'acao' in d else d):.2f} |")
    out += ["", "A inclinação agregada usa a mediana das células; o IC é da mesma mediana, reamostrando os candidatos dentro de cada célula.",
            "γ < 0 com p pequeno = desempenho cai ao longo da prova (cansaço/contexto); γ > 0 = 'aprendizado' durante a prova.",
            "Concordância = chance de dois candidatos marcarem a mesma letra no mesmo item (questões resolvidas): 0,20 é o acaso,",
            "1,00 = os candidatos são cópias de um só respondente. Perto de 1, os 20 candidatos não formam uma população (a",
            "variação entre eles some) e o IC por candidatos fica estreito demais: leia o resultado como de um respondente.",
            "Detalhe por célula: analise-celulas.csv."]
    out += decompor(a, V, rng)
    out += comparar_real(a, V)
    out += fidelidade_persona(a)
    open(os.path.join(a.rodada, "ANALISE.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
