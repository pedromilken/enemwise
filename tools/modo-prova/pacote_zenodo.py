"""Monta o pacote de reprodutibilidade do modo prova para o Zenodo (dados + código + ambiente + checksums).

Uso (na raiz do ENEMWise):
  python tools/modo-prova/pacote_zenodo.py                      # gera zenodo/ com os arquivos a subir

Arquivos gerados em zenodo/ (cada um vira um arquivo do registro):
  modo-prova-resultados.zip   rodadas completas (agentes, aleatório, nulos, persona) e laboratório (painel do jogo)
  modo-prova-dados.zip        cadernos de todas as cores, acerto real por item × posição, mapa da exportação v9.2
  modo-prova-codigo.zip       o repositório no commit usado (git archive)
  modo-prova-LEIA-ME.md, -TABELA1.md, -tabela1.csv, -ambiente.txt, -SHA256SUMS.txt e zenodo.json (metadados)
Todos os nomes começam com "modo-prova-" para conviver com outros arquivos no mesmo registro (ex.: os microdados).
Nada sai do computador: o envio é outro passo (subir_zenodo.py), que cria um RASCUNHO para revisão.
"""
import argparse, datetime, glob, hashlib, json, os, platform, re, shutil, subprocess, sys, zipfile
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

AQUI = os.path.dirname(os.path.abspath(__file__))


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout.strip()
    except Exception as e:  # ferramenta ausente
        return f"(indisponível: {e.__class__.__name__})"


def zipar(destino, itens, raiz="."):
    n = 0
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for it in itens:
            for f in sorted(glob.glob(it, recursive=True)):
                if os.path.isfile(f) and "__pycache__" not in f:
                    z.write(f, os.path.relpath(f, raiz)); n += 1
    return n


def sha256(f):
    h = hashlib.sha256()
    with open(f, "rb") as x:
        for b in iter(lambda: x.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="zenodo")
    ap.add_argument("--rodadas", default="agentes/saida")
    ap.add_argument("--incluir-pilotos", action="store_true")
    a = ap.parse_args()
    out = a.saida
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    commit = sh(["git", "rev-parse", "HEAD"]); curto = commit[:7]
    sujo = sh(["git", "status", "--porcelain", "--untracked-files=no"])

    # 1) resultados
    pastas = [p for p in sorted(glob.glob(os.path.join(a.rodadas, "prova-*")))
              if a.incluir_pilotos or "piloto" not in os.path.basename(p)]
    extras = [p for p in (os.path.join(a.rodadas, "painel-2026-10"), os.path.join(a.rodadas, "base")) if os.path.isdir(p)]
    n_res = zipar(os.path.join(out, "modo-prova-resultados.zip"),
                  [os.path.join(p, "**", "*") for p in pastas + extras] + [os.path.join(a.rodadas, "TABELA1.md"), os.path.join(a.rodadas, "tabela1.csv")],
                  raiz=os.path.dirname(a.rodadas.rstrip("/\\")) or ".")
    resumo = []
    for p in pastas:
        cfgf = os.path.join(p, "config.json")
        cfg = json.load(open(cfgf, encoding="utf-8")) if os.path.exists(cfgf) else {}
        n = sum(1 for _ in open(os.path.join(p, "respostas.jsonl"), encoding="utf-8")) if os.path.exists(os.path.join(p, "respostas.jsonl")) else 0
        resumo.append(f"| {os.path.basename(p)} | {cfg.get('cerebro', '-')} | {cfg.get('versao', '-')} | {cfg.get('memoria', '-')} | {cfg.get('persona', 'nenhuma')} | {n} |")

    # 2) dados (o mapa v9.2 vai sem o caminho local)
    tmp = os.path.join(out, "_tmp"); os.makedirs(tmp)
    v92 = "pipeline/v92.json"
    if os.path.exists(v92):
        d = json.load(open(v92, encoding="utf-8-sig"))
        d["caminho"] = re.sub(r"^.*?(results_v9_)", r"<pasta da exportação v9.2>/\1", d["caminho"].replace("\\", "/"))
        json.dump(d, open(os.path.join(tmp, "v92.exemplo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    dados = ["dados/cadernos.json", "dados/acerto_real.csv", "tools/modo-prova/cronograma.json", os.path.join(tmp, "v92.exemplo.json")]
    n_dados = 0
    with zipfile.ZipFile(os.path.join(out, "modo-prova-dados.zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for it in dados:
            for f in glob.glob(it):
                z.write(f, "dados/" + os.path.basename(f)); n_dados += 1
    shutil.rmtree(tmp)
    faltam = [f for f in ("dados/cadernos.json", "dados/acerto_real.csv") if not os.path.exists(f)]

    # 3) código no commit
    cod = os.path.join(out, "modo-prova-codigo.zip")
    r = subprocess.run(["git", "archive", "--format=zip", "-o", cod, "HEAD"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("git archive falhou: " + r.stderr)

    # 4) ambiente
    amb = ["# Ambiente da execução", f"gerado em {datetime.datetime.now().isoformat(timespec='seconds')}", f"commit {commit}" + (" (com alterações locais!)" if sujo else ""),
           f"sistema: {platform.platform()}", f"python {platform.python_version()}", "node " + sh(["node", "--version"]),
           "", "## pacotes Python", sh([sys.executable, "-m", "pip", "freeze"]),
           "", "## modelos Ollama (nome, digest)", sh(["ollama", "list"])]
    gpu = sh(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    amb += ["", "## GPU", gpu]
    open(os.path.join(out, "modo-prova-ambiente.txt"), "w", encoding="utf-8").write("\n".join(amb) + "\n")

    for f in ("TABELA1.md", "tabela1.csv"):
        if os.path.exists(os.path.join(a.rodadas, f)):
            shutil.copy(os.path.join(a.rodadas, f), os.path.join(out, "modo-prova-" + f))

    # 5) LEIA-ME do pacote
    leia = open(os.path.join(AQUI, "LEIA-ME-zenodo.md"), encoding="utf-8").read()
    leia = leia.replace("{{COMMIT}}", commit).replace("{{DATA}}", datetime.date.today().isoformat()) \
               .replace("{{RODADAS}}", "\n".join(["| pasta | cérebro | versão do motor | memória | persona | provas-dia |", "|---|---|---|---|---|---|"] + resumo)) \
               .replace("{{TEXTOS}}", "in `modo-prova-codigo.zip` (`dados/provas-inep*.jsonl`, `web/public/data/prova`), as in the public repository; "
                        "they can be regenerated from the official INEP PDFs with `baixar-provas-enem.ps1` and `rodar-prova.ps1 -Etapa preparar`")
    open(os.path.join(out, "modo-prova-LEIA-ME.md"), "w", encoding="utf-8").write(leia)

    meta = json.load(open(os.path.join(AQUI, "zenodo.json"), encoding="utf-8"))
    meta["metadata"]["version"] = f"modo-prova {curto}"
    meta["metadata"]["publication_date"] = datetime.date.today().isoformat()
    json.dump(meta, open(os.path.join(out, "zenodo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    with open(os.path.join(out, "modo-prova-SHA256SUMS.txt"), "w", encoding="utf-8") as h:
        for f in sorted(os.listdir(out)):
            if f not in ("modo-prova-SHA256SUMS.txt", "zenodo.json"):
                h.write(f"{sha256(os.path.join(out, f))}  {f}\n")
    tam = sum(os.path.getsize(os.path.join(out, f)) for f in os.listdir(out)) / 1e6
    print(f"Pacote em {out}/ ({tam:.0f} MB): {len(pastas)} rodadas ({n_res} arquivos), {n_dados} arquivos de dados, código no commit {curto}.")
    if sujo:
        print("ATENÇÃO: há alterações locais não commitadas; o zip de código traz só o commit. Faça commit/push antes de subir.")
    if faltam:
        print("ATENÇÃO: faltam " + ", ".join(faltam))
    if not glob.glob(os.path.join(a.rodadas, "prova-*persona*")):
        print("Aviso: nenhuma rodada de persona encontrada (pendência do pôster).")


if __name__ == "__main__":
    main()
