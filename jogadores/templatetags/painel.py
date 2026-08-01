"""Filtros e tags de apresentação do painel."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


# ---------------------------------------------------------------------------
# Números e moeda
# ---------------------------------------------------------------------------
@register.filter
def moeda_br(valor) -> str:
    """`475200` → `475.200`. Sem centavos: os valores da liga são inteiros."""
    try:
        numero = Decimal(valor or 0)
    except (TypeError, InvalidOperation):
        return "0"
    return f"{numero:,.0f}".replace(",", ".")


@register.filter
def compacto(valor) -> str:
    """`1250000` → `1,25 mi`. Usado nos cards, onde falta espaço."""
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError):
        return "0"
    for limite, sufixo in ((1_000_000_000, "bi"), (1_000_000, "mi"), (1_000, "mil")):
        if abs(numero) >= limite:
            reduzido = numero / limite
            texto = f"{reduzido:.2f}" if reduzido < 10 else f"{reduzido:.1f}"
            return f"{texto.rstrip('0').rstrip('.').replace('.', ',')} {sufixo}"
    return f"{numero:,.0f}".replace(",", ".")


# ---------------------------------------------------------------------------
# Cores por faixa de valor
# ---------------------------------------------------------------------------
def _faixa(valor: int) -> str:
    if valor >= 85:
        return "elite"
    if valor >= 75:
        return "alto"
    if valor >= 65:
        return "medio"
    if valor >= 50:
        return "baixo"
    return "fraco"


ESCALA = {
    "elite": "bg-emerald-500",
    "alto": "bg-lime-500",
    "medio": "bg-amber-500",
    "baixo": "bg-orange-500",
    "fraco": "bg-rose-500",
}
ESCALA_TEXTO = {
    "elite": "text-emerald-400",
    "alto": "text-lime-400",
    "medio": "text-amber-400",
    "baixo": "text-orange-400",
    "fraco": "text-rose-400",
}


@register.filter
def cor_barra(valor) -> str:
    return ESCALA[_faixa(int(valor or 0))]


@register.filter
def cor_texto(valor) -> str:
    return ESCALA_TEXTO[_faixa(int(valor or 0))]


SETORES = {
    "goleiro": "from-amber-400 to-amber-600",
    "defesa": "from-sky-400 to-sky-600",
    "meio": "from-emerald-400 to-emerald-600",
    "ataque": "from-rose-400 to-rose-600",
}


@register.filter
def cor_setor(setor) -> str:
    return SETORES.get(setor, SETORES["meio"])


# ---------------------------------------------------------------------------
# Radar (SVG)
# ---------------------------------------------------------------------------
@register.simple_tag
def radar_pontos(eixos, raio=100, centro=110, escala=99):
    """Polígono do radar: valores (0–99) → `"x,y x,y ..."`."""
    if not eixos:
        return ""
    total = len(eixos)
    pontos = []
    for indice, eixo in enumerate(eixos):
        valor = eixo["valor"] if isinstance(eixo, dict) else eixo
        angulo = -math.pi / 2 + 2 * math.pi * indice / total
        distancia = raio * max(0, min(escala, int(valor or 0))) / escala
        pontos.append(
            f"{centro + distancia * math.cos(angulo):.1f},"
            f"{centro + distancia * math.sin(angulo):.1f}"
        )
    return mark_safe(" ".join(pontos))


@register.simple_tag
def radar_rotulos(eixos, raio=100, centro=110, folga=22):
    """Posição dos rótulos ao redor do radar."""
    saida = []
    total = len(eixos or [])
    for indice, eixo in enumerate(eixos or []):
        angulo = -math.pi / 2 + 2 * math.pi * indice / total
        saida.append({
            "sigla": eixo["sigla"],
            "valor": eixo["valor"],
            "rotulo": eixo["rotulo"],
            "x": round(centro + (raio + folga) * math.cos(angulo), 1),
            "y": round(centro + (raio + folga) * math.sin(angulo), 1),
        })
    return saida


@register.simple_tag
def radar_grade(niveis=4, raio=100, centro=110, lados=6):
    """Anéis de referência do radar."""
    aneis = []
    for nivel in range(1, niveis + 1):
        r = raio * nivel / niveis
        pontos = []
        for indice in range(lados):
            angulo = -math.pi / 2 + 2 * math.pi * indice / lados
            pontos.append(
                f"{centro + r * math.cos(angulo):.1f},{centro + r * math.sin(angulo):.1f}"
            )
        aneis.append(" ".join(pontos))
    return aneis


@register.simple_tag
def radar_eixos(raio=100, centro=110, lados=6):
    linhas = []
    for indice in range(lados):
        angulo = -math.pi / 2 + 2 * math.pi * indice / lados
        linhas.append({
            "x": round(centro + raio * math.cos(angulo), 1),
            "y": round(centro + raio * math.sin(angulo), 1),
            "cx": centro, "cy": centro,
        })
    return linhas


# ---------------------------------------------------------------------------
# Diversos
# ---------------------------------------------------------------------------
@register.filter
def estrelas(quantidade) -> str:
    try:
        cheias = max(0, min(5, int(quantidade or 0)))
    except (TypeError, ValueError):
        cheias = 0
    return "★" * cheias + "☆" * (5 - cheias)


@register.filter
def pe_extenso(pe) -> str:
    return {"D": "Destro", "E": "Canhoto"}.get((pe or "").upper(), "—")


@register.filter
def percentual(valor, maximo=99):
    try:
        return min(100, round(100 * float(valor or 0) / float(maximo)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0
