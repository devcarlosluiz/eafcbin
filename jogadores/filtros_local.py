"""Busca, filtros e ordenação do painel local (lê do acervo, não da API)."""

from __future__ import annotations

import unicodedata

from django.db.models import Q, QuerySet

#: rótulo → expressão de ordenação para o `order_by`.
ORDENACOES = {
    "overall": ("Overall (maior)", ["-overall", "nome"]),
    "overall_asc": ("Overall (menor)", ["overall", "nome"]),
    "idade_asc": ("Idade (mais novo)", ["idade", "-overall"]),
    "idade": ("Idade (mais velho)", ["-idade", "-overall"]),
    "nome": ("Nome (A–Z)", ["nome"]),
    "multa": ("Multa (maior)", ["-multa", "-overall"]),
    "recentes": ("Atualizados agora", ["-alterado_em", "-overall"]),
}
ORDENACAO_PADRAO = "overall"

SITUACOES = {
    "": "Todas",
    "meus": "Meus jogadores",
    "a_venda": "À venda",
    "leilao": "Em leilão",
    "favoritos": "Favoritos",
    "livres": "Sem dono",
    "com_ficha": "Com ficha técnica",
    "ausentes": "Ausentes da API",
}


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in base if not unicodedata.combining(c))


def _int(valor, minimo=None, maximo=None):
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    if minimo is not None and n < minimo:
        n = minimo
    if maximo is not None and n > maximo:
        n = maximo
    return n


def parametros(get) -> dict:
    ordenar = get.get("ordenar") or ORDENACAO_PADRAO
    if ordenar not in ORDENACOES:
        ordenar = ORDENACAO_PADRAO
    situacao = get.get("situacao") or ""
    if situacao not in SITUACOES:
        situacao = ""
    return {
        "q": (get.get("q") or "").strip(),
        "posicao": (get.get("posicao") or "").strip().upper(),
        "nacionalidade": (get.get("nacionalidade") or "").strip(),
        "overall_min": _int(get.get("overall_min"), 0, 99),
        "overall_max": _int(get.get("overall_max"), 0, 99),
        "situacao": situacao,
        "ordenar": ordenar,
    }


def aplicar(qs: QuerySet, f: dict) -> QuerySet:
    if f["q"]:
        # Cada termo precisa casar em algum campo mostrado (nunca no clube da
        # liga, que a interface esconde). A busca sem acento vai contra
        # `busca_norm` (nome+nacionalidade+posição já normalizados); nome
        # completo e time (do detalhe) entram como reforço, com acento.
        for termo in f["q"].split():
            alvo = _sem_acento(termo).casefold()
            qs = qs.filter(
                Q(busca_norm__contains=alvo)
                | Q(detalhe__nome_completo__icontains=termo)
                | Q(detalhe__time__icontains=termo)
            )
        qs = qs.distinct()

    if f["posicao"]:
        qs = qs.filter(posicao__iexact=f["posicao"])
    if f["nacionalidade"]:
        qs = qs.filter(nacionalidade=f["nacionalidade"])
    if f["overall_min"] is not None:
        qs = qs.filter(overall__gte=f["overall_min"])
    if f["overall_max"] is not None:
        qs = qs.filter(overall__lte=f["overall_max"])

    situacao = f["situacao"]
    if situacao == "meus":
        qs = qs.filter(meu_jogador=True)
    elif situacao == "a_venda":
        qs = qs.filter(a_venda=True)
    elif situacao == "leilao":
        qs = qs.filter(in_leilao=True)
    elif situacao == "favoritos":
        qs = qs.filter(favorito=True)
    elif situacao == "livres":
        qs = qs.filter(usuario_id__isnull=True)
    elif situacao == "com_ficha":
        qs = qs.filter(detalhe__isnull=False)
    elif situacao == "ausentes":
        qs = qs.filter(ausente_desde__isnull=False)

    return qs.order_by(*ORDENACOES[f["ordenar"]][1])


def ativos(f: dict) -> list[dict]:
    """Filtros preenchidos, para os chips de remoção."""
    rotulos = {
        "q": "Busca", "posicao": "Posição", "nacionalidade": "País",
        "overall_min": "Overall ≥", "overall_max": "Overall ≤", "situacao": "Situação",
    }
    chips = []
    for chave, rotulo in rotulos.items():
        valor = f.get(chave)
        if valor in (None, "", []):
            continue
        texto = SITUACOES[valor] if chave == "situacao" else valor
        chips.append({"chave": chave, "rotulo": rotulo, "valor": texto})
    return chips
