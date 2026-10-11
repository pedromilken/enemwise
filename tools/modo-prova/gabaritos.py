"""Lê os gabaritos oficiais do caderno Amarelo. Saída: {"ano|numero|lingua": letra ou X (anulada)}."""
import re, sys, json, collections
from pathlib import Path
import pymupdf
from extrair_provas import extrair
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")   # Windows: saída redirecionada (| Select-String) usa cp1252

RESP = re.compile(r"^(?:[A-E]|anulad[oa]|x)$", re.I)

def ler(pdf: Path, ano: int, dia: int):
    doc = pymupdf.open(pdf)
    out = {}
    if len(doc) > 4:  # 2010: o "gabarito" é o caderno marcado
        return out
    for p in doc:
        ws = [w for w in p.get_text("words")]
        if not ws:
            continue
        txt = p.get_text().lower()
        if "amarel" not in txt:
            continue
        nums = [w for w in ws if re.fullmatch(r"\d{1,3}", w[4]) and 1 <= int(w[4]) <= 180]
        resps = [w for w in ws if RESP.match(w[4])]
        multi = len({w[4].lower() for w in ws if w[4].lower() in ("cinza", "azul", "rosa", "branco", "branca")}) >= 2
        nums.sort(key=lambda w: w[0])
        for w in nums:
            n = int(w[4]); yc = (w[1] + w[3]) / 2
            if (n, None) in out or (n, "ingles") in out:
                continue
            cand = sorted([r for r in resps if r[0] > w[2] - 1 and r[0] - w[2] < 170 and abs((r[1] + r[3]) / 2 - yc) < 4],
                          key=lambda r: r[0])
            # para no próximo número da mesma linha
            prox = [v[0] for v in nums if v is not w and v[0] > w[2] and abs((v[1] + v[3]) / 2 - yc) < 4]
            if prox:
                cand = [r for r in cand if r[0] < min(prox)]
            if not cand:
                continue
            norm = lambda r: "X" if len(r) > 1 or r.upper() == "X" else r.upper()
            if len(cand) >= 2 and not multi:
                out[(n, "ingles")] = norm(cand[0][4]); out[(n, "espanhol")] = norm(cand[1][4])
            else:
                out[(n, None)] = norm(cand[0][4])
    return out
    for p in doc:
        ws = [w for w in p.get_text("words")]
        if not ws:
            continue
        txt = p.get_text().lower()
        if "amarel" not in txt:
            continue
        # linhas pela altura
        ws.sort(key=lambda w: (round((w[1] + w[3]) / 2 / 3), w[0]))
        linhas = collections.defaultdict(list)
        for w in ws:
            linhas[round((w[1] + w[3]) / 2 / 3)].append(w)
        # colunas do Amarelo: x do cabeçalho "Amarelo" quando houver várias cores (2009)
        xs_am = [w[0] for w in ws if w[4].lower().startswith("amarel")]
        multi = len({w[4].lower() for w in ws if w[4].lower() in ("cinza", "azul", "rosa", "branco", "branca")}) >= 2
        for k in sorted(linhas):
            L = sorted(linhas[k], key=lambda w: w[0])
            i = 0
            while i < len(L):
                t = L[i][4]
                if re.fullmatch(r"\d{1,3}", t) and 1 <= int(t) <= 180:
                    n = int(t); resp = []
                    j = i + 1
                    while j < len(L) and RESP.match(L[j][4]):
                        resp.append(L[j][4]); j += 1
                    if resp and (n, None) not in out and (n, "ingles") not in out:
                        norm = lambda r: "X" if len(r) > 1 or r.upper() == "X" else r.upper()
                        if len(resp) == 2 and not multi:
                            out[(n, "ingles")] = norm(resp[0]); out[(n, "espanhol")] = norm(resp[1])
                        else:
                            out[(n, None)] = norm(resp[0])
                    i = j if j > i + 1 else i + 1
                else:
                    i += 1
    return out


# ---- 2010: o "gabarito" oficial é o caderno com a alternativa certa circulada ----
def verde(c): return c and c[1] > 0.45 and c[0] < 0.3

def ler_marcado(pdf: Path, ano=2010, dia=1):
    qs = extrair(pdf, ano, dia)       # recortes no próprio caderno marcado
    doc = pymupdf.open(pdf); out = {}
    for pi, p in enumerate(doc):
        dr = p.get_drawings()
        greens = [d["rect"] for d in dr if verde(d.get("color")) and 10 <= d["rect"].width <= 25]
        if not greens: continue
        circ = [d["rect"] for d in dr if 5.5 <= d["rect"].width <= 8.5 and 5.5 <= d["rect"].height <= 8.5]
        for g in greens:
            cx, cy = (g.x0 + g.x1) / 2, (g.y0 + g.y1) / 2
            for q in qs:
                for k, r in enumerate(q["recortes"]):
                    x0, y0, x1, y1 = r["bbox"]
                    if r["pagina"] != pi + 1 or not (x0 - 15 <= cx <= x1 + 15 and y0 - 5 <= cy <= y1 + 5): continue
                    ys = []
                    for c in sorted(circ, key=lambda c: c.y0):
                        if abs((c.x0 + c.x1) / 2 - cx) < 6 and y0 - 5 <= c.y0 <= y1 + 5 and not any(abs(c.y0 - y) < 4 for y in ys):
                            ys.append(c.y0)
                    ys = ys[-5:] if len(ys) > 5 else ys
                    if not ys: continue
                    i = min(range(len(ys)), key=lambda j: abs(ys[j] + 3.5 - cy))
                    if abs(ys[i] + 3.5 - cy) > 8: continue
                    if len(ys) < 5 and k > 0: i += 5 - len(ys)
                    out[(q["numero"], q["lang"])] = "ABCDE"[i]
    return out



def ler_todos(raiz: Path, log=sys.stderr) -> dict:
    res = {}
    for d in sorted(raiz.iterdir()):
        if not d.name.isdigit():
            continue
        for dia in (1, 2):
            f = d / f"D{dia}_gabarito.pdf"
            if not f.exists():
                continue
            g = ler(f, int(d.name), dia)
            if not g:  # caderno marcado (2010)
                g = ler_marcado(f, int(d.name), dia)
            exp = range(1, 91) if dia == 1 else range(91, 181)
            falta = sorted(set(exp) - {n for n, _ in g})
            print(f"gabarito {d.name} D{dia}: {len(g)} respostas" + (f", faltam {falta[:8]}" if falta else ""), file=log)
            for (n, l), v in g.items():
                res[f"{d.name}|{n}|{l or ''}"] = v
    return res
