"""Resoluções comentadas das questões, geradas uma vez com um modelo de linguagem.

O app mostra a resolução depois da resposta e quando a questão volta em revisão. Gerar no
pipeline, e não no navegador, tem duas vantagens: custa uma vez só, e o texto pode ser
revisado antes de ir para o estudante.

Retomável: o cache (resolucoes.json) guarda uma entrada por id de questão; rodar de novo só
gera o que falta. A chave da API nunca vai para o repositório: vem do ambiente ou de --chave.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

MODELO_PADRAO = "claude-sonnet-5"

PROMPT = """Você é professor de {area_nome} preparando estudantes do ensino médio para o Enem.
Escreva a resolução comentada da questão abaixo, em português do Brasil, para quem acabou de respondê-la.

Regras:
- Comece pelo que a questão pede e pelo conceito envolvido (habilidade H{habilidade} da Matriz{conteudo}).
- Mostre o raciocínio passo a passo até chegar ao gabarito ({gabarito}). Em matemática e ciências, faça as contas.
- Diga em uma frase por que cada alternativa errada é tentadora ou onde está o erro dela.
- Termine com "Para lembrar:" e uma frase com a ideia que resolve questões parecidas.
- Até 220 palavras. Parágrafos curtos separados por linha em branco. Sem markdown, sem títulos, sem listas com asteriscos.

Questão (ENEM {ano}, nº {numero}):
{enunciado}
{descricao}
Alternativas:
{alternativas}
Gabarito: {gabarito}"""

NOME_AREA = {"MT": "Matemática", "LC": "Linguagens e Códigos", "CN": "Ciências da Natureza", "CH": "Ciências Humanas"}


def _chamar(chave: str, modelo: str, texto: str, tentativas: int = 4) -> str:
    corpo = json.dumps({"model": modelo, "max_tokens": 700, "messages": [{"role": "user", "content": texto}]}).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=corpo, method="POST", headers={
        "content-type": "application/json", "x-api-key": chave, "anthropic-version": "2023-06-01"})
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                dados = json.loads(r.read().decode("utf-8"))
            return "\n".join(b.get("text", "") for b in dados.get("content", []) if b.get("type") == "text").strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and i < tentativas - 1:
                time.sleep(2 ** (i + 1))
                continue
            raise RuntimeError(f"API respondeu {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from e


def gerar(itens: list[dict], cache: Path, chave: str | None = None, modelo: str = MODELO_PADRAO,
          nomes_conteudo: dict[str, str] | None = None, limite: int | None = None, pausa: float = 0.3) -> dict:
    chave = chave or os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise SystemExit("Informe a chave com --chave ou na variável de ambiente ANTHROPIC_API_KEY.")
    feito: dict[str, str] = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    pendentes = [it for it in itens if it.get("enunciado") and it["id"] not in feito]
    if limite:
        pendentes = pendentes[:limite]
    print(f"resoluções: {len(feito)} em cache, {len(pendentes)} a gerar")
    erros = 0
    for n, it in enumerate(pendentes, 1):
        alts = "\n".join(f"{'ABCDE'[i]}) {a}" for i, a in enumerate(it.get("alternativas") or []))
        conts = [nomes_conteudo.get(t, t) for t in (it.get("topicos") or [])] if nomes_conteudo else []
        texto = PROMPT.format(area_nome=NOME_AREA.get(it["area"], it["area"]), habilidade=it.get("habilidade"),
                              conteudo=f"; conteúdo: {', '.join(conts)}" if conts else "", gabarito=it.get("gabarito"),
                              ano=it.get("ano"), numero=it.get("numero"), enunciado=it["enunciado"],
                              descricao="\n".join(it.get("descricao") or []), alternativas=alts)
        try:
            feito[it["id"]] = _chamar(chave, modelo, texto)
        except Exception as e:  # segue para a próxima; o cache guarda o que deu certo
            erros += 1
            print(f"  [{it['id']}] falhou: {e}")
        if n % 10 == 0 or n == len(pendentes):
            cache.write_text(json.dumps(feito, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {n}/{len(pendentes)} geradas ({erros} erros)", flush=True)
        time.sleep(pausa)
    cache.write_text(json.dumps(feito, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"em_cache": len(feito), "geradas_agora": len(pendentes) - erros, "erros": erros}
