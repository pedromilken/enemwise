"""Completa as questões que o PDF não entrega em texto, com um modelo de visão local (Ollama).

Duas tarefas, conforme `precisa_visao` de cada questão:
  descrever   figura ou gráfico: descrição objetiva com os dados necessários para responder
  transcrever fórmula quebrada, alternativas em imagem, texto ilegível ou alternativas não achadas:
              enunciado + 5 alternativas + figuras, a partir da imagem da questão
O modelo NÃO resolve a questão: a instrução proíbe indicar a resposta.

Cache retomável em <saida>/visao-cache.jsonl (chave = modelo + versão do pedido + bytes das imagens).

Uso:
  ollama pull qwen2.5vl:7b
  python descrever_figuras.py --dados dados --recortes dados/recortes [--modelo qwen2.5vl:7b] [--limite 20]
Saída: dados/provas-inep-visao.jsonl e dados/provas-inep-espanhol-visao.jsonl (use estas no `enemwise batch --questoes`).
"""
import argparse, base64, hashlib, json, os, re, sys, time, urllib.request
from pathlib import Path
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")   # Windows: saída redirecionada (| Select-String) usa cp1252


def jsonl(r):
    """Uma linha JSON por registro, escapando separadores de linha Unicode (o splitlines() do Python quebraria neles)."""
    s = json.dumps(r, ensure_ascii=False)
    for ch in ("\u2028", "\u2029", "\x85", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"):
        s = s.replace(ch, "\\u%04x" % ord(ch))
    return s

VERSAO = "v1"
TRANSCREVER = {"formula", "sem_alternativas", "ilegivel", "alternativas_figura"}

P_DESCREVER = """Você recebe a imagem de uma questão do ENEM. Descreva, em português, cada figura, gráfico, tabela, mapa ou charge
que aparece nela, de forma objetiva e completa: tipo de figura, títulos, eixos e unidades, valores e rótulos legíveis,
tendências, elementos visuais e textos dentro da imagem. Quem ler a descrição precisa ter a mesma informação de quem vê a figura.
NÃO resolva a questão e NÃO indique qual alternativa é correta.
Responda só com JSON: {"figuras": ["descrição da figura 1", "descrição da figura 2", ...]}"""

P_TRANSCREVER = """Você recebe a imagem de uma questão do ENEM (pode estar em mais de um recorte, em ordem).
Transcreva a questão em português, fiel ao original:
- "enunciado": todo o texto antes das alternativas; fórmulas em texto simples (ex.: x^2, raiz(3), 3/4, 10^-3, delta_H).
- "alternativas": exatamente 5 itens, A a E, sem a letra; se a alternativa for uma figura ou gráfico, descreva-a por completo.
- "figuras": descrição objetiva de cada figura, gráfico ou tabela do enunciado, com valores e rótulos.
NÃO resolva a questão e NÃO indique qual alternativa é correta.
Texto extraído do PDF (pode ter fórmulas quebradas; use só como apoio):
---
{texto}
---
Responda só com JSON: {{"enunciado": "...", "alternativas": ["...", "...", "...", "...", "..."], "figuras": ["..."]}}"""


def chamar(modelo, prompt, imagens, host, ctx):
    body = {"model": modelo, "stream": False, "format": "json",
            "options": {"temperature": 0, "num_ctx": ctx},
            "messages": [{"role": "user", "content": prompt, "images": imagens}]}
    req = urllib.request.Request(host.rstrip("/") + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]


def reduzir(png):
    import pymupdf
    pix = pymupdf.Pixmap(str(png))
    pix.shrink(1)  # metade da largura e da altura
    return base64.b64encode(pix.tobytes("png")).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", required=True, help="pasta com provas-inep.jsonl")
    ap.add_argument("--recortes", required=True)
    ap.add_argument("--modelo", default="qwen2.5vl:7b")
    ap.add_argument("--host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--limite", type=int, help="processa só N questões pendentes (para medir o tempo)")
    a = ap.parse_args()
    dados, rec = Path(a.dados), Path(a.recortes)
    cache_p = dados / "visao-cache.jsonl"
    cache = {}
    if cache_p.exists():
        for l in cache_p.read_text(encoding="utf-8").split("\n"):
            if l.strip():
                d = json.loads(l); cache[d["chave"]] = d
    fc = cache_p.open("a", encoding="utf-8")
    feitos = novos = falhas = 0
    t0 = time.time()
    for nome in ("provas-inep", "provas-inep-espanhol"):
        src = dados / f"{nome}.jsonl"
        if not src.exists():
            continue
        regs = [json.loads(l) for l in src.read_text(encoding="utf-8").split("\n") if l.strip()]
        for r in regs:
            pv = set(r.get("precisa_visao") or [])
            if not pv:
                continue
            ano, num = r["id"].split("_")
            sfx = f"_{r['lingua'][:2]}" if r.get("lingua") else ""
            pngs = sorted(rec.glob(f"{ano}_{int(num):03d}{sfx}_*.png"))
            if not pngs:
                r.setdefault("visao", {"erro": "sem recorte"}); continue
            imgs = [base64.b64encode(p.read_bytes()).decode() for p in pngs]
            tarefa = "transcrever" if pv & TRANSCREVER else "descrever"
            prompt = P_TRANSCREVER.format(texto=(r["question"] + "\n" + "\n".join(r["alternatives"] or []))[:6000]) if tarefa == "transcrever" else P_DESCREVER
            chave = hashlib.sha256((a.modelo + VERSAO + tarefa + "".join(imgs)).encode()).hexdigest()
            if chave not in cache:
                if a.limite is not None and novos >= a.limite:
                    continue
                try:
                    try:
                        txt = chamar(a.modelo, prompt, imgs, a.host, a.ctx)
                    except Exception:
                        # erro 500/400 costuma ser imagem grande demais para a memória: tenta de novo com metade da resolução
                        txt = chamar(a.modelo, prompt, [reduzir(p) for p in pngs], a.host, a.ctx)
                    d = {"chave": chave, "id": r["id"], "lingua": r.get("lingua"), "tarefa": tarefa, "modelo": a.modelo, "resposta": txt}
                except Exception as e:
                    falhas += 1
                    print(f"  falha {r['id']}: {e}", file=sys.stderr)
                    continue
                cache[chave] = d; fc.write(json.dumps(d, ensure_ascii=False) + "\n"); fc.flush()
                novos += 1
                if novos % 10 == 0:
                    print(f"  {novos} novas ({(time.time() - t0) / novos:.1f} s/questão)", file=sys.stderr)
            try:
                out = json.loads(re.sub(r"^```(json)?|```$", "", cache[chave]["resposta"].strip()))
            except Exception:
                r["visao"] = {"tarefa": tarefa, "erro": "json inválido"}; continue
            figs = [str(x) for x in (out.get("figuras") or []) if str(x).strip()]
            r["description"] = figs
            r["visao"] = {"tarefa": tarefa, "modelo": a.modelo, "versao": VERSAO}
            if tarefa == "transcrever":
                alts = out.get("alternativas") or []
                if isinstance(alts, list) and len(alts) == 5 and all(str(x).strip() for x in alts):
                    r["alternatives_pdf"] = r["alternatives"]
                    r["alternatives"] = [re.sub(r"^\(?[A-E][).:]\s*", "", str(x)).strip() for x in alts]
                    if str(out.get("enunciado", "")).strip():
                        r["question_pdf"] = r["question"]; r["question"] = str(out["enunciado"]).strip()
                else:
                    r["visao"]["erro"] = "transcrição sem 5 alternativas"
            feitos += 1
        dst = dados / f"{nome}-visao.jsonl"
        dst.write_text("\n".join(jsonl(r) for r in regs) + "\n", encoding="utf-8")
        semalt = sum(1 for r in regs if not r.get("alternatives"))
        print(f"{dst.name}: {len(regs)} questões; {semalt} ainda sem alternativas", file=sys.stderr)
    print(f"visão: {feitos} questões completadas ({novos} chamadas novas, {falhas} falhas)", file=sys.stderr)


if __name__ == "__main__":
    main()
