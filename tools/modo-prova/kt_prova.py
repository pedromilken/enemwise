"""Knowledge tracing nas provas dos agentes: o mesmo cardápio do estudo dos confundidores, por área.

Para cada área (17 edições juntas; parâmetros e itens de cada edição), sobre as sequências na ordem do caderno:
  3PL INEP        teto psicométrico: P = c + (1-c)/(1+e^{-1,7a(θ-b)}), θ = EAP do candidato sem o próprio item
  Elo-3PL         θ atualizado online após cada resposta (b, a, c do INEP); K escolhido na validação
  BKT             por habilidade, em cada célula ano × área; relatamos p̂(T) (aprender a cada oportunidade)
  PFA             logit = β_item + γs·acertos anteriores + γf·erros anteriores na habilidade
  AFM             logit = θ_aluno + β_item + γ·oportunidades na habilidade (γ e teste por bootstrap em analisar_prova)
  3PL + posição   o teto 3PL mais δ·posição na área: mede quanto a ORDEM acrescenta à previsão (a pergunta central do artigo)
Validação cruzada em 5 partes por candidato (ninguém é previsto com os próprios dados). Métricas: AUC e log-loss.
Itens anulados e sem texto ficam fora; tempo esgotado entra como resposta (é chute ou branco, como no ENEM).

Uso: python kt_prova.py agentes/saida/prova-<cerebro>-<rodada> [--dobras 5]
Saída: KT.md e kt-celulas.csv na pasta da rodada.
"""
import argparse, json, os, sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")   # Windows: saída redirecionada (| Select-String) usa cp1252

D = 1.7
G = np.linspace(-4, 4, 81)


def carregar(dirr):
    rows = []
    for l in open(os.path.join(dirr, "respostas.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        for x in r["linhas"]:
            if x["correct"] is None or x.get("a") is None:
                continue
            rows.append(dict(uid=r["uid"], ano=r["ano"], area=x["area"], dia=r["dia"], pos=x["pos"], pos_area=x["pos_area"],
                             item=f'{r["ano"]}-{x["co_item"]}', hab=f'{r["ano"]}-{x["area"]}-{x.get("habilidade") or 0}',
                             a=x["a"], b=x["b"], c=x["c"], y=int(x["correct"]), acao=x["acao"]))
    d = pd.DataFrame(rows)
    return d.sort_values(["uid", "area", "pos"]).reset_index(drop=True)


def p3(th, a, b, c):
    return c + (1 - c) / (1 + np.exp(-D * a * (th - b)))


def auc(y, p):
    y = np.asarray(y); p = np.asarray(p)
    if y.min() == y.max():
        return np.nan
    r = pd.Series(p).rank().to_numpy()
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def ll(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


# ---------- 3PL teto: EAP deixando o próprio item de fora ----------
def teto_3pl(d):
    out = np.zeros(len(d))
    for _, g in d.groupby(["uid", "area"]):
        idx = g.index.to_numpy()
        P = p3(G[None, :], g.a.to_numpy()[:, None], g.b.to_numpy()[:, None], g.c.to_numpy()[:, None])
        y = g.y.to_numpy()[:, None]
        L = y * np.log(P) + (1 - y) * np.log(1 - P)              # itens × grade
        tot = L.sum(0) - G ** 2 / 2
        for k, i in enumerate(idx):
            lp = tot - L[k]; w = np.exp(lp - lp.max()); th = (w * G).sum() / w.sum()
            out[i] = p3(th, g.a.iloc[k], g.b.iloc[k], g.c.iloc[k])
    return out


# ---------- Elo-3PL online ----------
def elo(d, K):
    out = np.zeros(len(d))
    for _, g in d.groupby(["uid", "area"]):
        th = 0.0
        for i, a, b, c, y in zip(g.index, g.a, g.b, g.c, g.y):
            p = p3(th, a, b, c); out[i] = p
            th += K * (y - p)
    return out


# ---------- BKT por célula (grade), previsão online ----------
GRADE_BKT = [(L0, T, Gs, S) for L0 in (0.2, 0.4, 0.6, 0.8) for T in (0.0, 0.02, 0.05, 0.1, 0.2, 0.3)
             for Gs in (0.1, 0.2, 0.3) for S in (0.05, 0.1, 0.2)]


def bkt_pred(seqs, prm):
    L0, T, Gs, S = prm
    preds = []
    for ys in seqs:
        L = L0; ps = []
        for y in ys:
            p = L * (1 - S) + (1 - L) * Gs; ps.append(p)
            post = L * (1 - S) / p if y else L * S / (1 - p)
            L = post + (1 - post) * T
        preds.append(ps)
    return preds


def bkt_fit(seqs):
    best, bp = None, None
    yy = np.concatenate([np.asarray(s) for s in seqs]) if seqs else np.array([])
    for prm in GRADE_BKT:
        pp = np.concatenate([np.asarray(p) for p in bkt_pred(seqs, prm)])
        v = ll(yy, pp)
        if best is None or v < best:
            best, bp = v, prm
    return bp


def seqs_por_hab(g):
    """sequências (uid, hab) na ordem do caderno; devolve listas de índices e de respostas"""
    idx, ys = [], []
    for _, h in g.groupby(["uid", "hab"], sort=False):
        idx.append(h.index.to_numpy()); ys.append(h.y.tolist())
    return idx, ys


# ---------- logísticos (PFA, posição) ----------
def logit_fit(X, y, off, lam=1.0, nfree=0):
    """minimiza log-loss com ridge (exceto as nfree primeiras colunas)"""
    def f(w):
        z = off + X @ w; p = 1 / (1 + np.exp(-z))
        pen = lam / 2 * np.sum(w[nfree:] ** 2)
        g = X.T @ (p - y) + np.concatenate([np.zeros(nfree), lam * w[nfree:]])
        return -np.sum(y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12)) + pen, g
    return minimize(f, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B").x


def contagens(d):
    s = np.zeros(len(d)); f = np.zeros(len(d)); o = np.zeros(len(d))
    for _, g in d.groupby(["uid", "hab"], sort=False):
        ys = g.y.to_numpy(); cs = np.concatenate([[0], np.cumsum(ys)[:-1]])
        k = np.arange(len(ys))
        s[g.index] = cs; f[g.index] = k - cs; o[g.index] = k
    return s, f, o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rodada"); ap.add_argument("--dobras", type=int, default=5)
    ap.add_argument("--so-resolvidas", action="store_true",
                    help="tira as questões que ficaram sem tempo (efeito do relógio): grava KT-resolvidas.md")
    a = ap.parse_args()
    d = carregar(a.rodada)
    suf = ""
    if a.so_resolvidas:
        d = d[~d["acao"].isin(["esgotado", "esgotado_na_questao", "pulou_fim"])].reset_index(drop=True)
        suf = "-resolvidas"
    if d.empty:
        sys.exit("sem respostas")
    cfg = json.load(open(os.path.join(a.rodada, "config.json"), encoding="utf-8"))
    rng = np.random.default_rng(2027)
    uids = d.uid.unique(); dob = dict(zip(uids, rng.integers(0, a.dobras, len(uids))))
    d["dobra"] = d.uid.map(dob)
    s, f, o = contagens(d); d["succ"], d["fail"], d["opp"] = s, f, o
    d["p_3pl"] = teto_3pl(d)
    preds = {k: np.full(len(d), np.nan) for k in ("Elo-3PL", "BKT", "Itens", "Itens + posição", "PFA", "3PL + posição")}
    extras = []
    for area, dA in d.groupby("area"):
        for k in range(a.dobras):
            tr, te = dA[dA.dobra != k], dA[dA.dobra == k]
            if te.empty or tr.empty:
                continue
            # Elo: K pela validação no treino
            Ks = [0.05, 0.1, 0.2, 0.3, 0.5, 0.8]
            Kb = min(Ks, key=lambda K: ll(tr.y.to_numpy(), elo(tr.reset_index(drop=True), K)))
            preds["Elo-3PL"][te.index] = elo(te.reset_index(drop=True), Kb)
            # BKT por célula (ano)
            for ano, teA in te.groupby("ano"):
                trA = tr[tr.ano == ano]
                if trA.empty:
                    continue
                prm = bkt_fit(seqs_por_hab(trA)[1])
                idx, ys = seqs_por_hab(teA)
                for ii, pp in zip(idx, bkt_pred(ys, prm)):
                    preds["BKT"][ii] = pp
            # PFA: efeitos de item (livres) + γs, γf
            itens = pd.Index(dA.item.unique())
            def X_pfa(z):
                M = np.zeros((len(z), len(itens) + 2)); M[np.arange(len(z)), itens.get_indexer(z.item)] = 1
                M[:, -2] = np.log1p(z.succ); M[:, -1] = np.log1p(z.fail); return M
            w = logit_fit(X_pfa(tr), tr.y.to_numpy(float), np.zeros(len(tr)), lam=1.0)
            preds["PFA"][te.index] = 1 / (1 + np.exp(-(X_pfa(te) @ w)))
            # linha de base dos agentes: só a dificuldade de cada item PARA os agentes (sem aprendizagem nem ordem)
            def X_it(z, pos=False):
                M = np.zeros((len(z), len(itens) + (1 if pos else 0))); M[np.arange(len(z)), itens.get_indexer(z.item)] = 1
                if pos: M[:, -1] = (z.pos_area.to_numpy(float) - 23) / 45
                return M
            wi = logit_fit(X_it(tr), tr.y.to_numpy(float), np.zeros(len(tr)), lam=1.0)
            preds["Itens"][te.index] = 1 / (1 + np.exp(-(X_it(te) @ wi)))
            wip = logit_fit(X_it(tr, True), tr.y.to_numpy(float), np.zeros(len(tr)), lam=1.0)
            preds["Itens + posição"][te.index] = 1 / (1 + np.exp(-(X_it(te, True) @ wip)))
            # 3PL + posição: offset = logit do teto 3PL
            off = lambda z: np.log(np.clip(z.p_3pl, 1e-4, 1 - 1e-4) / (1 - np.clip(z.p_3pl, 1e-4, 1 - 1e-4)))
            Xp = lambda z: ((z.pos_area.to_numpy(float) - 23) / 45)[:, None]
            wp = logit_fit(Xp(tr), tr.y.to_numpy(float), off(tr).to_numpy(), lam=0.0, nfree=1)
            preds["3PL + posição"][te.index] = 1 / (1 + np.exp(-(off(te).to_numpy() + Xp(te) @ wp)))
            extras.append(dict(area=area, dobra=k, K=Kb, gs=w[-2], gf=w[-1], delta_45=wp[0], delta_it=wip[-1]))
    for k, v in preds.items():
        d["p_" + k] = v
    # BKT p(T) por célula com todos os dados (descritivo, como no artigo)
    cel = []
    for (ano, area), g in d.groupby(["ano", "area"]):
        prm = bkt_fit(seqs_por_hab(g)[1])
        cel.append(dict(ano=ano, area=area, n=len(g), bkt_T=prm[1], bkt_L0=prm[0], bkt_G=prm[2], bkt_S=prm[3],
                        auc_3pl=auc(g.y, g.p_3pl)))
    cel = pd.DataFrame(cel); cel.to_csv(os.path.join(a.rodada, f"kt-celulas{suf}.csv"), index=False)
    ex = pd.DataFrame(extras)
    modelos = ["p_3pl", "p_3PL + posição", "p_Elo-3PL", "p_Itens", "p_Itens + posição", "p_PFA", "p_BKT"]
    nomes = ["3PL INEP", "3PL INEP + posição", "Elo-3PL", "Itens (agentes)", "Itens + posição", "PFA", "BKT"]
    L = ["# KT nas provas — " + cfg["cerebro"] + (" (só questões resolvidas, sem o relógio)" if suf else ""), "",
         f"Rodada {cfg['rodada']}; memória {cfg['memoria']}. Validação cruzada em {a.dobras} partes por candidato; 17 edições juntas por área.", "",
         "## Previsão (AUC / log-loss)", "", "| área | respostas | " + " | ".join(nomes) + " |", "|---|---|" + "---|" * len(nomes)]
    for area, g in d.groupby("area"):
        cells = []
        for m in modelos:
            ok = g[m].notna()
            cells.append(f"{auc(g.y[ok], g[m][ok]):.3f} / {ll(g.y[ok].to_numpy(), g[m][ok].to_numpy()):.3f}")
        L.append(f"| {area} | {len(g)} | " + " | ".join(cells) + " |")
    L += ["", "## Parâmetros de aprendizagem e de ordem", "",
          "| área | BKT p̂(T) mediana [células com p̂(T) ≥ 0,05] | PFA γ acertos / γ erros | ΔAUC PFA − Itens (aprendizagem) | δ posição sobre Itens (logit, 1ª→45ª) | ΔAUC posição − Itens | ΔAUC posição − 3PL INEP |",
          "|---|---|---|---|---|---|---|"]
    for area, g in d.groupby("area"):
        c = cel[cel.area == area]; e = ex[ex.area == area]
        A = lambda m: auc(g.y, g[m])
        L.append(f"| {area} | {c.bkt_T.median():.3f} [{(c.bkt_T >= 0.05).sum()}/{len(c)}] | {e.gs.mean():+.3f} / {e.gf.mean():+.3f} | "
                 f"{A('p_PFA') - A('p_Itens'):+.4f} | {e.delta_it.mean():+.3f} | {A('p_Itens + posição') - A('p_Itens'):+.4f} | {A('p_3PL + posição') - A('p_3pl'):+.4f} |")
    L += ["", "Leitura:",
          "- 3PL INEP usa os parâmetros calibrados nos candidatos; 'Itens (agentes)' estima a dificuldade de cada item PARA os agentes.",
          "  A diferença entre os dois mede o quanto a dificuldade dos agentes se afasta da humana.",
          "- Aprendizagem durante a prova: PFA e BKT só ganham de 'Itens' se o histórico de acertos e erros na habilidade ajudar a prever.",
          "  Sem aprendizagem: p̂(T) ≈ 0, γ acertos ≈ γ erros e ΔAUC PFA − Itens ≈ 0.",
          "- Ordem: δ < 0 = acerto cai ao longo da área; ΔAUC posição > 0 = a ordem acrescenta previsão além do item",
          "  (no artigo, o excesso dos modelos profundos sobre o teto 3PL mora na ordem dos itens).",
          "Detalhe por célula (ano × área): kt-celulas" + suf + ".csv."]
    open(os.path.join(a.rodada, f"KT{suf}.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
