"""Conteúdos programáticos: segmenta as questões em tópicos de disciplina.

A Matriz de Referência diz que COMPETÊNCIA a questão cobra; ela não diz que
CONTEÚDO cai nela. "H8: resolver situação-problema de espaço e forma" cobre
tanto área de triângulo quanto volume de cilindro. Quem estuda precisa do
conteúdo; quem ensina, dos dois.

Fontes da taxonomia: o anexo "Objetos de conhecimento associados às Matrizes de
Referência" (INEP) e o programa do vestibular da Fuvest, que detalha os mesmos
objetos em itens finos (por exemplo, geometria analítica dentro de geometria).

Como a classificação funciona, e o que ela não é: cada tópico tem termos
característicos; o texto da questão é comparado com eles e a habilidade da
Matriz entra como reforço, nunca como regra isolada. É uma heurística
transparente e auditável, não um classificador treinado: questões sem termo
claro ficam SEM tópico, de propósito, em vez de receber um palpite.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

# (id, nome, disciplina, habilidades típicas, termos, termos fortes)
Topico = tuple[str, str, str, tuple[int, ...], tuple[str, ...], tuple[str, ...]]

TAXONOMIA: dict[str, tuple[Topico, ...]] = {
    "MT": (
        ("numeros", "Números e operações", "Matemática", (1, 2, 3, 4),
         ("fracao", "fracoes", "decimal", "divisor", "divisores", "multiplo", "multiplos", "numero primo",
          "numeros primos", "arredond", "valor absoluto", "numeros inteiros", "numeros racionais", "algarismo"),
         ("mmc", "mdc", "notacao cientifica", "divisibilidade")),
        ("financeira", "Porcentagem e matemática financeira", "Matemática", (3, 4, 5, 16, 17),
         ("por cento", "porcentagem", "percentual", "aumento de", "reducao de", "desconto", "taxa de", "lucro",
          "prejuizo", "salario", "imposto", "reais", "custo", "preco", "taxa", "tarifa", "valor a pagar"),
         ("juros simples", "juros compostos", "juros", "inflacao", "montante", "capital inicial")),
        ("proporcao", "Razão, proporção e grandezas", "Matemática", (10, 11, 12, 15, 16, 17, 18),
         ("proporcional", "proporcao", "razao entre", "por litro", "km/h", "densidade", "vazao", "rendimento",
          "consumo", "velocidade media", "quilometros", "litros por", "escala", "para cada", "por unidade"),
         ("regra de tres", "diretamente proporcional", "inversamente proporcional", "escala de")),
        ("sequencias", "Sequências e progressões", "Matemática", (2, 15, 16, 19),
         ("sequencia", "termo seguinte", "termos da sequencia", "padrao numerico", "recorrencia"),
         ("progressao aritmetica", "progressao geometrica", "razao da progressao")),
        ("funcoes", "Funções e gráficos", "Matemática", (19, 20, 21, 22, 23, 15, 16, 17),
         ("funcao", "f(x)", "grafico", "parabola", "vertice", "crescente", "decrescente", "dominio",
          "imagem da funcao", "maximo", "minimo", "logaritmo", "exponencial", "lei de formacao",
          "em funcao de", "expressao que representa", "modelo matematico"),
         ("funcao quadratica", "funcao afim", "funcao exponencial", "funcao logaritmica", "y =")),
        ("equacoes", "Equações, inequações e sistemas", "Matemática", (19, 21, 22, 3),
         ("equacao", "inequacao", "incognita", "raizes da equacao", "resolver a equacao", "sistema de equacoes",
          "expressao algebrica"),
         ("sistema linear", "delta", "bhaskara")),
        ("geometria-plana", "Geometria plana", "Matemática", (6, 7, 8, 9, 10, 12, 13, 14),
         ("triangulo", "quadrado", "retangulo", "losango", "trapezio", "poligono", "hexagono", "circulo",
          "angulo", "perimetro", "area da", "area do", "diagonal", "lados", "altura do triangulo", "bissetriz"),
         ("teorema de pitagoras", "semelhanca de triangulos", "teorema de tales", "area total da figura")),
        ("geometria-espacial", "Geometria espacial e volumes", "Matemática", (6, 7, 8, 9, 12, 13, 14),
         ("volume", "cubo", "cilindro", "cone", "esfera", "prisma", "piramide", "paralelepipedo", "capacidade",
          "litros", "metros cubicos", "m3", "aresta", "solido"),
         ("volume do cilindro", "volume do cone", "area total do solido", "tronco de")),
        ("geometria-analitica", "Geometria analítica", "Matemática", (6, 7, 8, 9, 19, 20, 22),
         ("coordenadas", "eixo x", "eixo y", "abscissa", "ordenada", "ponto medio", "reta que passa",
          "distancia entre os pontos", "origem do plano"),
         ("plano cartesiano", "equacao da reta", "equacao da circunferencia", "coeficiente angular")),
        ("trigonometria", "Trigonometria", "Matemática", (6, 7, 8, 9, 19, 20),
         ("seno", "cosseno", "tangente", "angulo de 30", "angulo de 45", "angulo de 60", "radianos",
          "periodo da funcao", "amplitude"),
         ("lei dos senos", "lei dos cossenos", "ciclo trigonometrico", "razoes trigonometricas")),
        ("estatistica", "Estatística e leitura de dados", "Matemática", (24, 25, 26, 27, 29, 30),
         ("media", "mediana", "moda", "grafico de barras", "grafico de setores", "tabela", "frequencia",
          "amostra", "pesquisa", "dados apresentados", "desvio padrao", "variancia", "percentil"),
         ("media aritmetica", "media ponderada", "medidas de tendencia central", "distribuicao de frequencia")),
        ("probabilidade", "Probabilidade", "Matemática", (27, 28, 29, 30, 2),
         ("probabilidade", "chance de", "sorteio", "sorteado", "dado", "moeda", "aleatoriamente", "urna",
          "baralho", "evento"),
         ("probabilidade de", "espaco amostral", "probabilidade condicional")),
        ("contagem", "Análise combinatória", "Matemática", (2, 3, 28),
         ("possibilidades", "maneiras diferentes", "combinacoes", "permutacao", "arranjo", "anagramas",
          "quantas formas", "senhas"),
         ("principio multiplicativo", "analise combinatoria", "fatorial")),
    ),
    "LC": (
        ("interpretacao", "Leitura e interpretação de texto", "Língua Portuguesa", (18, 19, 21, 22, 23, 24, 1, 3, 4),
         ("o texto", "no texto", "do texto", "trecho", "leitura do texto", "ideia central", "tese", "argumento",
          "autor defende", "finalidade do texto", "publico-alvo"),
         ("objetivo do texto", "de acordo com o texto", "o texto tem por")),
        ("generos-midias", "Gêneros textuais e mídias", "Língua Portuguesa", (1, 2, 3, 4, 18, 21, 28, 29, 30),
         ("cartaz", "anuncio", "propaganda", "campanha", "charge", "tirinha", "cartum", "infografico", "noticia",
          "reportagem", "manchete", "rede social", "internet", "blog", "aplicativo", "digital"),
         ("genero textual", "campanha publicitaria", "peca publicitaria")),
        ("variacao", "Variação linguística e norma", "Língua Portuguesa", (25, 26, 27),
         ("variedade", "regionalismo", "sotaque", "giria", "fala popular", "coloquial", "norma culta",
          "norma-padrao", "linguagem formal", "informal"),
         ("variacao linguistica", "variedades linguisticas", "preconceito linguistico")),
        ("gramatica", "Gramática em uso", "Língua Portuguesa", (25, 26, 27, 18, 19),
         ("concordancia", "regencia", "crase", "pontuacao", "pronome", "verbo", "conjuncao", "preposicao",
          "sujeito", "oracao", "sintaxe", "morfologia", "tempo verbal"),
         ("coesao", "coerencia", "elemento coesivo", "recurso coesivo")),
        ("figuras-funcoes", "Figuras e funções da linguagem", "Língua Portuguesa", (19, 21, 22, 24, 16),
         ("metafora", "metonimia", "ironia", "hiperbole", "eufemismo", "personificacao", "ambiguidade",
          "conotativo", "denotativo", "sentido figurado"),
         ("figura de linguagem", "funcao da linguagem", "funcao poetica", "funcao conativa")),
        ("literatura", "Literatura", "Literatura", (15, 16, 17, 13, 14),
         ("poema", "poesia", "verso", "estrofe", "eu lirico", "romance", "conto", "cronica", "narrador",
          "personagem", "obra literaria", "modernismo", "romantismo", "barroco", "realismo", "parnasianismo"),
         ("texto literario", "literatura brasileira", "semana de arte moderna", "geracao de")),
        ("lem", "Língua estrangeira (inglês e espanhol)", "Língua Estrangeira", (5, 6, 7, 8),
         ("the ", " of the", "english", "espanol", "palabras", "texto em ingles", "texto em espanhol"),
         ()),
        ("artes", "Arte e produção cultural", "Arte", (12, 13, 14, 5),
         ("pintura", "escultura", "quadro", "obra de arte", "artista", "museu", "teatro", "musica", "danca",
          "cinema", "fotografia", "arquitetura"),
         ("produção artistica", "manifestacao artistica", "linguagem artistica")),
        ("corporais", "Práticas corporais e esporte", "Educação Física", (9, 10, 11),
         ("esporte", "atleta", "jogo", "ginastica", "exercicio fisico", "capoeira", "futebol", "olimpico",
          "corpo", "movimento corporal", "lazer"),
         ("praticas corporais", "linguagem corporal", "atividade fisica")),
    ),
    "CN": (
        ("mecanica", "Mecânica", "Física", (20, 17, 18, 1, 2),
         ("velocidade", "aceleracao", "forca", "atrito", "massa", "peso", "movimento", "queda", "gravidade",
          "trabalho", "potencia", "energia cinetica", "energia potencial", "colisao", "pressao", "empuxo"),
         ("leis de newton", "quantidade de movimento", "conservacao de energia", "energia mecanica")),
        ("termologia", "Calor e termodinâmica", "Física", (21, 17, 18, 23),
         ("temperatura", "calor", "termometro", "dilatacao", "condensacao", "evaporacao", "caloria",
          "isolante termico", "maquina termica", "gas ideal"),
         ("calor especifico", "termodinamica", "equilibrio termico", "calor latente")),
        ("ondas-optica", "Ondas, óptica e radiação", "Física", (1, 22, 17, 18),
         ("onda", "frequencia", "comprimento de onda", "som", "luz", "espelho", "lente", "refracao", "reflexao",
          "ultrassom", "raios", "espectro", "laser", "infravermelho", "ultravioleta"),
         ("fenomeno ondulatorio", "optica geometrica", "radiacao eletromagnetica")),
        ("eletricidade", "Eletricidade e magnetismo", "Física", (5, 6, 21, 23),
         ("corrente eletrica", "tensao", "voltagem", "resistor", "resistencia eletrica", "circuito", "carga eletrica",
          "campo magnetico", "ima", "kwh", "potencia eletrica", "gerador", "transformador"),
         ("lei de ohm", "efeito joule", "consumo de energia eletrica")),
        ("materia-atomo", "Estrutura da matéria e tabela periódica", "Química", (24, 17, 18),
         ("atomo", "eletron", "proton", "neutron", "isotopo", "tabela periodica", "elemento quimico",
          "ligacao ionica", "ligacao covalente", "molecula", "polaridade", "numero atomico"),
         ("modelo atomico", "distribuicao eletronica", "forcas intermoleculares")),
        ("reacoes", "Reações químicas e estequiometria", "Química", (24, 25, 8, 18),
         ("reacao quimica", "equacao quimica", "mol", "massa molar", "rendimento", "balanceamento",
          "reagente", "produto da reacao", "combustao", "oxidacao"),
         ("estequiometria", "constante de avogadro", "lei de lavoisier")),
        ("solucoes", "Soluções, ácidos e bases", "Química", (24, 25, 26, 27),
         ("solucao", "concentracao", "soluto", "solvente", "diluicao", "ph", "acido", "base", "sal",
          "solubilidade", "neutralizacao", "titulacao"),
         ("concentracao em mol", "escala de ph", "produto ionico")),
        ("energia-quimica", "Termoquímica, eletroquímica e radioatividade", "Química", (21, 23, 26, 22),
         ("entalpia", "exotermica", "endotermica", "pilha", "bateria", "eletrolise", "oxirreducao", "corrosao",
          "radioativ", "meia-vida", "fissao", "fusao nuclear", "isotopos radioativos"),
         ("lei de hess", "potencial de reducao", "energia nuclear")),
        ("organica", "Química orgânica e polímeros", "Química", (24, 25, 27, 18),
         ("hidrocarboneto", "cadeia carbonica", "alcool", "aldeido", "cetona", "acido carboxilico", "ester",
          "amina", "polimero", "plastico", "petroleo", "biodiesel", "etanol", "fermentacao"),
         ("funcao organica", "isomeria", "polimerizacao")),
        ("celula", "Célula, metabolismo e biotecnologia", "Biologia", (15, 11, 13, 29),
         ("celula", "membrana", "mitocondria", "cloroplasto", "nucleo", "enzima", "proteina", "metabolismo",
          "fotossintese", "respiracao celular", "atp", "tecido"),
         ("sintese proteica", "divisao celular", "celula-tronco", "dna recombinante")),
        ("genetica", "Genética e hereditariedade", "Biologia", (13, 14, 11, 29),
         ("gene", "genes", "alelo", "cromossomo", "dna", "rna", "mutacao", "heredograma", "hereditariedade",
          "dominante", "recessivo", "transgenico", "clonagem"),
         ("leis de mendel", "codigo genetico", "engenharia genetica")),
        ("evolucao", "Evolução e diversidade", "Biologia", (16, 28, 15),
         ("evolucao", "selecao natural", "darwin", "lamarck", "adaptacao", "especie", "especiacao", "fossil",
          "ancestral", "taxonomia", "filogenia"),
         ("teoria da evolucao", "selecao artificial", "deriva genetica")),
        ("ecologia", "Ecologia e ambiente", "Biologia", (4, 9, 10, 12, 28, 30),
         ("ecossistema", "cadeia alimentar", "teia alimentar", "bioma", "populacao", "comunidade", "habitat",
          "biodiversidade", "desmatamento", "poluicao", "efeito estufa", "aquecimento global", "reciclagem",
          "ciclo do carbono", "ciclo da agua", "sustentavel"),
         ("fluxo de energia", "ciclos biogeoquimicos", "nicho ecologico", "sucessao ecologica")),
        ("saude", "Corpo humano, saúde e doenças", "Biologia", (14, 13, 29, 30, 2),
         ("doenca", "virus", "bacteria", "vacina", "imunidade", "anticorpo", "infeccao", "epidemia", "parasita",
          "hormonio", "sistema digestorio", "sistema nervoso", "sangue", "alimentacao", "obesidade", "medicamento"),
         ("sistema imunologico", "transmissao da doenca", "saude publica")),
    ),
    "CH": (
        ("brasil-colonia-imperio", "Brasil: colônia e império", "História", (1, 2, 3, 11, 13, 16, 18),
         ("colonial", "colonia", "escravidao", "escravos", "senzala", "engenho", "quilombo", "capitanias",
          "bandeirantes", "mineracao", "imperio", "dom pedro", "independencia do brasil", "cafe"),
         ("brasil colonia", "periodo colonial", "abolicao", "brasil imperial")),
        ("brasil-republica", "Brasil republicano", "História", (11, 12, 13, 15, 21, 22, 24),
         ("republica", "getulio vargas", "estado novo", "ditadura militar", "golpe de 1964", "constituicao de 1988",
          "redemocratizacao", "populismo", "eleicoes", "presidente"),
         ("era vargas", "regime militar", "republica velha", "anistia")),
        ("historia-geral", "História geral", "História", (1, 3, 7, 9, 13, 15, 16),
         ("antiguidade", "grecia", "roma", "idade media", "feudalismo", "renascimento", "iluminismo",
          "revolucao francesa", "revolucao industrial", "imperialismo", "guerra mundial", "guerra fria",
          "nazismo", "fascismo", "revolucao russa", "colonizacao da america"),
         ("revolucao industrial", "primeira guerra", "segunda guerra", "guerra fria")),
        ("cidadania", "Cidadania, direitos e movimentos sociais", "História e Sociologia", (10, 12, 21, 22, 23, 24, 25),
         ("direitos", "cidadania", "democracia", "movimento social", "greve", "sindicato", "voto", "justica",
          "constituicao", "politicas publicas", "inclusao", "desigualdade", "racismo", "feminismo"),
         ("direitos humanos", "direitos civis", "acoes afirmativas", "movimentos sociais")),
        ("cultura", "Cultura, identidade e patrimônio", "História e Sociologia", (1, 2, 3, 4, 5),
         ("cultura", "patrimonio", "indigena", "afro", "religiao", "festa popular", "identidade", "memoria",
          "tradicao", "folclore", "museu"),
         ("patrimonio cultural", "diversidade cultural", "cultura material")),
        ("geografia-fisica", "Geografia física e questões ambientais", "Geografia", (26, 27, 28, 29, 30, 6),
         ("clima", "relevo", "solo", "vegetacao", "bioma", "cerrado", "amazonia", "caatinga", "bacia hidrografica",
          "rio", "chuva", "erosao", "desmatamento", "aquecimento global", "recursos naturais", "seca"),
         ("mudanca climatica", "efeito estufa", "unidades de conservacao", "dominios morfoclimaticos")),
        ("geografia-urbana", "População, cidades e migrações", "Geografia", (8, 10, 18, 19, 26, 27),
         ("populacao", "cidade", "urbana", "urbanizacao", "metropole", "favela", "migracao", "imigracao",
          "emigracao", "demografia", "natalidade", "envelhecimento", "moradia", "saneamento"),
         ("crescimento populacional", "segregacao espacial", "piramide etaria", "exodo rural")),
        ("geografia-economica", "Economia, indústria e agricultura", "Geografia", (7, 8, 9, 16, 17, 18, 19, 20),
         ("industria", "industrializacao", "agricultura", "agronegocio", "agropecuaria", "exportacao",
          "globalizacao", "comercio", "mercado", "energia", "petroleo", "transporte", "renda", "emprego",
          "trabalho", "tecnologia na producao"),
         ("divisao internacional do trabalho", "reforma agraria", "matriz energetica", "blocos economicos")),
        ("cartografia", "Cartografia e representação do espaço", "Geografia", (6, 26),
         ("mapa", "escala", "projecao", "cartografia", "coordenadas geograficas", "latitude", "longitude",
          "fuso horario", "imagem de satelite", "legenda do mapa"),
         ("projecao cartografica", "representacao cartografica")),
        ("filosofia-sociologia", "Filosofia e sociologia", "Filosofia e Sociologia", (12, 14, 15, 21, 23, 24),
         ("filosofia", "filosofo", "sociologia", "socrates", "platao", "aristoteles", "kant", "hobbes", "locke",
          "rousseau", "marx", "weber", "durkheim", "etica", "moral", "contrato social", "estado moderno"),
         ("pensamento filosofico", "teoria sociologica")),
    ),
}

EXIGE_TERMO_FORTE = ("geometria-analitica",)  # tema específico demais para rotular por termo genérico

LIMIAR = 2.0          # pontuação mínima para rotular
MAX_TOPICOS = 2       # uma questão pode legitimamente cruzar dois conteúdos
PESO_HABILIDADE = 1.0  # reforço quando a habilidade da Matriz combina com o tópico


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t)


def _ocorre(termo: str, texto: str) -> bool:
    if not termo.replace(" ", "").isalnum():      # termos com símbolos: busca direta
        return termo in texto
    return re.search(rf"\b{re.escape(termo)}", texto) is not None


def pontuar(texto: str, area: str, habilidade: int | None = None) -> list[tuple[str, float]]:
    """Pontuação de cada tópico da área para um texto (maior é melhor)."""
    t = normalizar(texto)
    saida = []
    for tid, _nome, _disc, habs, termos, fortes in TAXONOMIA.get(area, ()):
        n_fortes = sum(1 for x in fortes if _ocorre(normalizar(x), t))
        if tid in EXIGE_TERMO_FORTE and not n_fortes:
            continue
        p = sum(1.0 for x in termos if _ocorre(normalizar(x), t))
        p += 2.0 * n_fortes
        if p and habilidade is not None and habilidade in habs:
            p += PESO_HABILIDADE
        if p:
            saida.append((tid, round(p, 2)))
    return sorted(saida, key=lambda x: -x[1])


def classificar(texto: str, area: str, habilidade: int | None = None) -> list[str]:
    """Tópicos da questão, do mais provável ao menos. Lista vazia quando não há evidência."""
    pontos = [(tid, p) for tid, p in pontuar(texto, area, habilidade) if p >= LIMIAR]
    if not pontos:
        return []
    corte = pontos[0][1] - 1.0                     # só mantém o que chega perto do primeiro
    return [tid for tid, p in pontos[:MAX_TOPICOS] if p >= corte]


def rotular(itens: pd.DataFrame, col_texto: str = "enunciado", col_alt: str | None = "alternativas") -> pd.DataFrame:
    """Acrescenta a coluna `topicos` (lista de ids) ao DataFrame de itens."""
    out = itens.copy()
    textos = out[col_texto].fillna("").astype(str)
    if col_alt and col_alt in out:
        textos = textos + " " + out[col_alt].fillna("").astype(str)
    out["topicos"] = [
        classificar(txt, area, int(h) if pd.notna(h) else None)
        for txt, area, h in zip(textos, out["area"], out.get("habilidade", pd.Series([None] * len(out))))
    ]
    return out


def catalogo() -> list[dict]:
    """Taxonomia em formato de dados, para o app e para os relatórios."""
    return [{"id": tid, "nome": nome, "area": area, "disciplina": disc}
            for area, topicos in TAXONOMIA.items()
            for tid, nome, disc, _h, _t, _f in topicos]


def cobertura(itens: pd.DataFrame) -> pd.DataFrame:
    """Quantas questões receberam tópico, por área."""
    com = itens["topicos"].apply(bool)
    return (itens.assign(com_topico=com).groupby("area")
            .agg(itens=("com_topico", "size"), com_topico=("com_topico", "sum"))
            .assign(cobertura=lambda d: (d["com_topico"] / d["itens"]).round(3)).reset_index())
