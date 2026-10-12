"""Envia o pacote (pasta zenodo/) ao Zenodo como RASCUNHO. Não publica: a publicação (que gera o DOI e não pode ser
desfeita) é feita por você na página do rascunho, depois de revisar.

Uso (token em $env:ZENODO_TOKEN, escopos deposit:write e deposit:actions):
  python tools/modo-prova/subir_zenodo.py                         # novo registro
  python tools/modo-prova/subir_zenodo.py --nova-versao-de 1234567  # nova versão de um registro seu já publicado
  python tools/modo-prova/subir_zenodo.py --sandbox               # teste em sandbox.zenodo.org (token do sandbox)
"""
import argparse, json, os, sys
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
try:
    import requests
except ImportError:
    sys.exit("instale: python -m pip install requests")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default="zenodo")
    ap.add_argument("--sandbox", action="store_true")
    ap.add_argument("--nova-versao-de", help="id (número) de um registro já publicado: cria a próxima versão dele")
    a = ap.parse_args()
    tok = os.environ.get("ZENODO_TOKEN")
    if not tok:
        sys.exit("defina $env:ZENODO_TOKEN (Zenodo > Applications > Personal access tokens)")
    base = "https://sandbox.zenodo.org/api" if a.sandbox else "https://zenodo.org/api"
    S = requests.Session(); S.headers["Authorization"] = f"Bearer {tok}"
    meta = json.load(open(os.path.join(a.pasta, "zenodo.json"), encoding="utf-8"))
    arquivos = sorted(f for f in os.listdir(a.pasta) if f != "zenodo.json" and os.path.isfile(os.path.join(a.pasta, f)))
    if not arquivos:
        sys.exit(f"pasta {a.pasta} vazia: rode pacote_zenodo.py antes")

    def ok(r, o):
        if r.status_code >= 400:
            sys.exit(f"{o} falhou ({r.status_code}): {r.text[:500]}")
        return r.json() if r.content else {}

    if a.nova_versao_de:
        d = ok(S.post(f"{base}/deposit/depositions/{a.nova_versao_de}/actions/newversion"), "nova versão")
        dep = ok(S.get(d["links"]["latest_draft"]), "abrir rascunho")
        for f in dep.get("files", []):   # a nova versão herda os arquivos da anterior: substitui todos
            ok(S.delete(f"{base}/deposit/depositions/{dep['id']}/files/{f['id']}"), "limpar arquivo herdado")
    else:
        dep = ok(S.post(f"{base}/deposit/depositions", json={}), "criar rascunho")
    bucket = dep["links"]["bucket"]
    for f in arquivos:
        p = os.path.join(a.pasta, f)
        print(f"enviando {f} ({os.path.getsize(p) / 1e6:.1f} MB)…", flush=True)
        with open(p, "rb") as x:
            ok(S.put(f"{bucket}/{f}", data=x), f"envio de {f}")
    ok(S.put(f"{base}/deposit/depositions/{dep['id']}", json=meta), "metadados")
    html = dep["links"].get("html") or f"{base.replace('/api', '')}/deposit/{dep['id']}"
    print(f"\nRascunho {dep['id']} criado com {len(arquivos)} arquivos. Revise e publique em:\n  {html}")
    print("Antes de publicar: confira autores (adicione coautores se for o caso), licença e descrição.")


if __name__ == "__main__":
    main()
