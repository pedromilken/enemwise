/* Adaptador do laboratório de agentes: ENEMWISE (questões reais do ENEM, Matriz de Referência do INEP).
   O núcleo (laboratorio.js) é o mesmo nas cinco ferramentas; este arquivo só diz ao núcleo o que é um item, o que o
   agente "estudou" (notas) e como corrigir.

   Itens: as questões com texto que o próprio ENEMWise publica (web/public/data/items/*.json), com a habilidade da Matriz,
   as cinco alternativas e o gabarito oficial. Por padrão só as questões SEM figura (--figuras descricao inclui as com
   figura, trocando a imagem pela descrição textual que o ENEMWise já guarda).
   Habilidade = área + habilidade da Matriz (ex.: MT-H21). Padrão: as 3 habilidades com mais questões em cada área.
   Notas = a habilidade da Matriz (descritor, competência, nível de Bloom) + até 4 exemplos resolvidos: OUTRAS questões
   da mesma habilidade com a alternativa correta (o que o estudante veria como questão resolvida).
   Dificuldade para o KT (--dificuldade):
     autoral (padrão)  terços do b do INEP viram d = 1, 2, 3 e o chute é 1/5, como nas outras ferramentas: o MESMO
                       termômetro nos cinco domínios
     inep              o KT usa o b e o c calibrados pelo INEP (ITEM_B): o ENEM é o único domínio com parâmetros reais,
                       então isto é análise de sensibilidade, não a comparação principal
   Referência externa (só no ENEM): o acerto do agente sem notas, item a item, é comparado com a dificuldade humana
   medida pelo INEP (correlação de Spearman entre C0 e −b, e entre C0 e o acerto da banda 550–650). */
"use strict";
const fs = require("fs"), path = require("path");
module.exports = {
  id: "enemwise", nome: "ENEMWise",
  carregar({ ROOT, LAB, opts, KT }) {
    const dir = path.join(ROOT, "web", "public", "data", "items"), M = JSON.parse(fs.readFileSync(path.join(ROOT, "web", "src", "data", "matriz.json"), "utf8"));
    let raw = []; for (const f of fs.readdirSync(dir).filter(f => f.endsWith(".json")).sort()) raw.push(...JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));
    const withFig = opts && opts.figuras === "descricao";
    raw = raw.filter(i => i.habilidade > 0 && i.gabarito && /^[A-E]$/.test(i.gabarito) && i.alternativas && i.alternativas.length === 5 && (withFig || !(i.figuras && i.figuras.length)));
    const bs = raw.map(i => i.b).sort((a, b) => a - b), q1 = bs[Math.floor(bs.length / 3)], q2 = bs[Math.floor(2 * bs.length / 3)], inep = opts && opts.dificuldade === "inep";
    const items = raw.map(i => ({ id: i.id, skill: i.area + "-H" + i.habilidade, type: i.area, d: i.b < q1 ? 1 : i.b < q2 ? 2 : 3, c: inep ? Math.max(.05, Math.min(.5, i.c)) : 0.2, src: i }));
    if (inep) for (const it of items) KT.ITEM_B[it.id] = 1.7 * it.src.b;   /* escala logística do INEP (D = 1,7) */
    const byId = Object.fromEntries(items.map(i => [i.id, i]));
    const count = {}; items.forEach(i => count[i.skill] = (count[i.skill] || 0) + 1);
    const skills = [...new Set(items.map(i => i.skill))].sort();
    const padrao = ["LC", "CH", "CN", "MT"].flatMap(a => skills.filter(s => s.startsWith(a + "-")).sort((x, y) => count[y] - count[x] || x.localeCompare(y)).slice(0, 3));
    const hab = s => { const [a, h] = s.split("-H"); return Object.assign({ area: a }, M.areas[a].habilidades[h] || {}); };
    const skillName = s => { const x = hab(s); return s + " · " + (x.descricao || "").slice(0, 70); };
    const clean = s => String(s || "").replace(/\s+/g, " ").trim(), cut = (s, n) => s.length > n ? s.slice(0, n) + "…" : s;
    const stem = it => clean(it.src.enunciado) + (withFig && it.src.descricao && it.src.descricao.length ? "\n[" + it.src.descricao.map(clean).join(" ") + "]" : "");
    function notes(lang, skill, exclude) {
      const x = hab(skill), comp = (M.areas[x.area].competencias || []).find(c => c.numero === x.competencia);
      const ex = items.filter(i => i.skill === skill && i.id !== exclude).slice(0, 4);
      return "## " + M.areas[x.area].nome + " · habilidade " + skill.split("-H")[1] + "\n- Habilidade: " + (x.descricao || "") + (comp ? "\n- Competência " + comp.numero + ": " + comp.descricao : "") + (x.bloom ? "\n- Nível de Bloom: " + x.bloom : "") +
        "\nWORKED EXAMPLES (other questions of this skill, with the correct answer):\n" + ex.map(i => "* " + cut(stem(i), 500) + "\n  CORRECT: " + clean(i.src.alternativas["ABCDE".indexOf(i.src.gabarito)])).join("\n");
    }
    const build = (it, r) => { const k = "ABCDE".indexOf(it.src.gabarito), alts = it.src.alternativas.map(clean);
      return LAB.mcItem("ENEM " + it.src.ano + " · " + M.areas[it.skill.split("-")[0]].nome, stem(it), [alts[k], ...alts.filter((_, j) => j !== k)], r); };
    const SYS = () => "You are role-playing a Brazilian high-school student preparing for the ENEM exam in a training game. You only know what is written in your NOTES below; if the NOTES do not cover the question, answer the way a student who has not studied this would guess, without using knowledge you are not supposed to have. Follow the reply format exactly and write nothing else.";
    /* referência externa: o agente acha difícil o que é difícil para os humanos? */
    function externo(med) {
      const by = {}; med.forEach(x => (by[x.item] = by[x.item] || []).push(x.c0)); const ids = Object.keys(by); if (ids.length < 10) return "";
      const rank = v => { const o = v.map((x, i) => [x, i]).sort((a, b) => a[0] - b[0]), r = Array(v.length); let i = 0; while (i < o.length) { let j = i; while (j + 1 < o.length && o[j + 1][0] === o[i][0]) j++; for (let k = i; k <= j; k++) r[o[k][1]] = (i + j) / 2; i = j + 1; } return r; };
      const sp = (a, b) => { const x = rank(a), y = rank(b), mx = x.reduce((s, v) => s + v, 0) / x.length, my = y.reduce((s, v) => s + v, 0) / y.length; let n = 0, dx = 0, dy = 0; x.forEach((v, i) => { n += (v - mx) * (y[i] - my); dx += (v - mx) ** 2; dy += (y[i] - my) ** 2; }); return dx && dy ? n / Math.sqrt(dx * dy) : 0; };
      const c0 = ids.map(i => by[i].reduce((s, v) => s + v, 0) / by[i].length), nb = ids.map(i => -byId[i].src.b), pb = ids.map(i => (byId[i].src.p_banda || [])[2] || 0);
      return `**Referência humana (INEP)**: correlação de Spearman, item a item, entre o acerto do agente sem notas e a facilidade para os humanos: com −b da TRI ρ = ${sp(c0, nb).toFixed(2)}; com o acerto da banda 550–650 ρ = ${sp(c0, pb).toFixed(2)} (${ids.length} itens). Perto de zero, o agente acha difícil coisas diferentes das que os estudantes acham.`;
    }
    return {
      dominioPt: "ENEM (Matriz de Referência do INEP)", dominioEn: "the Brazilian ENEM exam", idiomas: ["pt"],
      padrao: { habilidades: padrao, itensPorHabilidade: 10 },
      skills: skills.map(id => ({ id, area: id.split("-")[0] })), items, byId,
      area: s => s.split("-")[0], skillName, langName: () => "Portuguese", notes, externo,
      attempt: (brain, lang, it, notesText, r) => LAB.singleTurn(brain, SYS(), build(it, r), notesText, r),
      tutorTask: (lang, it, r) => { const k = "ABCDE".indexOf(it.src.gabarito), alts = it.src.alternativas.map(clean), wrong = alts[(k + 1 + Math.floor(r() * 4)) % 5];
        return { task: "ITEM: " + cut(stem(it), 1500) + "\nOPTIONS:\n" + alts.map(a => "- " + a).join("\n") + "\nTHE STUDENT CHOSE: " + wrong, correct: alts[k], reference: "" }; },
      preview: (lang, it, notesText, r) => "NOTES:\n" + notesText + "\n\n" + build(it, r).body,
      limites: ["Questões reais e públicas do ENEM estão no treino dos LLMs: o vazamento (C0) mede também memorização de questões, não só conhecimento.",
        "Só português (a prova não tem versão oficial em outros idiomas); por isso o IC vem de alunos, não de idiomas.",
        "Por padrão ficam de fora as questões com figura; com --figuras descricao, a figura vira a descrição textual do ENEMWise."]
    };
  }
};
