#!/usr/bin/env node
/* Modo prova: agentes fazem a 1ª etapa do ENEM como os candidatos fizeram, edição por edição.

   O que é reproduzido do cenário real de cada ano (cronograma.json + cadernos.json):
   - os dois dias, as áreas de cada dia e a ordem delas no caderno;
   - a duração oficial de cada dia; no dia da redação, uma reserva de tempo para ela (--redacao-min);
   - os cadernos regulares de todas as cores (a ordem das questões muda de cor para cor), sorteados por candidato;
   - a língua estrangeira escolhida (inglês ou espanhol nas cinco primeiras de LC);
   - um caderno contínuo por dia: o agente vê as questões em ordem, com o relógio e o que falta;
   - sem retorno durante a prova: o gabarito só chega depois do dia inteiro (como a conferência na vida real).

   O relógio é virtual. O tempo de cada questão segue um modelo declarado:
     resolver = (palavras / wpm + resolução da área) × ritmo do candidato   (ritmo ~ lognormal, um por candidato)
     chutar   = --chute-min;   pular = 30% da leitura (a questão volta no fim se sobrar tempo)
   Acabou o tempo: as questões que faltam viram chute (--esgotado chute) ou branco (--esgotado branco).

   Saída (agentes/saida/prova-<cérebro>-<rodada>/):
     respostas.jsonl           uma linha por candidato×dia (retomável: rode de novo e ele continua)
     longo/<ano>_<AREA>.csv    formato longo do v9.2: uid, co_item, correct, nota, co_prova, posicao, resposta (+ extras)
     RESUMO.md, config.json

   Uso:
     node tools/modo-prova/modo-prova.js --cerebro ollama:qwen3:8b --agentes 20 --anos 2009-2025 \
          --cadernos dados/cadernos.json --textos dados
     node tools/modo-prova/modo-prova.js --consolidar --saida agentes/saida/prova-...   (só refaz longo/ e RESUMO.md)
*/
"use strict";
const fs = require("fs"), path = require("path");
const LAB = require(path.join(__dirname, "..", "agentes", "laboratorio.js"));
const { makeRng, makeBrain, preflight, readAnswer, brainSlug } = LAB;
const VERSAO = "1.4.1";

/* ---------------- argumentos ---------------- */
function args(argv) {
  const o = { agentes: 20, anos: "2009-2025", memoria: "auto", esgotado: "chute", retorno: "gabarito", "redacao-min": 60, wpm: 200,
    resolucao: "LC:1.2,CH:1.4,CN:2.4,MT:2.8", dispersao: 0.25, "chute-min": 0.5, chute: "nao", persona: "nenhuma", lingua: "ingles", temperatura: 0.7, semente: "enem",
    paralelo: 1, raciocinio: false, consolidar: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]; if (!a.startsWith("--")) continue;
    const k = a.slice(2), nx = argv[i + 1];
    if (nx === undefined || nx.startsWith("--")) o[k] = true; else { o[k] = nx; i++; }
  }
  for (const k of ["agentes", "redacao-min", "wpm", "dispersao", "chute-min", "temperatura", "paralelo"]) o[k] = +o[k];
  o.res = Object.fromEntries(String(o.resolucao).split(",").map(s => s.split(":")).map(([a, v]) => [a, +v]));
  return o;
}
const anosDe = s => String(s).split(",").flatMap(p => { const [lo, hi] = p.split("-").map(Number); return Array.from({ length: (hi || lo) - lo + 1 }, (_, i) => lo + i); });
const lerJSONL = f => fs.existsSync(f) ? fs.readFileSync(f, "utf8").split(/\r?\n/).filter(l => l.trim()).map(l => JSON.parse(l)) : [];
const palavras = s => (String(s || "").match(/\S+/g) || []).length;
const hm = min => { min = Math.max(0, min); const h = Math.floor(min / 60), m = Math.floor(min % 60); return (h ? h + "h" : "") + String(m).padStart(h ? 2 : 1, "0") + "min"; };
const AREA_NOME = { LC: "Linguagens, Códigos e suas Tecnologias", CH: "Ciências Humanas e suas Tecnologias", CN: "Ciências da Natureza e suas Tecnologias", MT: "Matemática e suas Tecnologias" };

/* ---------------- textos: caderno Amarelo (PDF + visão), com o banco do app como reserva ---------------- */
function carregarTextos(o, cad) {
  const dir = o.textos, porPos = {};
  const arq = n => [path.join(dir, n + "-visao.jsonl"), path.join(dir, n + ".jsonl")].find(f => fs.existsSync(f));
  for (const n of ["provas-inep", "provas-inep-espanhol"]) {
    const f = arq(n); if (!f) continue;
    for (const r of lerJSONL(f)) { const [ano, num] = r.id.split("_"); porPos[`${ano}|${+num}|${r.lingua || ""}`] = r; }
  }
  const porItem = {};
  for (const [ano, A] of Object.entries(cad.anos)) for (const [dia, cs] of Object.entries(A.cadernos)) {
    const am = cs.find(c => /AMAREL/i.test(c.cor)); if (!am) continue;
    for (const it of am.itens) {
      const r = porPos[`${ano}|${it.pos}|${it.lingua === "espanhol" ? "espanhol" : (it.lingua ? "ingles" : "")}`] || porPos[`${ano}|${it.pos}|`] || porPos[`${ano}|${it.pos}|ingles`];
      if (r && r.alternatives && r.alternatives.length === 5) porItem[it.co_item] = { enunciado: r.question, alternativas: r.alternatives, descricao: r.description || [], fonte: "pdf" };
    }
  }
  if (o.banco && fs.existsSync(o.banco)) for (const f of fs.readdirSync(o.banco).filter(f => /^\d{4}\.json$/.test(f))) {
    for (const it of JSON.parse(fs.readFileSync(path.join(o.banco, f), "utf8"))) {
      if (porItem[+it.co_item] || !it.enunciado) continue;
      let alts = it.alternativas; if (typeof alts === "string") { try { alts = JSON.parse(alts.replace(/'/g, '"')); } catch { alts = null; } }
      if (Array.isArray(alts) && alts.length === 5) porItem[+it.co_item] = { enunciado: it.enunciado, alternativas: alts, descricao: Array.isArray(it.descricao) ? it.descricao : [], fonte: "banco" };
    }
  }
  return porItem;
}

/* ---------------- persona (categoria "LLM com perfil", como Generative Students, Lu & Wang 2024) ----------------
   Cada candidato recebe uma proficiência θ ~ Normal(0,1) na escala do INEP (nota ≈ 500 + 100θ). Em cada área, ele DOMINA a
   habilidade da Matriz cuja dificuldade média (b médio dos itens dela na edição) é menor que θ, e NÃO domina as outras.
   O perfil vai nas regras da prova e cada questão diz se a habilidade dela é dominada. Isso cria a dispersão de habilidade
   entre candidatos que o cérebro sozinho não tem; a fidelidade é medida depois (θ do perfil × nota obtida). */
function criarPersona(A, r) {
  const z = Math.sqrt(-2 * Math.log(r() + 1e-12)) * Math.cos(2 * Math.PI * r());
  const theta = +z.toFixed(3);
  const bHab = {};
  for (const cs of Object.values(A.cadernos)) for (const it of (cs[0] || { itens: [] }).itens) {
    if (it.b == null || !it.habilidade) continue;
    const k = it.area + "|" + it.habilidade; (bHab[k] ||= []).push(it.b);
  }
  /* domina com probabilidade P = 1/(1+e^{-1,7(θ - b̄)}) da habilidade: um candidato na média do INEP (θ = 0) domina poucas,
     como na população real (acerto médio de 30-40%); sorteio fixo por candidato */
  const dom = {}; for (const [k, bs] of Object.entries(bHab)) { const bm = bs.reduce((x, y) => x + y, 0) / bs.length; dom[k] = r() < 1 / (1 + Math.exp(-1.7 * (theta - bm))); }
  const faixa = theta < -0.5 ? "abaixo da média" : theta < 0.5 ? "na média" : theta < 1.5 ? "acima da média" : "muito acima da média";
  const nd = Object.entries(dom).filter(([, v]) => !v).length, nt = Object.keys(dom).length;
  return { theta, domina: it => !!dom[it.area + "|" + it.habilidade],
    texto: `SEU PERFIL: você é um(a) estudante com desempenho ${faixa} (nota esperada por volta de ${Math.round(500 + 100 * theta)} pontos). ` +
      `Das ${nt} habilidades da Matriz cobradas hoje, você não domina ${nd}. Responda exatamente como esse estudante responderia: ` +
      `nas questões de habilidades que você NÃO domina, você não tem o conhecimento necessário e tende a errar ou a escolher a alternativa ` +
      `que parece mais plausível à primeira vista; nas que você domina, resolva normalmente. Não use conhecimento que esse estudante não teria.` };
}

/* ---------------- uma prova: um candidato, um dia ---------------- */
const SIS = (ano, dia, D, o, tempoUtil, n, extra) =>
  `Você é um(a) estudante concluinte do ensino médio fazendo o ENEM ${ano}, ${dia.dia}º dia. Neste caderno há ${n} questões de múltipla escolha: ` +
  dia.areas.map(a => AREA_NOME[a]).join(" e depois ") + ". " +
  (dia.redacao ? `O dia tem ${hm(dia.duracao_min)} no total, incluindo a redação; ${hm(o["redacao-min"])} ficam reservados para ela, então você tem ${hm(tempoUtil)} para as questões. ` : `Você tem ${hm(tempoUtil)} para as questões. `) +
  "Não há desconto por erro. Questão em branco vale zero. Você não recebe a correção durante a prova.\n" +
  "Antes de cada questão você vê o tempo que resta e quantas questões faltam. Para cada questão, responda em UMA linha, com UMA destas opções:\n" +
  "RESPOSTA: <letra>   (você resolve a questão; leva o tempo de ler e resolver)\n" +
  (o.chute === "sim" ? "CHUTE               (não resolve: a letra é SORTEADA ao acaso; leva cerca de " + Math.round(o["chute-min"] * 60) + " segundos. Use só quando não houver tempo para resolver)\n" : "") +
  "PULAR               (deixa para o fim; se sobrar tempo, a questão volta)\n" +
  (o.raciocinio ? "Você pode pensar em até 5 linhas antes, mas a última linha deve ser uma das opções acima.\n" : "Não escreva mais nada além dessa linha.\n") +
  (extra ? "\n" + extra + "\n" : "");

function textoItem(it, T) {
  const d = (T.descricao || []).length ? "\n[Descrição das figuras: " + T.descricao.join(" | ") + "]" : "";
  return T.enunciado + d + "\n\n" + "ABCDE".split("").map((l, i) => l + ") " + T.alternativas[i]).join("\n");
}

function lerAcao(txt) {
  const s = String(txt || "");
  let m = s.match(/(RESPOSTA|CHUTE)\s*[:：]\s*\(?([A-E])\b/i);
  if (m) return { acao: m[1].toUpperCase() === "CHUTE" ? "chute" : "resposta", letra: m[2].toUpperCase(), fmt: "pedido" };
  if (/\bCHUTE\b/i.test(s)) return { acao: "chute", letra: null, fmt: "pedido" };
  if (/\bPULAR\b/i.test(s)) return { acao: "pular", letra: null, fmt: "pedido" };
  const r = readAnswer(s, "letter");
  if (r.v && /^[A-E]$/.test(r.v)) return { acao: "resposta", letra: r.v, fmt: "tolerado" };
  return { acao: "ilegivel", letra: null, fmt: "ilegivel" };
}

async function fazerDia(brain, o, ano, dia, cad, T, uid, rng, memoriaPrev) {
  const lingua = memoriaPrev.lingua;
  const itens = cad.itens.filter(it => !it.lingua || it.lingua === lingua).sort((a, b) => a.pos - b.pos);
  const tempoUtil = dia.duracao_min - (dia.redacao ? o["redacao-min"] : 0);
  const ritmo = memoriaPrev.ritmo;
  const per = memoriaPrev.persona;
  const sis = SIS(ano, dia, null, o, tempoUtil, itens.length, [per ? per.texto : "", memoriaPrev.retorno].filter(Boolean).join("\n\n"));
  const domina = it => per ? per.domina(it) : null;
  let relogio = tempoUtil;
  const memo = o.memoriaModo, janela = o.janela;
  const hist = [];   /* pares [user, assistant] */
  const res = new Map(), fila = itens.slice(), puladas = [];
  const custoLer = it => palavras(T[it.co_item] ? textoItem(it, T[it.co_item]) : "") / o.wpm;
  const esgotar = (it, motivo) => {
    const letra = o.esgotado === "chute" ? "ABCDE"[Math.floor(rng() * 5)] : null;
    res.set(it.co_item, { it, acao: motivo, resposta: letra || ".", tempo: 0, relogio: 0, fmt: "-" });
  };
  async function servir(it, segunda) {
    const t = T[it.co_item];
    if (!t) { res.set(it.co_item, { it, acao: it.co_item < 0 ? "anulado_sem_item" : "sem_texto", resposta: null, tempo: 0, relogio, fmt: "-" }); return; }
    const faltam = fila.length + puladas.length + 1;
    const cab = `QUESTÃO ${it.pos} (${it.area}${it.lingua ? ", " + it.lingua : ""})${segunda ? " — questão que você pulou" : ""}\n` +
      (per && it.habilidade ? `Habilidade H${it.habilidade} da Matriz de Referência — você ${domina(it) ? "DOMINA" : "NÃO domina"} esta habilidade.\n` : "") +
      `Tempo restante: ${hm(relogio)} · faltam ${faltam} questão(ões) · ritmo para terminar: ${(relogio / faltam).toFixed(1).replace(".", ",")} min/questão\n\n`;
    const user = cab + textoItem(it, t) + (o.chute === "sim" ? "\n\nSua linha (RESPOSTA: <letra> | CHUTE | PULAR):" : "\n\nSua linha (RESPOSTA: <letra> | PULAR):");
    const ctx = memo === "nenhuma" ? [] : memo === "janela" ? hist.slice(-janela) : hist;
    const msgs = [{ role: "system", content: sis }, ...ctx.flatMap(([u, a]) => [{ role: "user", content: u }, { role: "assistant", content: a }]), { role: "user", content: user }];
    /* cérebro "aleatorio" (linha de base do acaso, a mesma do laboratório): resolve marcando uma letra ao acaso */
    const out = brain.kind === "aleatorio" ? (brain.stats.calls++, "RESPOSTA: " + "ABCDE"[Math.floor(rng() * 5)])
      : await brain.call(msgs, { temperature: o.temperatura, max: o.raciocinio ? 400 : 40, rng });
    hist.push([user, out.split(/\r?\n/).filter(Boolean).slice(-1)[0] || out]);
    let a = lerAcao(out);
    /* sem a opção de chute (padrão): "CHUTE: X" vale como resposta normal (paga o tempo de resolver); "CHUTE" sem letra é ilegível */
    if (a.acao === "chute" && o.chute !== "sim") a = a.letra ? { acao: "resposta", letra: a.letra, fmt: "tolerado" } : { acao: "ilegivel", letra: null, fmt: "ilegivel" };
    if (a.acao === "pular" && segunda) a = { acao: "pular2", letra: null, fmt: a.fmt };
    const ler = custoLer(it) * (segunda ? 0.5 : 1);
    const custo = a.acao === "chute" ? o["chute-min"] : a.acao === "pular" ? 0.3 * ler * ritmo : (ler + (o.res[it.area] || 2)) * ritmo;
    if (a.acao === "pular") { relogio -= custo; puladas.push(it); return; }
    if (a.acao === "pular2") { esgotar(it, "pulou_fim"); relogio -= o["chute-min"]; return; }
    if (custo > relogio) { esgotar(it, "esgotado_na_questao"); relogio = 0; return; }
    relogio -= custo;
    /* chute é cego: o agente já leu a questão (um LLM não "passa o olho"), então a letra dele não vale; sorteia-se.
       Sem isso, CHUTE vira um "responder barato" (piloto v1.0: qwen3 chutou 23% das questões com 64% de acerto). */
    if (a.acao === "chute") a.letra = "ABCDE"[Math.floor(rng() * 5)];
    res.set(it.co_item, { it, acao: a.acao, resposta: a.letra || ".", tempo: +custo.toFixed(2), relogio: +relogio.toFixed(2), fmt: a.fmt, bruto: out.slice(0, 200) });
  }
  while (fila.length) { const it = fila.shift(); if (relogio <= 0) { esgotar(it, "esgotado"); continue; } await servir(it, false); }
  while (puladas.length) { const it = puladas.shift(); if (relogio <= 0) { esgotar(it, "esgotado"); continue; } await servir(it, true); }
  /* correção (só agora, ao fim do dia) */
  const linhas = itens.map(it => {
    const r = res.get(it.co_item) || { acao: "esgotado", resposta: "." };
    const correct = it.anulado || r.acao === "sem_texto" ? null : (r.resposta === it.gab ? 1 : 0);
    return { co_item: it.co_item, area: it.area, pos: it.pos, pos_area: it.pos_area, co_prova: it.co_prova, lingua: it.lingua, gab: it.gab,
      resposta: r.resposta, correct, acao: r.acao, tempo: r.tempo || 0, relogio: r.relogio ?? 0, fmt: r.fmt, anulado: !!it.anulado, a: it.a, b: it.b, c: it.c, habilidade: it.habilidade,
      ...(per ? { domina: domina(it) } : {}) };
  });
  return { linhas, tempoUsado: +(tempoUtil - Math.max(0, relogio)).toFixed(1), tempoUtil };
}

function retornoDoDia(o, dia, linhas) {
  if (o.retorno === "nenhum") return "";
  const por = {}; for (const l of linhas) if (l.correct != null) { (por[l.area] ||= [0, 0]); por[l.area][0] += l.correct; por[l.area][1]++; }
  let s = `Depois do ${dia.dia}º dia você conferiu o gabarito: ` + Object.entries(por).map(([a, [k, n]]) => `${k} de ${n} em ${a}`).join(" e ") + ".";
  if (o.retorno === "gabarito") { const err = linhas.filter(l => l.correct === 0).map(l => `${l.pos} (certa ${l.gab})`); if (err.length) s += " Você errou ou deixou em branco: " + err.join(", ") + "."; }
  return s;
}

/* ---------------- nota TRI (EAP, 3PL do INEP, D = 1,7; escala 500 + 100θ) ---------------- */
function notaEAP(linhas) {
  const G = Array.from({ length: 81 }, (_, i) => -4 + i * 0.1); let num = 0, den = 0;
  for (const th of G) {
    let lp = -th * th / 2;
    for (const l of linhas) { if (l.correct == null || l.a == null) continue; const p = l.c + (1 - l.c) / (1 + Math.exp(-1.7 * l.a * (th - l.b))); lp += l.correct ? Math.log(p) : Math.log(1 - p); }
    const w = Math.exp(lp); num += th * w; den += w;
  }
  return den > 0 ? +(500 + 100 * num / den).toFixed(1) : null;
}

/* ---------------- consolidação: formato longo + resumo ---------------- */
function consolidar(dir) {
  const regs = lerJSONL(path.join(dir, "respostas.jsonl")), cfg = JSON.parse(fs.readFileSync(path.join(dir, "config.json"), "utf8"));
  const ld = path.join(dir, "longo"); fs.mkdirSync(ld, { recursive: true });
  const cel = {};
  for (const r of regs) for (const l of r.linhas) (cel[`${r.ano}_${l.area}`] ||= {})[r.uid] ||= [], cel[`${r.ano}_${l.area}`][r.uid].push({ ...l, r });
  const resumo = [], cab = "uid,co_item,correct,nota,co_prova,posicao,resposta,pos_area,acao,tempo_min,anulado,lingua,cor,dia,habilidade,cerebro";
  for (const [k, porUid] of Object.entries(cel).sort()) {
    const out = [cab]; let n = 0, ac = 0, notas = [], cont = {};
    for (const [uid, ls] of Object.entries(porUid)) {
      const nota = notaEAP(ls); if (nota != null) notas.push(nota);
      for (const l of ls) {
        out.push([uid, l.co_item, l.correct ?? "", nota ?? "", l.co_prova, l.pos, l.resposta ?? "", l.pos_area, l.acao, l.tempo, l.anulado ? 1 : 0, l.lingua || "", l.r.cor, l.r.dia, l.habilidade ?? 0, l.r.cerebro].join(","));
        if (l.correct != null) { n++; ac += l.correct; } cont[l.acao] = (cont[l.acao] || 0) + 1;
      }
    }
    fs.writeFileSync(path.join(ld, k + ".csv"), out.join("\n") + "\n");
    const tot = Object.values(cont).reduce((a, b) => a + b, 0), pc = x => ((cont[x] || 0) / tot * 100).toFixed(1);
    const [ano, area] = k.split("_");
    resumo.push(`| ${ano} | ${area} | ${Object.keys(porUid).length} | ${(ac / Math.max(1, n)).toFixed(3)} | ${notas.length ? (notas.reduce((a, b) => a + b, 0) / notas.length).toFixed(0) : "-"} | ${pc("resposta")} | ${pc("chute")} | ${(+pc("esgotado") + +pc("esgotado_na_questao") + +pc("pulou_fim")).toFixed(1)} | ${pc("ilegivel")} | ${pc("sem_texto")} |`);
  }
  const td = {}; for (const r of regs) { const k = `${r.ano}|${r.dia}`; (td[k] ||= []).push(r); }
  const tempos = Object.entries(td).sort().map(([k, rs]) => { const [ano, dia] = k.split("|"), u = rs.map(r => r.tempoUsado), m = u.reduce((a, b) => a + b, 0) / u.length;
    const esg = rs.filter(r => r.linhas.some(l => /esgotado/.test(l.acao))).length;
    return `| ${ano} | ${dia} | ${rs[0].tempoUtil} | ${m.toFixed(0)} | ${Math.min(...u).toFixed(0)}–${Math.max(...u).toFixed(0)} | ${(100 * esg / rs.length).toFixed(0)}% |`; });
  const md = `# Modo prova — ${cfg.cerebro}\n\nRodada ${cfg.rodada}, início ${cfg.inicio}. Memória: ${cfg.memoria}; tempo esgotado: ${cfg.esgotado}; retorno: ${cfg.retorno}; ` +
    `leitura ${cfg.wpm} palavras/min; resolução (min) ${cfg.resolucao}; ritmo lognormal dp ${cfg.dispersao}; reserva da redação ${cfg["redacao-min"]} min.\n\n` +
    `Nota = EAP do 3PL com os parâmetros do INEP (D = 1,7), escala 500 + 100θ, sem os itens anulados.\n\n` +
    `| ano | área | candidatos | acerto | nota média | % resolvidas | % chutes | % tempo esgotado | % ilegível | % sem texto |\n|---|---|---|---|---|---|---|---|---|---|\n` +
    resumo.join("\n") + "\n\n## Tempo por dia (min)\n\n| ano | dia | tempo para as questões | usado (média) | faixa | candidatos que estouraram o tempo |\n|---|---|---|---|---|---|\n" + tempos.join("\n") + "\n";
  fs.writeFileSync(path.join(dir, "RESUMO.md"), md);
  console.log(`consolidado: ${Object.keys(cel).length} células em ${ld}; resumo em RESUMO.md`);
}

/* Cérebro de teste (sem LLM): resolve com 60% de acerto, chuta quando o ritmo aperta. Testa o encanamento e o relógio. */
function cerebroTeste(cad) {
  const gab = {}; for (const [ano, A] of Object.entries(cad.anos)) for (const cs of Object.values(A.cadernos)) for (const c of cs) for (const it of c.itens) gab[`${ano}|${c.cor}|${it.pos}|${it.lingua || ""}`] = it.gab;
  const stats = { calls: 0, inTok: 0, outTok: 0, fails: 0 };
  return { kind: "teste", model: "", stats, async call(msgs, { rng }) {
    stats.calls++; const u = msgs[msgs.length - 1].content, ritmo = +((u.match(/ritmo para terminar: ([\d,]+)/) || [])[1] || "9").replace(",", ".");
    if (rng() < 0.03) return "PULAR";
    const L = "ABCDE"[Math.floor(rng() * 5)];
    if (ritmo < 1.2) return "CHUTE: " + L;
    return "RESPOSTA: " + (rng() < 0.6 ? (u.match(/\[gab:(\w)\]/) || [, L])[1] : L);
  } };
}

/* ---------------- principal ---------------- */
async function main() {
  const o = args(process.argv.slice(2));
  if (o.consolidar) { if (!o.saida) throw new Error("--consolidar precisa de --saida <pasta da rodada>"); return consolidar(o.saida); }
  if (!o.cerebro) throw new Error("informe --cerebro (ex.: ollama:qwen3:8b, deepseek:deepseek-chat, simulado, aleatorio)");
  const raiz = path.resolve(__dirname, "..", "..");
  o.cadernos ||= path.join(raiz, "dados", "cadernos.json"); o.textos ||= path.join(raiz, "dados");
  o.banco ||= path.join(raiz, "web", "public", "data", "items");
  const cad = JSON.parse(fs.readFileSync(o.cadernos, "utf8")), crono = cad.anos;
  const brain = o.cerebro === "teste" ? cerebroTeste(cad) : makeBrain(o.cerebro);
  if (o.memoria === "auto") o.memoria = brain.kind === "ollama" ? "janela:6" : "completa";
  [o.memoriaModo, o.janela] = o.memoria.startsWith("janela") ? ["janela", +(o.memoria.split(":")[1] || 6)] : [o.memoria, 0];
  if (brain.kind === "ollama" && o.memoriaModo === "completa" && !process.env.LAB_NUM_CTX) console.error("aviso: memória completa num cérebro local precisa de contexto grande; defina LAB_NUM_CTX (ex.: 65536) ou use --memoria janela:6");
  process.env.LAB_PARALELO = String(o.paralelo);
  await preflight(brain);
  const T = carregarTextos(o, cad);
  const rodada = o.rodada || new Date().toISOString().slice(0, 10);
  const dir = o.saida || path.join(raiz, "agentes", "saida", `prova-${brainSlug(o.cerebro)}-${rodada}`);
  fs.mkdirSync(dir, { recursive: true });
  const cfgF = path.join(dir, "config.json");
  const cfg = fs.existsSync(cfgF) ? JSON.parse(fs.readFileSync(cfgF, "utf8")) : { versao: VERSAO, nucleo: LAB.NUCLEO_VERSAO, cerebro: o.cerebro, rodada, inicio: new Date().toISOString(),
    memoria: o.memoria, esgotado: o.esgotado, retorno: o.retorno, wpm: o.wpm, resolucao: o.resolucao, dispersao: o.dispersao, "redacao-min": o["redacao-min"], "chute-min": o["chute-min"],
    chute: o.chute, persona: o.persona, lingua: o.lingua, temperatura: o.temperatura, raciocinio: !!o.raciocinio, semente: o.semente };
  for (const k of ["memoria", "esgotado", "retorno", "wpm", "resolucao", "dispersao", "redacao-min", "lingua", "semente", "chute", "persona"]) if (String(cfg[k] ?? { chute: "nao", persona: "nenhuma" }[k]) !== String(o[k])) throw new Error(`a pasta ${dir} é de uma rodada com ${k} = ${cfg[k]}; use outra --rodada para mudar parâmetros`);
  fs.writeFileSync(cfgF, JSON.stringify(cfg, null, 2));
  const respF = path.join(dir, "respostas.jsonl");
  const feitos = new Set(lerJSONL(respF).map(r => `${r.uid}|${r.dia}`));
  /* cobertura de texto */
  for (const ano of anosDe(o.anos)) { const A = crono[ano]; if (!A) { console.error(`${ano}: sem cadernos (rode exportar_cadernos.py)`); continue; }
    const its = new Set(Object.values(A.cadernos).flatMap(cs => cs.flatMap(c => c.itens.filter(i => !i.lingua || i.lingua === (o.lingua === "espanhol" ? "espanhol" : "ingles")).map(i => i.co_item))));
    const sem = [...its].filter(i => i > 0 && !T[i]).length;   /* código negativo = posição sem item (anulada), não falta de texto */ if (sem) console.error(`aviso ${ano}: ${sem} de ${its.size} questões sem texto (ficam fora da correção; rode descrever_figuras.py)`); }
  const tarefas = [];
  for (const ano of anosDe(o.anos)) if (crono[ano]) for (let k = 1; k <= o.agentes; k++) tarefas.push({ ano, uid: `${brainSlug(o.cerebro)}-${ano}-${String(k).padStart(3, "0")}` });
  let feitas = 0; const t0 = Date.now(), total = tarefas.length;
  async function candidato({ ano, uid }) {
    const A = crono[ano], r0 = makeRng(o.semente, uid);
    const z = Math.sqrt(-2 * Math.log(r0() + 1e-12)) * Math.cos(2 * Math.PI * r0());
    const mem = { ritmo: Math.exp(o.dispersao * z), lingua: o.lingua === "sorteio" ? (r0() < 0.5 ? "ingles" : "espanhol") : o.lingua, retorno: "" };
    if (o.persona === "habilidades") mem.persona = criarPersona(A, makeRng(o.semente, uid, "persona"));
    for (const dia of A.dias) {
      const cs = A.cadernos[dia.dia]; if (!cs || !cs.length) continue;
      const cad1 = cs[Math.floor(makeRng(o.semente, uid, "cor", dia.dia)() * cs.length)];
      const chave = `${uid}|${dia.dia}`;
      if (feitos.has(chave)) { const prev = lerJSONL(respF).find(r => `${r.uid}|${r.dia}` === chave); if (prev) mem.retorno = retornoDoDia(o, dia, prev.linhas); continue; }
      const rng = makeRng(o.semente, uid, "dia", dia.dia);
      const { linhas, tempoUsado, tempoUtil } = await fazerDia(brain, o, ano, dia, cad1, T, uid, rng, mem);
      fs.appendFileSync(respF, JSON.stringify({ uid, ano, dia: dia.dia, cor: cad1.cor, lingua: mem.lingua, ritmo: +mem.ritmo.toFixed(3), cerebro: o.cerebro,
        ...(mem.persona ? { theta_persona: mem.persona.theta } : {}), tempoUsado, tempoUtil, linhas }) + "\n");
      mem.retorno = retornoDoDia(o, dia, linhas);
    }
    feitas++;
    const el = (Date.now() - t0) / 1000;
    process.stdout.write(`\r${feitas}/${total} candidatos · ${brain.stats.calls} chamadas · ${(el / 60).toFixed(1)} min · faltam ~${(el / feitas * (total - feitas) / 60).toFixed(0)} min   `);
  }
  /* candidatos em paralelo (cada um faz seus dias em sequência) */
  const fila = tarefas.slice(); const workers = Array.from({ length: Math.max(1, o.paralelo) }, async () => { while (fila.length) await candidato(fila.shift()); });
  await Promise.all(workers);
  console.log(`\ntokens: entrada ${brain.stats.inTok}, saída ${brain.stats.outTok}; falhas ${brain.stats.fails}`);
  consolidar(dir);
}
if (require.main === module) main().catch(e => { console.error("\nERRO: " + e.message); process.exit(1); });
module.exports = { notaEAP, lerAcao, args };
