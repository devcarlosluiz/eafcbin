"""Rótulos legíveis (pt-BR) para os códigos da API interna.

A API devolve as características e especialidades como *flags* numeradas
(`C01`..`C82`, `E01`..`E17`), sem nome legível. Os dois mapas abaixo traduzem
esses códigos.

ATENÇÃO — apenas quatro correspondências estão confirmadas pela documentação
da API (`api.MD`): ``C01``, ``C06``, ``E02`` e ``E14``. As demais são a melhor
aproximação a partir da lista de PlayStyles/traits do jogo e **devem ser
conferidas** contra o payload real. Use::

    python manage.py descobrir_flags --amostra 40

para listar quais flags realmente aparecem e com que frequência, e ajuste este
arquivo. Códigos ausentes do mapa nunca quebram a aplicação: `rotulo_*` cai
para o próprio código.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Características — C01..C82
# ---------------------------------------------------------------------------
CARACTERISTICAS: dict[str, str] = {
    # --- Finalização -------------------------------------------------------
    "C01": "Chute colocado",            # confirmado (api.MD)
    "C02": "Cavadinha",
    "C03": "Chute forte",
    "C04": "Chute de fora da área",
    "C05": "Chute com o lado de fora",
    "C06": "Acrobata",                  # confirmado (api.MD)
    "C07": "Voleio potente",
    "C08": "Bicicleta",
    "C09": "Cabeceio forte",
    "C10": "Finalizador de área",
    # --- Bola parada -------------------------------------------------------
    "C11": "Especialista em bola parada",
    "C12": "Falta com efeito",
    "C13": "Falta com força",
    "C14": "Cobrador de pênalti",
    "C15": "Cobrador de escanteio",
    "C16": "Lateral longo",
    # --- Passe -------------------------------------------------------------
    "C17": "Passe tenso",
    "C18": "Passe incisivo",
    "C19": "Lançamento",
    "C20": "Passe curvado",
    "C21": "Tiki-taka",
    "C22": "Armador de jogo",
    "C23": "Cruzamento antecipado",
    "C24": "Cruzamento rasteiro",
    "C25": "Passe de primeira",
    "C26": "Trivela",
    # --- Drible / controle -------------------------------------------------
    "C27": "Driblador técnico",
    "C28": "Driblador veloz",
    "C29": "Malandro",
    "C30": "Estilo",
    "C31": "Primeiro toque",
    "C32": "Técnico",
    "C33": "Elástico",
    "C34": "Pedalada",
    "C35": "Giro rápido",
    "C36": "Proteção de bola",
    # --- Defesa ------------------------------------------------------------
    "C37": "Bloqueio",
    "C38": "Antecipação",
    "C39": "Interceptação",
    "C40": "Carrinho",
    "C41": "Marcação lateral",
    "C42": "Marcação sob pressão",
    "C43": "Brutamontes",
    "C44": "Desarme agressivo",
    "C45": "Linha de impedimento",
    "C46": "Cobertura defensiva",
    # --- Físico ------------------------------------------------------------
    "C47": "Domínio aéreo",
    "C48": "Incansável",
    "C49": "Passada rápida",
    "C50": "Explosivo",
    "C51": "Força bruta",
    "C52": "Equilíbrio",
    "C53": "Fôlego extra",
    "C54": "Resistente a lesões",
    "C55": "Propenso a lesões",
    "C56": "Recuperação rápida",
    # --- Mental / comportamento -------------------------------------------
    "C57": "Liderança",
    "C58": "Jogador de equipe",
    "C59": "Individualista",
    "C60": "Frieza",
    "C61": "Queridinho da torcida",
    "C62": "Jogador de um clube só",
    "C63": "Reclama com a arbitragem",
    "C64": "Simulador",
    "C65": "Evita o pé ruim",
    "C66": "Ambidestro",
    "C67": "Jogador sólido",
    "C68": "Entra forte no desarme",
    "C69": "Se apoia no marcador",
    "C70": "Visão de jogo apurada",
    # --- Goleiro -----------------------------------------------------------
    "C71": "GL — Jogo de pés",
    "C72": "GL — Domínio de cruzamentos",
    "C73": "GL — Saída do gol",
    "C74": "GL — Cauteloso nos cruzamentos",
    "C75": "GL — Arremesso longo",
    "C76": "GL — Alcance",
    "C77": "GL — Reflexos rápidos",
    "C78": "GL — Rebatedor",
    "C79": "GL — Defesa com os pés",
    "C80": "GL — Soco firme",
    "C81": "GL — Pênaltis",
    "C82": "GL — Reposição rápida",
}

# ---------------------------------------------------------------------------
# Especialidades — E01..E17
# ---------------------------------------------------------------------------
ESPECIALIDADES: dict[str, str] = {
    "E01": "Ameaça aérea",
    "E02": "Velocista",                 # confirmado (api.MD)
    "E03": "Driblador",
    "E04": "Armador",
    "E05": "Motor",
    "E06": "Chutes de longe",
    "E07": "Cruzador",
    "E08": "Especialista em faltas",
    "E09": "Acrobata",
    "E10": "Força",
    "E11": "Desarme",
    "E12": "Tático",
    "E13": "Zagueiro completo",
    "E14": "Matador",                   # confirmado (api.MD)
    "E15": "Meio-campista completo",
    "E16": "Atacante completo",
    "E17": "Goleiro completo",
}

# ---------------------------------------------------------------------------
# Demais mapas de apoio
# ---------------------------------------------------------------------------
POSICOES = {
    "GOL": "Goleiro",
    "ZAG": "Zagueiro",
    "LD": "Lateral-direito",
    "LE": "Lateral-esquerdo",
    "VOL": "Volante",
    "MC": "Meio-campista",
    "MD": "Meia-direita",
    "ME": "Meia-esquerda",
    "MEI": "Meia-atacante",
    "PD": "Ponta-direita",
    "PE": "Ponta-esquerda",
    "ATA": "Atacante",
    "SA": "Segundo atacante",
}

#: Agrupamento dos setores por posição — usado para colorir a interface.
SETOR_POR_POSICAO = {
    "GOL": "goleiro",
    "ZAG": "defesa",
    "LD": "defesa",
    "LE": "defesa",
    "VOL": "meio",
    "MC": "meio",
    "MD": "meio",
    "ME": "meio",
    "MEI": "meio",
    "PD": "ataque",
    "PE": "ataque",
    "SA": "ataque",
    "ATA": "ataque",
}

#: Atributos de linha, agrupados como no card do jogo.
GRUPOS_ATRIBUTOS = [
    ("Ataque", [
        ("cruzamento", "Cruzamento"),
        ("finalizacao", "Finalização"),
        ("cabeceio", "Cabeceio"),
        ("passe_curto", "Passe curto"),
        ("voleio", "Voleio"),
    ]),
    ("Habilidade", [
        ("drible", "Drible"),
        ("curva", "Curva"),
        ("cobranca_falta", "Cobrança de falta"),
        ("passe_longe", "Passe longo"),
        ("controle_bola", "Controle de bola"),
    ]),
    ("Movimento", [
        ("aceleracao", "Aceleração"),
        ("velocidade_final", "Velocidade final"),
        ("agilidade", "Agilidade"),
        ("reacoes", "Reações"),
        ("equilibrio", "Equilíbrio"),
    ]),
    ("Potência", [
        ("forca_chute", "Força do chute"),
        ("pulo", "Pulo"),
        ("resistencia", "Resistência"),
        ("forca", "Força"),
        ("chute_longe", "Chute de longe"),
    ]),
    ("Mentalidade", [
        ("agressividade", "Agressividade"),
        ("posicionamento", "Posicionamento"),
        ("visao_jogo", "Visão de jogo"),
        ("penalti", "Pênalti"),
        ("compostura", "Compostura"),
    ]),
    ("Defesa", [
        ("marcacao", "Marcação"),
        ("roubada_bola", "Roubada de bola"),
        ("carrinho", "Carrinho"),
        ("interceptacoes", "Interceptações"),
    ]),
]

GRUPO_GOLEIRO = ("Goleiro", [
    ("salto", "Salto"),
    ("gk_habilidade_mao", "Habilidade com as mãos"),
    ("gk_habilidade_pe", "Habilidade com os pés"),
    ("gk_posicionamento", "Posicionamento"),
    ("gk_reflexo", "Reflexos"),
])

#: Eixos do radar (campo no payload → rótulo).
EIXOS_RADAR = [
    ("grafico_velocidade", "RIT"),
    ("grafico_finalizacao", "FIN"),
    ("grafico_passe", "PAS"),
    ("grafico_drible", "DRI"),
    ("grafico_defesa", "DEF"),
    ("grafico_fisico", "FIS"),
]

EIXOS_RADAR_LONGO = {
    "RIT": "Ritmo",
    "FIN": "Finalização",
    "PAS": "Passe",
    "DRI": "Drible",
    "DEF": "Defesa",
    "FIS": "Físico",
}


def rotulo_caracteristica(codigo: str) -> str:
    return CARACTERISTICAS.get(codigo, codigo)


def rotulo_especialidade(codigo: str) -> str:
    return ESPECIALIDADES.get(codigo, codigo)


def nome_posicao(sigla: str) -> str:
    return POSICOES.get((sigla or "").upper(), sigla or "—")


def setor(sigla: str) -> str:
    return SETOR_POR_POSICAO.get((sigla or "").upper(), "meio")


# ---------------------------------------------------------------------------
# Montagem do radar e dos grupos de atributos.
#
# Recebem um `valor(campo) -> int` para não amarrar a onde os atributos moram:
# o painel ao vivo lê de um dict (dominio.Ficha), o acervo lê de colunas do
# banco (models.JogadorDetalhe). Assim as duas telas renderizam idêntico.
# ---------------------------------------------------------------------------
def montar_radar(valor) -> list[dict]:
    return [
        {"sigla": sigla, "rotulo": EIXOS_RADAR_LONGO[sigla], "valor": valor(campo)}
        for campo, sigla in EIXOS_RADAR
    ]


def montar_grupos(valor, e_goleiro: bool) -> list[dict]:
    grupos = list(GRUPOS_ATRIBUTOS)
    if e_goleiro:
        grupos = grupos + [GRUPO_GOLEIRO]
    saida = []
    for titulo, campos in grupos:
        itens = [{"rotulo": rotulo, "valor": valor(campo)} for campo, rotulo in campos]
        media = round(sum(i["valor"] for i in itens) / len(itens)) if itens else 0
        saida.append({"titulo": titulo, "itens": itens, "media": media})
    return saida
