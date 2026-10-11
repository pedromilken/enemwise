"""Extrai as questões dos cadernos oficiais do ENEM (PDF do INEP) para JSONL.

Saída compatível com link_text.load_questions (id "ANO_NUM", alternatives, label...).
Cada questão também guarda os recortes de página onde está, para descrever figuras depois.

Uso: python extrair_provas.py <pasta provas-inep> <saida.jsonl> [--recortes pasta] [--anos 2009 2023]
"""
from __future__ import annotations

import argparse, json, re, sys, unicodedata
from pathlib import Path

import pymupdf
from fontTools import agl
from fontTools.ttLib.standardGlyphOrder import standardGlyphOrder as MAC

# Fontes embutidas sem tabela de caracteres: o PDF guarda o índice do glifo (ordem padrão Mac).
def decodifica(t: str) -> str:
    o = []
    for ch in t:
        g = ord(ch)
        if ch == " ":
            o.append(" "); continue
        g = g if g < 128 else g + 1
        o.append(agl.toUnicode(MAC[g]) if g < len(MAC) else ch)
    return "".join(o)


def _minusc(t):
    L = [c for c in t if c.isalpha()]
    return sum(c.islower() for c in L) / len(L) if L else 1.0


def texto_span(s, fontes_ruins) -> str:
    t = s["text"]
    if "\x03" in t:
        return decodifica(t)
    if s["font"] in fontes_ruins and len(t.strip()) >= 4 and _minusc(t) < 0.5:
        d = decodifica(t)
        if _minusc(d) > 0.8:
            return d
    return t

HDR = re.compile(r"^\s*QUEST[ÃA]O\s*[\t ]*\n?\s*(\d{1,3})\s*$", re.I | re.M)
LANG = re.compile(r"op[çc][ãa]o:?\s*(ingl[êe]s|espanhol)", re.I)
OPT = re.compile(r"^\s*([A-E])(?:\t| {1,3})", re.M)
RODAPE = re.compile(r"(CADERNO\s*\d|P[ÁA]GINA\s*\d|\*[A-Z0-9]{6,}\*|^\s*ENEM\s*20\d\d\s*$|^\s*\d{1,2}\s*$)", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).replace(" ", " ").replace("\xa0", " ")
    s = re.sub(r"[ \t]+\n", "\n", s)
    return s


def suspeito(t: str) -> float:
    """Fração de palavras ilegíveis (fonte sem tabela de caracteres)."""
    ws = re.findall(r"\S{3,}", t)
    if not ws:
        return 0.0
    bad = sum(1 for w in ws if re.search(r"[¿¾½¼»«¶µ³²]|[A-Z0-9]{2,}[a-z]?[A-Z]{2,}", w) and not re.match(r"^[A-Z0-9\-\.,;:()]+$", w))
    return bad / len(ws)


def formula(t: str) -> bool:
    """Fórmula achatada pela extração: muitos tokens de um caractere ou símbolos soltos."""
    tk = t.split()
    if len(tk) < 8:
        return False
    um = sum(1 for w in tk if len(w) == 1 and w not in "aeoAEOéàÀ")
    return um / len(tk) > 0.12 or bool(re.search(r"[⋅∙√∑∫≤≥≠∆Δπ]|\(\s*\)", t))


def fluxo(doc):
    """Blocos em ordem de leitura: página, coluna (esq./dir.), y."""
    out = []
    ruins = {s["font"] for p in doc for b in p.get_text("dict")["blocks"] for l in b.get("lines", [])
             for s in l["spans"] if "\x03" in s["text"]}
    for pi, p in enumerate(doc):
        W, H = p.rect.width, p.rect.height
        meio = W / 2
        for b in p.get_text("dict")["blocks"]:
            x0, y0, x1, y1 = b["bbox"]
            if y1 < H * 0.04 or y0 > H * 0.958 or (b["type"] == 0 and x1 - x0 < 10 and y1 - y0 > 100):
                continue
            col = 0 if (x0 + x1) / 2 < meio else 1
            if x1 - x0 > W * 0.6:  # bloco de largura total (título de seção)
                col = 0
            if b["type"] == 1:
                if (x1 - x0) > 25 and (y1 - y0) > 25:
                    out.append(dict(p=pi, c=col, y=y0, bb=(x0, y0, x1, y1), img=True, t=""))
                continue
            linhas = ["".join(texto_span(s, ruins) for s in l["spans"]) for l in b["lines"]]
            t = "\n".join(linhas)
            t = re.sub(r"(?:ENEM ?20\d\d ?){3,}\S*", "", t)  # marca-d'água
            if not t.strip() or (RODAPE.search(t) and len(t) < 120):
                continue
            out.append(dict(p=pi, c=col, y=y0, bb=(x0, y0, x1, y1), img=False, t=t))
    out.sort(key=lambda r: (r["p"], r["c"], r["y"]))
    return out


def desenhos(doc):
    """Áreas com gráficos vetoriais (muitos traços) por página."""
    res = {}
    for pi, p in enumerate(doc):
        rs = [d["rect"] for d in p.get_drawings() if d["rect"].width > 2 or d["rect"].height > 2]
        res[pi] = rs
    return res


def opcoes(corpo: str):
    """Última sequência A..E em início de linha."""
    ms = list(OPT.finditer(corpo))
    if len({m.group(1) for m in ms}) < 5:  # 2010: letras são desenhos; a linha começa com tab
        tabs = [m.end() - 1 for m in re.finditer(r"^(?:[ ]*\t| (?=\S))", corpo, re.M)]
        if len(tabs) >= 5:
            for letra, pos in reversed(list(zip("ABCDE", tabs[-5:]))):
                corpo = corpo[:pos] + letra + ("" if corpo[pos] == "\t" else "\t") + corpo[pos + 1:]
            ms = list(OPT.finditer(corpo))
    pos, fim = {}, len(corpo)
    for letra in "EDCBA":
        cand = [m for m in ms if m.group(1) == letra and m.start() < fim]
        if not cand:
            return None, corpo
        m = cand[-1]
        pos[letra] = m
        fim = m.start()
    alts = []
    letras = "ABCDE"
    for i, l in enumerate(letras):
        ini = pos[l].end()
        fi = pos[letras[i + 1]].start() if i < 4 else len(corpo)
        a = re.sub(r"\s*\n\s*", " ", corpo[ini:fi]).strip()
        alts.append(a)
    # "A\t\nA\t texto": a primeira marca vazia sobra no enunciado
    enun = corpo[:pos["A"].start()]
    enun = re.sub(r"(?:\n\s*[A-E]\s*)+$", "", enun.rstrip())
    return alts, enun


def limpa_enunciado(t: str) -> str:
    linhas = [l.strip() for l in t.split("\n")]
    out, par = [], []
    for l in linhas:
        if not l:
            if par:
                out.append(" ".join(par)); par = []
            continue
        par.append(l)
    if par:
        out.append(" ".join(par))
    return "\n".join(out).strip()


def extrair(pdf: Path, ano: int, dia: int):
    doc = pymupdf.open(pdf)
    blocos = fluxo(doc)
    dw = desenhos(doc)
    qs, cur, lang = [], None, None
    for b in blocos:
        if not b["img"]:
            m = LANG.search(b["t"])
            if m:
                lang = "espanhol" if m.group(1).lower().startswith("esp") else "ingles"
        # um bloco pode conter o cabeçalho no meio
        partes = [b["t"]] if b["img"] else re.split(r"(?=^\s*QUEST[ÃA]O\s*[\t ]*\n?\s*\d{1,3}\s*$)", b["t"], flags=re.I | re.M)
        for parte in partes:
            m = None if b["img"] else HDR.match(parte) or HDR.search(parte[:40])
            if m and lang == "ingles" and int(m.group(1)) in (6, 96) and qs and qs[-1]["lang"] == "ingles":
                m = None  # cabeçalho espúrio dentro da seção de inglês (2022)
                parte = HDR.sub("", parte, count=1)
            if m:
                n = int(m.group(1))
                cur = dict(numero=n, lang=lang if n <= 5 or (90 < n <= 95) else None,
                           texto=[], img=0, seg={}, p0=b["p"])
                qs.append(cur)
                parte = parte[m.end():]
            if cur is None:
                continue
            k = (b["p"], b["c"])
            x0, y0, x1, y1 = b["bb"]
            s = cur["seg"].get(k)
            cur["seg"][k] = [min(s[0], x0), min(s[1], y0), max(s[2], x1), max(s[3], y1)] if s else [x0, y0, x1, y1]
            if b["img"]:
                cur["img"] += 1
            elif parte.strip():
                cur["texto"].append(parte)
    res, compart = [], {}
    SH = re.compile(r"Textos?\s+para\s+as\s+quest[õo]es\s+(\d+)\s*(?:e|a|,)\s*(\d+)[^\n]*", re.I)
    for q in qs:
        corpo = norm("\n".join(q["texto"]))
        m = SH.search(corpo)
        if m:
            for n in range(int(m.group(1)), int(m.group(2)) + 1):
                compart[n] = corpo[m.end():].strip()
            corpo = corpo[:m.start()]
        if q["numero"] in compart and not q.get("lang"):
            q["compartilhado"] = compart[q["numero"]]
        corpo = LANG.sub("", re.sub(r"Quest[õo]es\s+de\s+\d+\s+a\s+\d+\s*\([^)]*\)", "", corpo, flags=re.I))
        alts, enun = opcoes(corpo)
        vet = 0
        for (pi, c), bb in q["seg"].items():
            r = pymupdf.Rect(bb)
            vet += sum(1 for d in dw[pi] if r.intersects(d))
        res.append(dict(ano=ano, dia=dia, numero=q["numero"], lang=q["lang"],
                        enunciado=limpa_enunciado((q.get("compartilhado", "") + "\n\n" + enun).strip()),
                        texto_compartilhado=bool(q.get("compartilhado")), alternativas=alts,
                        n_img=q["img"], n_vetor=vet,
                        alternativas_figura=alts is None and bool(re.search(r"\bA\b.*\bB\b.*\bC\b.*\bD\b.*\bE\b", corpo[-400:], re.S)),
                        ilegivel=round(suspeito(corpo), 3),
                        formula=formula(corpo),
                        recortes=[dict(pagina=pi + 1, bbox=[round(v, 1) for v in bb]) for (pi, c), bb in sorted(q["seg"].items())]))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta"); ap.add_argument("saida")
    ap.add_argument("--anos", nargs="*", type=int)
    ap.add_argument("--recortes", help="pasta para PNG das questões com figura")
    a = ap.parse_args()
    raiz = Path(a.pasta)
    todos = []
    for d in sorted(raiz.iterdir()):
        if not d.name.isdigit() or (a.anos and int(d.name) not in a.anos):
            continue
        for dia in (1, 2):
            pdf = d / f"D{dia}_prova.pdf"
            if pdf.exists():
                qs = extrair(pdf, int(d.name), dia)
                todos += qs
                if a.recortes:
                    salvar_recortes(pdf, qs, Path(a.recortes))
    Path(a.saida).write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in todos) + "\n", encoding="utf-8")
    print(f"{len(todos)} questões -> {a.saida}", file=sys.stderr)


def salvar_recortes(pdf, qs, pasta: Path, todos=False):
    """PNG de cada trecho de página da questão (150 dpi): <ano>_<num>[_es|_in]_<k>.png"""
    doc = pymupdf.open(pdf)
    pasta.mkdir(parents=True, exist_ok=True)
    for q in qs:
        if not todos and not (q["n_img"] or q["n_vetor"] > 8):
            continue
        for i, r in enumerate(q["recortes"]):
            pix = doc[r["pagina"] - 1].get_pixmap(clip=pymupdf.Rect(r["bbox"]), dpi=150)
            sfx = f"_{q['lang'][:2]}" if q["lang"] else ""
            pix.save(pasta / f"{q['ano']}_{q['numero']:03d}{sfx}_{i}.png")


if __name__ == "__main__":
    main()
