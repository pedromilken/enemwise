"""Microdados do ENEM como dataset de Knowledge Tracing.

Uma linha por (participante, questão), na ordem do caderno. Formatos:
  interacoes/ano=<ano>/part-*.parquet   formato longo canônico
  participantes/ano=<ano>/*.parquet      uid, fold, teste, notas por área
  itens.csv, habilidades.csv             dicionários com ids inteiros estáveis
  pykt/<nome>/data.txt                   entrada do pyKT (6 linhas por estudante)

Três cuidados que o formato torna explícitos:
1. ORDEM NÃO É TEMPO. A sequência segue a posição no caderno; o participante pode
   responder em outra ordem. Não há timestamp, e o dataset não finge ter.
2. NÃO HÁ APRENDIZAGEM INTERCALADA. É uma fotografia. Ganho de um modelo de KT sobre a
   TRI aqui é efeito de posição, cansaço ou chute, não aprendizagem. Isso faz do
   dataset um controle nulo, não um benchmark de aprendizagem.
3. AMOSTRA DETERMINÍSTICA. O sorteio usa hash do (ano, linha), então o mesmo participante
   entra em qualquer reexecução, independentemente do tamanho do chunk.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import items as itm, leitura as io
from .schema import BANDAS, RESP_ALIASES

ORDEM_DIAS = {  # (dia, ordem dentro do dia)
    "antiga": {"CH": (1, 0), "CN": (1, 1), "LC": (2, 0), "MT": (2, 1)},   # 2009-2016
    "nova": {"LC": (1, 0), "CH": (1, 1), "CN": (2, 0), "MT": (2, 1)},     # 2017 em diante
}
MASK64 = np.uint64(0xFFFFFFFFFFFFFFFF)


def dia_da_area(ano: int, area: str) -> tuple[int, int]:
    return ORDEM_DIAS["antiga" if ano <= 2016 else "nova"][area]


def _uniforme(ano: int, linhas: np.ndarray, seed: int) -> np.ndarray:
    """SplitMix64 sobre (seed, ano, linha) -> [0, 1). Determinístico e sem estado."""
    with np.errstate(over="ignore"):
        z = (linhas.astype(np.uint64) + np.uint64(ano) * np.uint64(1_000_003) + np.uint64(seed)) * np.uint64(0x9E3779B97F4A7C15)
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> np.uint64(31))
    return (z >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def _fold(uid: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    u = _uniforme(0, uid, seed + 7919)
    return (u * 5).astype(np.int8), u >= 0.8  # 5 folds; 20% fora como teste


def exportar_edicao(ano: int, itens: Path, microdados: Path, out: Path, fracao: float = 0.01, seed: int = 0,
                    lingua: int = 0, chunksize: int = 500_000, nrows: int | None = None) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq

    booklets = itm.filter_booklets(itm.load_itens(itens), lingua=lingua)
    layout = itm.booklet_layout(booklets)
    info = booklets.drop_duplicates("CO_ITEM").set_index("CO_ITEM")
    hab = info["CO_HABILIDADE"] if "CO_HABILIDADE" in info else pd.Series(dtype=float)
    aban = info["IN_ITEM_ABAN"].fillna(0).astype(int) if "IN_ITEM_ABAN" in info else pd.Series(0, index=info.index)

    cols = io.columns(microdados)
    areas = {}
    for area in ("CN", "CH", "MT"):  # LC fica no caminho longo auditado
        names = {k: io.resolve(cols, v, area) for k, v in RESP_ALIASES.items()}
        if all(names[k] for k in ("presenca", "prova", "nota", "respostas")):
            names["gabarito"] = io.resolve(cols, ["TX_GABARITO_{a}"], area)
            areas[area] = names
    usecols = sorted({c for n in areas.values() for c in n.values() if c})

    dir_int = out / "interacoes" / f"ano={ano}"
    dir_par = out / "participantes" / f"ano={ano}"
    dir_int.mkdir(parents=True, exist_ok=True)
    dir_par.mkdir(parents=True, exist_ok=True)
    stats = {a: {"linhas_presentes": 0, "amostradas": 0, "tamanho_invalido": 0, "gabarito_confere": 0, "gabarito_checado": 0}
             for a in areas}
    linha0, parte = 0, 0
    reader = pd.read_csv(microdados, usecols=usecols, chunksize=chunksize, nrows=nrows,
                         dtype={areas[a]["respostas"]: "string" for a in areas}, **io.sniff(microdados))
    for chunk in reader:
        idx = np.arange(linha0, linha0 + len(chunk))
        linha0 += len(chunk)
        keep = _uniforme(ano, idx, seed) < fracao
        chunk = chunk.loc[keep].copy()
        uid = (np.int64(ano) * 100_000_000 + idx[keep]).astype(np.int64)
        chunk["uid"] = uid
        frames = []
        for area, nm in areas.items():
            dia, ordem_dia = dia_da_area(ano, area)
            ok = (pd.to_numeric(chunk[nm["presenca"]], errors="coerce") == 1) & chunk[nm["respostas"]].notna()
            sub = chunk.loc[ok]
            stats[area]["amostradas"] += len(sub)
            for co_prova, grp in sub.groupby(nm["prova"]):
                lay = layout.get(int(co_prova))
                if lay is None:
                    continue
                lay = lay[lay["SG_AREA"] == area].reset_index(drop=True)
                n_it = len(lay)
                s = grp[nm["respostas"]].astype(str).str.strip()
                valid = s.str.len() == n_it
                stats[area]["tamanho_invalido"] += int((~valid).sum())
                grp, s = grp.loc[valid], s[valid]
                if grp.empty:
                    continue
                gab_str = "".join(lay["TX_GABARITO"])
                if nm.get("gabarito"):
                    g = grp[nm["gabarito"]].astype(str).str.strip()
                    stats[area]["gabarito_checado"] += len(g)
                    stats[area]["gabarito_confere"] += int((g == gab_str).sum())
                mat = np.frombuffer("".join(s).encode("latin-1"), dtype="S1").reshape(-1, n_it)
                gab = np.frombuffer(gab_str.encode("latin-1"), dtype="S1")
                k = len(grp)
                co_items = lay["CO_ITEM"].to_numpy(np.int64)
                frames.append(pd.DataFrame({
                    "uid": np.repeat(grp["uid"].to_numpy(), n_it),
                    "area": area, "dia": np.int8(dia),
                    "ordem_exame": np.tile((dia * 1000 + ordem_dia * 100 + np.arange(n_it)).astype(np.int32), k),
                    "posicao_caderno": np.tile(lay["CO_POSICAO"].to_numpy(np.int16), k),
                    "co_prova": np.int32(co_prova),
                    "co_item": np.tile(co_items, k),
                    "habilidade": np.tile(pd.to_numeric(hab.reindex(co_items), errors="coerce").to_numpy(), k),
                    "anulado": np.tile(aban.reindex(co_items).fillna(0).to_numpy(np.int8), k),
                    "resposta": mat.reshape(-1).astype(str),
                    "correct": (mat == gab).reshape(-1).astype(np.int8),
                    "nota_area": np.repeat(pd.to_numeric(grp[nm["nota"]], errors="coerce").to_numpy(np.float32), n_it),
                }))
            stats[area]["linhas_presentes"] += int(ok.sum())
        if frames:
            df = pd.concat(frames, ignore_index=True)
            df["banda"] = np.digitize(df["nota_area"].fillna(-1).to_numpy(), [lo for lo, _ in BANDAS[1:]]).astype(np.int8)
            # "ano" vem da partição hive (ano=<ano>), não é repetido dentro do arquivo
            pq.write_table(pa.Table.from_pandas(df, preserve_index=False), dir_int / f"part-{parte:04d}.parquet")
            fold, teste = _fold(chunk["uid"].to_numpy(), seed)
            par = pd.DataFrame({"uid": chunk["uid"].to_numpy(), "fold": fold, "teste": teste})
            for area, nm in areas.items():
                par[f"nota_{area}"] = pd.to_numeric(chunk[nm["nota"]], errors="coerce").to_numpy(np.float32)
            pq.write_table(pa.Table.from_pandas(par, preserve_index=False), dir_par / f"part-{parte:04d}.parquet")
            parte += 1
    for a in stats.values():
        a["taxa_gabarito_confere"] = round(a["gabarito_confere"] / a["gabarito_checado"], 4) if a["gabarito_checado"] else None
    rel = {"ano": ano, "fracao": fracao, "seed": seed, "linhas_lidas": int(linha0), "areas": stats,
           "lc": "ausente no caminho bruto; use a exportação longa auditada"}
    (out / "relatorios").mkdir(exist_ok=True)
    (out / "relatorios" / f"{ano}.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    itens_ed = booklets.drop_duplicates("CO_ITEM").assign(ano=ano)
    itens_ed.to_csv(out / "relatorios" / f"itens_{ano}.csv", index=False)
    return rel


def dicionarios(out: Path) -> dict:
    """ids inteiros estáveis para questões e habilidades (sem 'NA' no texto: o pyKT o trata como ausente)."""
    fs = sorted((out / "relatorios").glob("itens_*.csv"))
    itens = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
    itens = itens.sort_values(["ano", "SG_AREA", "CO_ITEM"]).reset_index(drop=True)
    itens["question_id"] = np.arange(len(itens))
    itens["chave_habilidade"] = itens["SG_AREA"] + "-H" + itens["CO_HABILIDADE"].astype("Int64").astype(str)
    habs = sorted(itens.loc[itens["CO_HABILIDADE"].notna(), "chave_habilidade"].unique())
    mapa = {h: i for i, h in enumerate(habs)}
    itens["concept_id"] = itens["chave_habilidade"].map(mapa).astype("Int64")
    cols = [c for c in ["question_id", "ano", "SG_AREA", "CO_ITEM", "CO_HABILIDADE", "concept_id", "NU_PARAM_A",
                        "NU_PARAM_B", "NU_PARAM_C", "TX_GABARITO", "IN_ITEM_ABAN"] if c in itens]
    itens[cols].to_csv(out / "itens.csv", index=False)
    pd.DataFrame({"concept_id": list(mapa.values()), "habilidade": list(mapa.keys())}).to_csv(out / "habilidades.csv", index=False)
    return {"questoes": int(len(itens)), "habilidades": len(mapa)}


def carregar(out: Path, anos: list[int] | None = None, areas: list[str] | None = None) -> pd.DataFrame:
    import pyarrow.dataset as ds
    d = ds.dataset(out / "interacoes", format="parquet", partitioning="hive")
    filtro = None
    if anos:
        filtro = ds.field("ano").isin(anos)
    if areas:
        f2 = ds.field("area").isin(areas)
        filtro = f2 if filtro is None else filtro & f2
    return d.to_table(filter=filtro).to_pandas()


def exportar_pykt(out: Path, nome: str, anos: list[int] | None = None, areas: list[str] | None = None,
                  excluir_anulados: bool = True) -> dict:
    """data.txt do pyKT: por estudante, 6 linhas (uid,len / questões / conceitos / respostas / NA / NA)."""
    itens = pd.read_csv(out / "itens.csv")
    qmap = dict(zip(zip(itens["ano"], itens["CO_ITEM"]), itens["question_id"]))
    cmap = dict(zip(zip(itens["ano"], itens["CO_ITEM"]), itens["concept_id"]))
    df = carregar(out, anos, areas)
    n0 = len(df)
    if excluir_anulados:
        df = df[df["anulado"] == 0]
    df = df.assign(q=[qmap.get(k) for k in zip(df["ano"], df["co_item"])],
                   c=[cmap.get(k) for k in zip(df["ano"], df["co_item"])])
    sem_conceito = int(df["c"].isna().sum())
    df = df.dropna(subset=["q", "c"]).sort_values(["uid", "ordem_exame"])
    destino = out / "pykt" / nome
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "data.txt").open("w", encoding="utf-8") as f:
        for uid, g in df.groupby("uid", sort=False):
            f.write(f"{uid},{len(g)}\n")
            f.write(",".join(g["q"].astype(int).astype(str)) + "\n")
            f.write(",".join(g["c"].astype(int).astype(str)) + "\n")
            f.write(",".join(g["correct"].astype(int).astype(str)) + "\n")
            f.write("NA\nNA\n")
    rel = {"interacoes_lidas": n0, "exportadas": int(len(df)), "sem_habilidade_descartadas": sem_conceito,
           "estudantes": int(df["uid"].nunique()), "arquivo": str(destino / "data.txt")}
    (destino / "resumo.json").write_text(json.dumps(rel, indent=2), encoding="utf-8")
    return rel


# ---------------------------------------------------------------- a partir do v9.2
def _manifesto_celula(cfg, ano: int, areas) -> dict:
    """Lê o _manifesto.json gravado pelo export_enemwise.py da v9.2, se existir."""
    out = {}
    for area in areas:
        arqs = cfg.arquivos(ano, area)
        if arqs:
            m = Path(arqs[0]).parent / "_manifesto.json"
            if m.exists():
                out[area] = json.loads(m.read_text(encoding="utf-8"))
    return out


def exportar_de_longo(cfg, ano: int, itens: Path, out: Path, fracao: float = 0.01, seed: int = 0, lingua: int = 0,
                      areas: tuple[str, ...] = ("CN", "CH", "LC", "MT"), permitir_lacunas: bool = False,
                      tamanho_lote: int = 1_000_000) -> dict:
    """Mesmo esquema de exportar_edicao, mas com acertos vindos da exportação longa auditada."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    from . import longo

    booklets = itm.filter_booklets(itm.load_itens(itens), lingua=lingua)
    raw_itens = itm.load_itens(itens)
    info = raw_itens.drop_duplicates("CO_ITEM").set_index("CO_ITEM")
    hab = pd.to_numeric(info.get("CO_HABILIDADE", pd.Series(dtype=float)), errors="coerce")
    aban = info["IN_ITEM_ABAN"].fillna(0).astype(int) if "IN_ITEM_ABAN" in info else pd.Series(0, index=info.index)
    area_do_item = info["SG_AREA"]
    # todas as línguas: um participante de espanhol tem itens de espanhol no caderno
    pos_por_prova = raw_itens.drop_duplicates(["CO_PROVA", "CO_ITEM"]).set_index(["CO_PROVA", "CO_ITEM"])["CO_POSICAO"]
    usar_posicao = bool(cfg.colunas.get("posicao"))  # preferida: na v9.2 já é a ordem certificada da folha
    manifesto = _manifesto_celula(cfg, ano, areas)

    dir_int = out / "interacoes" / f"ano={ano}"
    dir_par = out / "participantes" / f"ano={ano}"
    dir_int.mkdir(parents=True, exist_ok=True)
    dir_par.mkdir(parents=True, exist_ok=True)
    rel = {"ano": ano, "fonte": "exportação longa v9.2", "fracao": fracao, "seed": seed, "areas": {}, "lacunas": []}
    notas: list[pd.DataFrame] = []
    parte = 0
    for area in areas:
        st = {"interacoes_lidas": 0, "participantes_lidos": 0, "participantes_amostrados": 0, "interacoes_amostradas": 0,
              "itens_fora_do_itens_prova": 0, "itens_de_outra_area": 0, "sem_posicao": 0, "correct_nao_binario": 0,
              "itens_por_participante": {}}
        try:
            dia, ordem_dia = dia_da_area(ano, area)
            vistos: list[np.ndarray] = []
            contagens: list[pd.Series] = []
            for lote in longo.lotes(cfg, ano, area, tamanho=tamanho_lote):
                st["interacoes_lidas"] += len(lote)
                uid = longo.uid_int(lote["uid"], ano)
                vistos.append(np.unique(uid))
                keep = _uniforme(ano, uid, seed) < fracao
                lote = lote.loc[keep].copy()
                lote["uid"] = uid[keep]
                if lote.empty:
                    continue
                lote["co_item"] = pd.to_numeric(lote["co_item"], errors="coerce").astype("Int64")
                corr = pd.to_numeric(lote["correct"], errors="coerce")
                st["correct_nao_binario"] += int((~corr.isin([0, 1])).sum())
                lote["correct"] = corr.fillna(0).astype(np.int8)
                fora = ~lote["co_item"].isin(info.index)
                st["itens_fora_do_itens_prova"] += int(fora.sum())
                lote = lote.loc[~fora]
                outra = area_do_item.reindex(lote["co_item"].astype(int)).to_numpy() != area
                st["itens_de_outra_area"] += int(outra.sum())
                if not usar_posicao:
                    chave = pd.MultiIndex.from_arrays([pd.to_numeric(lote["co_prova"], errors="coerce").astype("Int64"),
                                                       lote["co_item"]])
                    pos = pos_por_prova.reindex(chave).to_numpy()
                else:
                    pos = pd.to_numeric(lote["posicao"], errors="coerce").to_numpy()
                st["sem_posicao"] += int(pd.isna(pos).sum())
                lote = lote.assign(posicao_caderno=pos).dropna(subset=["posicao_caderno"])
                lote["posicao_caderno"] = lote["posicao_caderno"].astype(np.int16)
                # posição dentro do bloco de 45 da área: vale para numeração absoluta (1-180) ou por área (1-45)
                # e não depende de o participante cair inteiro no mesmo lote
                rel_pos = (lote["posicao_caderno"].astype(np.int32) - 1) % 45
                items = lote["co_item"].astype(int).to_numpy()
                df = pd.DataFrame({
                    "uid": lote["uid"].to_numpy(np.int64), "area": area, "dia": np.int8(dia),
                    "ordem_exame": (dia * 1000 + ordem_dia * 100 + rel_pos).astype(np.int32).to_numpy(),
                    "posicao_caderno": lote["posicao_caderno"].to_numpy(),
                    "co_prova": pd.to_numeric(lote.get("co_prova", pd.Series(-1, index=lote.index)), errors="coerce").fillna(-1).astype(np.int32).to_numpy(),
                    "co_item": items.astype(np.int64),
                    "habilidade": hab.reindex(items).to_numpy(),
                    "anulado": aban.reindex(items).fillna(0).to_numpy(np.int8),
                    "resposta": lote["resposta"].astype(str).to_numpy() if "resposta" in lote else "",
                    "correct": lote["correct"].to_numpy(),
                    "nota_area": pd.to_numeric(lote["nota"], errors="coerce").to_numpy(np.float32),
                })
                df["banda"] = np.digitize(df["nota_area"].fillna(-1).to_numpy(), [lo for lo, _ in BANDAS[1:]]).astype(np.int8)
                pq.write_table(pa.Table.from_pandas(df, preserve_index=False), dir_int / f"part-{parte:04d}.parquet")
                parte += 1
                st["interacoes_amostradas"] += len(df)
                contagens.append(df.groupby("uid").size())
                notas.append(df.drop_duplicates("uid")[["uid", "nota_area"]].assign(area=area))
            st["participantes_lidos"] = int(len(np.unique(np.concatenate(vistos)))) if vistos else 0
            if contagens:
                tot = pd.concat(contagens).groupby(level=0).sum()
                st["participantes_amostrados"] = int(len(tot))
                st["itens_por_participante"] = {int(k): int(v) for k, v in tot.value_counts().sort_index().items()}
        except FileNotFoundError as e:
            rel["lacunas"].append(f"{ano}-{area}")
            st["erro"] = str(e)
            if not permitir_lacunas:
                raise
        if area in manifesto:
            st["n_populacao_alinhada"] = manifesto[area].get("n_populacao_alinhada")
            st["fracao_exportacao"] = manifesto[area].get("frac")
            st["blank_policy_exportacao"] = manifesto[area].get("blank_policy")
        rel["areas"][area] = st
    if notas:
        n = pd.concat(notas).pivot_table(index="uid", columns="area", values="nota_area", aggfunc="first")
        n.columns = [f"nota_{c}" for c in n.columns]
        n = n.reset_index()
        fold, teste = _fold(n["uid"].to_numpy(), seed)
        n.insert(1, "fold", fold)
        n.insert(2, "teste", teste)
        pq.write_table(pa.Table.from_pandas(n, preserve_index=False), dir_par / "part-0000.parquet")
    (out / "relatorios").mkdir(exist_ok=True)
    (out / "relatorios" / f"{ano}.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_itens.drop_duplicates("CO_ITEM").assign(ano=ano).to_csv(out / "relatorios" / f"itens_{ano}.csv", index=False)
    return rel


def conciliar_grade(out: Path, grade_path: Path, tolerancia_relativa: float = 0.001) -> dict:
    """Compara a população de cada célula com a grade certificada do artigo.

    Com o _manifesto.json da exportação v9.2, compara a POPULAÇÃO ALINHADA (antes do
    sorteio) com `students` da grade. A grade usou brancos descartados; quem deixou a
    área inteira em branco sai dela e fica na exportação com branco = erro, então a
    diferença esperada é mínima e positiva. Sem manifesto, compara os participantes lidos.
    """
    from . import longo
    grade = longo.ler_grade(grade_path)
    col = next((c for c in ("n_participantes", "participantes", "students", "n", "n_registros") if c in grade.columns), None)
    if col is None:
        raise ValueError("A grade precisa de uma coluna n_participantes (ou students, participantes, n, n_registros).")
    linhas = []
    for f in sorted((out / "relatorios").glob("[0-9]*.json")):
        rel = json.loads(f.read_text(encoding="utf-8"))
        for area, st in rel["areas"].items():
            esperado = grade.loc[(grade["ano"] == rel["ano"]) & (grade["area"].str.upper() == area), col]
            lido = st.get("n_populacao_alinhada") or st.get("participantes_lidos")
            g = int(esperado.iloc[0]) if len(esperado) else None
            dif = None if g is None or lido is None else lido - g
            linhas.append({"ano": rel["ano"], "area": area, "lido": lido, "grade": g, "diferenca": dif,
                           "base": "população alinhada (manifesto)" if st.get("n_populacao_alinhada") else "participantes lidos",
                           "confere": bool(g and dif is not None and abs(dif) <= tolerancia_relativa * g)})
    df = pd.DataFrame(linhas)
    res = {"celulas": len(df), "conferem": int(df["confere"].sum()), "tolerancia_relativa": tolerancia_relativa,
           "divergentes": df[~df["confere"]].to_dict(orient="records")}
    (out / "relatorios" / "conciliacao_grade.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res
