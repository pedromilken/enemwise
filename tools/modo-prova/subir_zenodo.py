"""Envia arquivos ao Zenodo SEM publicar. A publicação (registra o DOI e trava os arquivos) é feita por você na página.

Uso (token em $env:ZENODO_TOKEN, escopos deposit:write e deposit:actions):
  python tools/modo-prova/subir_zenodo.py --rascunho 22166455          # ACRESCENTA ao seu rascunho (DOI reservado)
  python tools/modo-prova/subir_zenodo.py                               # cria um registro novo (rascunho)
  python tools/modo-prova/subir_zenodo.py --nova-versao-de 1234567      # nova versão de um registro já publicado
  python tools/modo-prova/subir_zenodo.py --pasta zenodo-confounds --rascunho 22166455   # outro pacote, mesmo registro
  --sandbox  testa em sandbox.zenodo.org (token do sandbox)

No rascunho existente, os metadados (título, descrição, autores) NÃO são alterados: o script grava em
<pasta>/descricao-sugerida.html o trecho a colar na descrição. Arquivos com o mesmo nome não são sobrescritos sem --substituir.
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
    ap.add_argument("--rascunho", help="id do rascunho existente (o número do DOI reservado: 10.5281/zenodo.<id>)")
    ap.add_argument("--nova-versao-de", help="id de um registro já publicado: cria a próxima versão dele")
    ap.add_argument("--substituir", action="store_true", help="no rascunho existente, troca arquivos de mesmo nome")
    a = ap.parse_args()
    tok = os.environ.get("ZENODO_TOKEN")
    if not tok:
        sys.exit("defina $env:ZENODO_TOKEN (Zenodo > Applications > Personal access tokens)")
    base = "https://sandbox.zenodo.org/api" if a.sandbox else "https://zenodo.org/api"
    S = requests.Session(); S.headers["Authorization"] = f"Bearer {tok}"
    mf = os.path.join(a.pasta, "zenodo.json")
    meta = json.load(open(mf, encoding="utf-8")) if os.path.exists(mf) else None
    arquivos = sorted(f for f in os.listdir(a.pasta) if f not in ("zenodo.json", "descricao-sugerida.html")
                      and os.path.isfile(os.path.join(a.pasta, f)))
    if not arquivos:
        sys.exit(f"pasta {a.pasta} vazia")

    def ok(r, o):
        if r.status_code >= 400:
            sys.exit(f"{o} falhou ({r.status_code}): {r.text[:500]}")
        return r.json() if r.content else {}

    if a.rascunho:
        dep = ok(S.get(f"{base}/deposit/depositions/{a.rascunho}"), "abrir rascunho")
        if dep.get("submitted"):
            sys.exit("esse registro já foi publicado: use --nova-versao-de " + str(a.rascunho))
        existentes = {f["filename"]: f["id"] for f in dep.get("files", [])}
        repetidos = [f for f in arquivos if f in existentes]
        if repetidos and not a.substituir:
            sys.exit("já existem no rascunho: " + ", ".join(repetidos) + " (use --substituir para trocar)")
        for f in repetidos:
            ok(S.delete(f"{base}/deposit/depositions/{dep['id']}/files/{existentes[f]}"), f"remover {f} antigo")
        print(f"Rascunho {dep['id']}: \"{dep['metadata'].get('title', '')}\" ({len(existentes)} arquivo(s) já presentes)")
    elif a.nova_versao_de:
        d = ok(S.post(f"{base}/deposit/depositions/{a.nova_versao_de}/actions/newversion"), "nova versão")
        dep = ok(S.get(d["links"]["latest_draft"]), "abrir rascunho")
        for f in dep.get("files", []):
            ok(S.delete(f"{base}/deposit/depositions/{dep['id']}/files/{f['id']}"), "limpar arquivo herdado")
    else:
        dep = ok(S.post(f"{base}/deposit/depositions", json={}), "criar rascunho")

    bucket = dep["links"]["bucket"]
    for f in arquivos:
        p = os.path.join(a.pasta, f)
        print(f"enviando {f} ({os.path.getsize(p) / 1e6:.1f} MB)…", flush=True)
        with open(p, "rb") as x:
            ok(S.put(f"{bucket}/{f}", data=x), f"envio de {f}")

    if a.rascunho:
        if meta:
            open(os.path.join(a.pasta, "descricao-sugerida.html"), "w", encoding="utf-8").write(meta["metadata"]["description"])
            print(f"\nMetadados do rascunho mantidos. Trecho sugerido para a descrição: {os.path.join(a.pasta, 'descricao-sugerida.html')}")
    elif meta:
        ok(S.put(f"{base}/deposit/depositions/{dep['id']}", json=meta), "metadados")
    html = dep["links"].get("html") or f"{base.replace('/api', '')}/deposit/{dep['id']}"
    print(f"\n{len(arquivos)} arquivo(s) no rascunho {dep['id']}. Revise e publique em:\n  {html}")


if __name__ == "__main__":
    main()
