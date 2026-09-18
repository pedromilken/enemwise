from __future__ import annotations

import argparse
import json
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from . import avaliacao, benchmark, bloom, conteudos, dataset, datasheet, inep, leitura, link_text, longo, merge as mrg, resolucoes, synth
from .edicao import build_edition


def _anos(spec: str) -> list[int]:
    out = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    return out


def _longos(long_dir: str | None, ano: int) -> dict[str, Path]:
    if not long_dir:
        return {}
    found = {}
    for area in ("CN", "CH", "LC", "MT"):
        for ext in ("parquet", "csv"):
            p = Path(long_dir) / f"{ano}_{area}.{ext}"
            if p.exists():
                found[area] = p
    return found


def _load_all_questions(paths: list[str]) -> list[pd.DataFrame]:
    dfs = []
    for p in paths:
        df = link_text.load_questions(p)
        print(f"texto: {Path(p).name} -> {len(df)} questões, edições {sorted(df['ano'].unique().tolist())}", file=sys.stderr)
        dfs.append(df)
    return dfs


def _one(ano, raiz, out, questoes_paths, long_dir, lingua, nrows, longo_config=None):
    itens = leitura.find_file(raiz, "ITENS_PROVA", ano)
    micro = leitura.find_microdados(raiz, ano)
    if itens is None:
        return ano, {"erro": "ITENS_PROVA não encontrado"}
    try:
        cfg = longo.ConfigLongo.ler(longo_config) if longo_config else None
        rel = build_edition(ano, itens, micro, Path(out) / str(ano), _load_all_questions(questoes_paths),
                            _longos(long_dir, ano), lingua=lingua, nrows=nrows, longo_cfg=cfg)
        reprov = [f'{a["area"]}' for a in rel["auditoria"] if a.get("ok") is False]
        return ano, {"ok": True, "itens_com_texto": rel["itens_com_texto"], "auditoria_reprovada": reprov,
                     "segundos": rel["segundos"]}
    except Exception as e:  # uma edição quebrada não derruba as outras
        return ano, {"erro": f"{type(e).__name__}: {e}", "trace": traceback.format_exc(limit=3)}


def batch(args) -> dict:
    anos = _anos(args.anos)
    status = {}
    if args.jobs > 1:
        with ProcessPoolExecutor(args.jobs) as ex:
            futs = [ex.submit(_one, a, args.raiz, args.out, args.questoes, args.long_dir, args.lingua, args.nrows, getattr(args, "longo_config", None)) for a in anos]
            for f in as_completed(futs):
                ano, st = f.result()
                status[ano] = st
                print(f"[{ano}] {st}", file=sys.stderr)
    else:
        for a in anos:
            ano, st = _one(a, args.raiz, args.out, args.questoes, args.long_dir, args.lingua, args.nrows, getattr(args, "longo_config", None))
            status[ano] = st
            print(f"[{ano}] {st}", file=sys.stderr)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "batch_status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return status


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):  # console do Windows e redirecionamento em cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="enemwise")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synth", help="gera microdados sintéticos de 3 edições")
    s.add_argument("--out", required=True)
    s.add_argument("--n", type=int, default=8000)

    b = sub.add_parser("batch", help="processa várias edições encontrando os arquivos sozinho")
    b.add_argument("--raiz", required=True, help="pasta com os zips do INEP já extraídos")
    b.add_argument("--anos", default="2009-2025", help='ex.: "2009-2025" ou "2009-2016,2022"')
    b.add_argument("--questoes", nargs="*", default=[], help="fontes de texto, em ordem de prioridade")
    b.add_argument("--long-dir", help="pasta com <ano>_<AREA>.parquet|csv (co_item, correct, nota)")
    b.add_argument("--longo-config", help="mapeamento JSON da exportação longa v9.2: usa ela nas quatro áreas")
    b.add_argument("--lingua", type=int, default=0)
    b.add_argument("--nrows", type=int, help="limita linhas por edição (ensaio rápido)")
    b.add_argument("--jobs", type=int, default=1, help="edições em paralelo (cada uma usa ~2 GB)")
    b.add_argument("--out", required=True)

    m = sub.add_parser("merge", help="junta as edições no pacote do app")
    m.add_argument("--entrada", required=True)
    m.add_argument("--web", required=True)
    m.add_argument("--D", type=float, default=1.0)
    m.add_argument("--sintetico", action="store_true")
    m.add_argument("--incluir-reprovadas", action="store_true", help="usa nos priors células reprovadas na auditoria")

    av = sub.add_parser("avaliar", help="métricas prequenciais a partir das exportações dos estudantes")
    av.add_argument("--exportacoes", required=True, help="pasta com os .json exportados")
    av.add_argument("--incluir-dica", action="store_true")
    av.add_argument("--saida")

    ct = sub.add_parser("conteudos", help="audita a classificação por conteúdo programático das questões")
    ct.add_argument("--entrada", required=True, help="pasta do batch (com <ano>/items_full.json) ou pasta data do app")
    ct.add_argument("--topico", help="mostra exemplos de um tópico (id do catálogo)")
    ct.add_argument("--amostra", type=int, default=5)

    rs = sub.add_parser("resolucoes", help="gera resoluções comentadas com a API da Anthropic (cache retomável)")
    rs.add_argument("--entrada", required=True, help="pasta do batch (com <ano>/items_full.json)")
    rs.add_argument("--cache", default=None, help="arquivo de cache (padrão: <entrada>/resolucoes.json)")
    rs.add_argument("--chave", default=None, help="chave da API; ou defina ANTHROPIC_API_KEY")
    rs.add_argument("--modelo", default=resolucoes.MODELO_PADRAO)
    rs.add_argument("--limite", type=int, default=None, help="gera só as N primeiras pendentes (para testar o custo)")

    bl = sub.add_parser("bloom", help="CSV (chave, descricao[, bloom]) -> habilidades.json com nível sugerido")
    bl.add_argument("--entrada", required=True)
    bl.add_argument("--saida", required=True)

    dl = sub.add_parser("baixar", help="baixa os microdados do INEP, grava manifesto e extrai só o necessário")
    dl.add_argument("--anos", default="2009-2025")
    dl.add_argument("--destino", required=True)
    dl.add_argument("--sem-provas", action="store_true", help="não extrai os PDFs das provas")
    dl.add_argument("--manter-zip", action="store_true")

    vf = sub.add_parser("verificar", help="checa se zips já baixados são anteriores às correções do INEP")
    vf.add_argument("--raiz", required=True)

    dt = sub.add_parser("dataset", help="exporta os microdados como dataset de Knowledge Tracing")
    dt.add_argument("--raiz", required=True)
    dt.add_argument("--anos", default="2009-2025")
    dt.add_argument("--fracao", type=float, default=0.01, help="fração de participantes por edição (1.0 = todos)")
    dt.add_argument("--seed", type=int, default=0)
    dt.add_argument("--lingua", type=int, default=0)
    dt.add_argument("--nrows", type=int)
    dt.add_argument("--out", required=True)

    pk = sub.add_parser("dataset-pykt", help="gera data.txt no formato do pyKT")
    pk.add_argument("--dataset", required=True)
    pk.add_argument("--nome", required=True)
    pk.add_argument("--anos")
    pk.add_argument("--areas", nargs="*")

    bm = sub.add_parser("dataset-benchmark", help="linhas de base prequenciais e teste de falsificação")
    bm.add_argument("--dataset", required=True)
    bm.add_argument("--ano", type=int, required=True)
    bm.add_argument("--area", required=True)
    bm.add_argument("--max-estudantes", type=int, default=20000)
    bm.add_argument("--permutacoes", type=int, default=5)

    li = sub.add_parser("longo-inspecionar", help="lê um arquivo da exportação v9.2 e sugere o mapeamento de colunas")
    li.add_argument("--arquivo", required=True)
    li.add_argument("--saida", help="grava o JSON sugerido (em UTF-8) neste arquivo; use em vez de '>' no PowerShell")

    dl2 = sub.add_parser("dataset-longo", help="dataset de KT a partir da exportação longa v9.2, quatro áreas")
    dl2.add_argument("--config", required=True)
    dl2.add_argument("--raiz-inep", required=True, help="onde estão os ITENS_PROVA (habilidade, anulação, posição)")
    dl2.add_argument("--anos", default="2009-2025")
    dl2.add_argument("--fracao", type=float, default=0.02)
    dl2.add_argument("--seed", type=int, default=0)
    dl2.add_argument("--grade", help="CSV da grade certificada (ano, area, n_participantes) para conciliação")
    dl2.add_argument("--permitir-lacunas", action="store_true", help="segue mesmo se faltar alguma célula")
    dl2.add_argument("--out", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "synth":
        print(synth.generate(args.out, n=args.n))
    elif args.cmd == "longo-inspecionar":
        if not Path(args.arquivo).exists():
            sys.exit(f"Arquivo não encontrado: {args.arquivo}\nNo PowerShell, localize com: "
                     "Get-ChildItem -Recurse -Filter *.parquet <pasta> | Select-Object -First 5 FullName")
        rel = longo.inspecionar(args.arquivo)
        if args.saida:
            cfg = rel["sugestao"]
            Path(args.saida).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Mapeamento sugerido gravado em {args.saida}. Avisos: {rel['avisos'] or 'nenhum'}")
            print("Colunas encontradas:", ", ".join(rel["colunas"]))
        else:
            print(json.dumps(rel, ensure_ascii=False, indent=2, default=str))
    elif args.cmd == "dataset-longo":
        cfg, out, falhas = longo.ConfigLongo.ler(args.config), Path(args.out), {}
        for ano in _anos(args.anos):
            itens = leitura.find_file(args.raiz_inep, "ITENS_PROVA", ano)
            if itens is None:
                falhas[ano] = "ITENS_PROVA não encontrado"
                continue
            try:
                rel = dataset.exportar_de_longo(cfg, ano, itens, out, fracao=args.fracao, seed=args.seed,
                                                permitir_lacunas=args.permitir_lacunas)
                print(f"[{ano}] " + json.dumps({a: s.get("participantes_amostrados") for a, s in rel["areas"].items()}), file=sys.stderr)
            except Exception as e:
                falhas[ano] = f"{type(e).__name__}: {e}"
                print(f"[{ano}] FALHOU: {falhas[ano]}", file=sys.stderr)
        resumo = {"dicionarios": dataset.dicionarios(out), "falhas": falhas}
        if args.grade:
            resumo["conciliacao"] = dataset.conciliar_grade(out, Path(args.grade))
        datasheet.gerar(out)
        print(json.dumps(resumo, ensure_ascii=False, indent=2, default=str))
        if falhas or (args.grade and resumo["conciliacao"]["divergentes"]):
            sys.exit(1)
    elif args.cmd == "dataset":
        out = Path(args.out)
        for ano in _anos(args.anos):
            itens, micro = leitura.find_file(args.raiz, "ITENS_PROVA", ano), leitura.find_microdados(args.raiz, ano)
            if not itens or not micro:
                print(f"[{ano}] arquivos não encontrados", file=sys.stderr)
                continue
            rel = dataset.exportar_edicao(ano, itens, micro, out, fracao=args.fracao, seed=args.seed, lingua=args.lingua, nrows=args.nrows)
            print(f"[{ano}] " + json.dumps({a: (s["amostradas"], s["taxa_gabarito_confere"]) for a, s in rel["areas"].items()}), file=sys.stderr)
        print(json.dumps(dataset.dicionarios(out), indent=2))
        print(datasheet.gerar(out))
    elif args.cmd == "dataset-pykt":
        anos = _anos(args.anos) if args.anos else None
        print(json.dumps(dataset.exportar_pykt(Path(args.dataset), args.nome, anos, args.areas), indent=2))
    elif args.cmd == "dataset-benchmark":
        print(json.dumps(benchmark.rodar(Path(args.dataset), args.ano, args.area, args.max_estudantes, args.permutacoes), ensure_ascii=False, indent=2))
    elif args.cmd == "baixar":
        man = inep.baixar(_anos(args.anos), args.destino, incluir_provas=not args.sem_provas, manter_zip=args.manter_zip)
        print(json.dumps({a: {k: v for k, v in r.items() if k in ("erro", "status", "verificacao", "bytes")}
                          for a, r in man.items()}, ensure_ascii=False, indent=2))
    elif args.cmd == "verificar":
        print(json.dumps(inep.verificar_pasta(args.raiz), ensure_ascii=False, indent=2))
    elif args.cmd == "avaliar":
        rel = avaliacao.avaliar(avaliacao.carregar_exportacoes(args.exportacoes), excluir_dica=not args.incluir_dica)
        texto = json.dumps(rel, ensure_ascii=False, indent=2, default=float)
        Path(args.saida).write_text(texto, encoding="utf-8") if args.saida else print(texto)
    elif args.cmd == "resolucoes":
        raiz = Path(args.entrada)
        itens = pd.concat([pd.read_json(a) for a in sorted(raiz.rglob("items_full.json"))], ignore_index=True)
        itens = itens[itens["enunciado"].notna()]
        nomes = {t["id"]: t["nome"] for t in conteudos.catalogo()}
        r = resolucoes.gerar(json.loads(itens.to_json(orient="records", force_ascii=False)),
                             Path(args.cache) if args.cache else raiz / "resolucoes.json",
                             chave=args.chave, modelo=args.modelo, nomes_conteudo=nomes, limite=args.limite)
        print(json.dumps(r, ensure_ascii=False))
        print("Rode `enemwise merge` para levar as resoluções ao app.")

    elif args.cmd == "conteudos":
        raiz = Path(args.entrada)
        arqs = sorted(raiz.rglob("items_full.json")) or sorted((raiz / "items").glob("*.json"))
        if not arqs:
            raise SystemExit(f"Nenhum items_full.json nem items/*.json em {raiz}")
        itens = pd.concat([pd.read_json(a) for a in arqs], ignore_index=True)
        itens = itens[itens.get("enunciado", pd.Series(dtype=object)).notna()]
        itens["habilidade"] = pd.to_numeric(itens.get("habilidade"), errors="coerce")
        r = itens if "topicos" in itens else conteudos.rotular(itens)
        print(conteudos.cobertura(r).to_string(index=False))
        nomes = {t["id"]: t["nome"] for t in conteudos.catalogo()}
        cont = pd.Series([t for lst in r["topicos"] for t in lst]).value_counts()
        print("\nQuestões por conteúdo:")
        for k, v in cont.items():
            print(f"  {nomes.get(k, k)}: {v}")
        if args.topico:
            sel = r[r["topicos"].apply(lambda l: args.topico in l)]
            print(f"\nExemplos de {nomes.get(args.topico, args.topico)} ({len(sel)} questões):")
            for _, it in sel.head(args.amostra).iterrows():
                print(f"  ENEM {it['ano']} q{it.get('numero')}: {str(it['enunciado'])[:150]}")

    elif args.cmd == "bloom":
        print(json.dumps(bloom.arquivo(args.entrada, args.saida), ensure_ascii=False, indent=2))
    elif args.cmd == "batch":
        batch(args)
    else:
        meta = mrg.merge(Path(args.entrada), Path(args.web), D=args.D, sintetico=args.sintetico,
                         incluir_reprovadas=args.incluir_reprovadas)
        print(json.dumps({k: meta[k] for k in ("edicoes", "edicoes_com_texto", "n_itens_com_texto",
                                               "auditoria_reprovada", "auditoria_alertas_certificadas",
                                               "parametros_reajustados", "n_itens_com_resolucao",
                                               "diagnostico_monotonia", "tamanho_mb")},
                         indent=2, ensure_ascii=False))
        vinc = pd.DataFrame(meta["vinculo_texto"])
        if not vinc.empty:
            print("\nVínculo de texto (questões vinculadas por fonte; a primeira fonte tem prioridade nas repetidas):")
            print(vinc.pivot_table(index="ano", columns="fonte", values="questoes_vinculadas", aggfunc="sum", fill_value=0).to_string())
            ruins = vinc[~vinc["aceito"]]
            if not ruins.empty:
                cols = [c for c in ("ano", "area", "fonte", "numeracao", "match", "motivo") if c in ruins]
                print("\nÁreas sem vínculo aceito:")
                print(ruins[cols].to_string(index=False))


if __name__ == "__main__":
    main()
