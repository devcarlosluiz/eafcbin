"""Painel local — lê os jogadores do acervo (banco), não da API ao vivo.

Espelha o visual do painel de consulta, mas responde instantâneo e permite
filtrar por qualquer campo, já que os dados estão no banco.
"""

from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max
from django.shortcuts import get_object_or_404, render

from . import filtros_local
from .data import fifa_labels
from .models import Execucao, Jogador

POR_PAGINA = 16


def _opcoes_de_filtro():
    posicoes = (
        Jogador.objects.exclude(posicao="")
        .values_list("posicao", flat=True).order_by("posicao").distinct()
    )
    nacionalidades = (
        Jogador.objects.exclude(nacionalidade="")
        .values("nacionalidade").annotate(total=Count("pk"))
        .order_by("-total", "nacionalidade")[:120]
    )
    return {
        "posicoes": [(p, fifa_labels.nome_posicao(p)) for p in posicoes],
        "nacionalidades": list(nacionalidades),
    }


def players_local(request):
    """Lista paginada do acervo, com busca e filtros."""
    f = filtros_local.parametros(request.GET)
    qs = filtros_local.aplicar(Jogador.objects.select_related("detalhe"), f)

    resumo = qs.aggregate(
        total=Count("pk"), media=Avg("overall"), melhor=Max("overall"),
    )

    paginator = Paginator(qs, POR_PAGINA)
    pagina = paginator.get_page(request.GET.get("page"))
    intervalo = paginator.get_elided_page_range(
        pagina.number, on_each_side=1, on_ends=1
    )

    # Query string sem `page`, para os links de paginação e chips.
    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    contexto = {
        "aba": "local",
        "pagina": pagina,
        "intervalo_paginas": list(intervalo),
        "reticencias": paginator.ELLIPSIS,
        "querystring": querystring,
        "filtros": f,
        "chips": filtros_local.ativos(f),
        "resumo": resumo,
        "ordenacoes": [(k, v[0]) for k, v in filtros_local.ORDENACOES.items()],
        "situacoes": filtros_local.SITUACOES.items(),
        "base_vazia": not Jogador.objects.exists(),
        "ultima_sync": Execucao.objects.filter(tipo="lista", situacao="ok").first(),
        **_opcoes_de_filtro(),
    }
    return render(request, "jogadores/players_local.html", contexto)


def players_local_detalhe(request, pk: int):
    """Ficha técnica lida do acervo."""
    jogador = get_object_or_404(Jogador.objects.select_related("detalhe"), pk=pk)
    ficha = getattr(jogador, "detalhe", None)

    semelhantes = (
        Jogador.objects.filter(posicao=jogador.posicao)
        .exclude(pk=jogador.pk)
        .filter(overall__gte=jogador.overall - 3, overall__lte=jogador.overall + 3)
        .order_by("-overall")[:6]
    )

    return render(request, "jogadores/players_local_detalhe.html", {
        "aba": "local",
        "jogador": jogador,
        "ficha": ficha,
        "semelhantes": semelhantes,
    })
