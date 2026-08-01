"""Views do painel — tudo é buscado na API no momento da requisição."""

from __future__ import annotations

import logging

from django.http import JsonResponse
from django.shortcuts import redirect, render

from .services import busca
from .services.arena_client import ArenaAuthError, ArenaError, cliente_compartilhado

logger = logging.getLogger(__name__)


def _inteiro(valor, padrao=1, minimo=1):
    try:
        return max(minimo, int(str(valor).strip()))
    except (TypeError, ValueError):
        return padrao


def _erro(request, template, contexto, exc, status=502):
    """Renderiza a página com o aviso no lugar dos resultados."""
    if isinstance(exc, ArenaAuthError):
        contexto["erro_titulo"] = "Não foi possível autenticar na API"
        status = 401
    else:
        contexto["erro_titulo"] = "A API não respondeu como esperado"
    contexto["erro"] = str(exc)
    contexto["sem_credenciais"] = "Credenciais não configuradas" in str(exc)
    return render(request, template, contexto, status=status)


def consulta(request):
    """Barra de consulta + resultados renderizados direto da API."""
    termo = (request.GET.get("q") or "").strip()
    pagina = _inteiro(request.GET.get("page"))
    de = _inteiro(request.GET.get("de"))

    contexto = {"termo": termo, "pagina_atual": pagina, "aba": "vivo"}

    try:
        cliente = cliente_compartilhado()
        resultado = busca.consultar(cliente, termo, pagina=pagina, de=de)
    except ArenaError as exc:
        return _erro(request, "jogadores/consulta.html", contexto, exc)

    # Consulta por ID cai direto na ficha do jogador.
    if resultado.modo == "id" and resultado.jogadores:
        return redirect("jogadores:detalhe", pk=resultado.jogadores[0].id)

    contexto["resultado"] = resultado
    return render(request, "jogadores/consulta.html", contexto)


def detalhe(request, pk: int):
    """Ficha técnica completa — uma requisição a `/jogadores/{id}`."""
    contexto = {"termo": request.GET.get("q") or "", "jogador_id": pk, "aba": "vivo"}
    try:
        jogador = busca.obter_jogador(cliente_compartilhado(), pk)
    except ArenaError as exc:
        return _erro(request, "jogadores/detalhe.html", contexto, exc)

    contexto["jogador"] = jogador
    contexto["ficha"] = jogador.detalhe
    return render(request, "jogadores/detalhe.html", contexto)


def saude(request):
    """Healthcheck do contêiner — não toca a API, para não gastar rate limit."""
    return JsonResponse({"ok": True})


def sugestoes(request):
    """Autocomplete — só responde quando a API tem filtro no servidor.

    Sem filtro server-side, sugerir a cada tecla exigiria varrer páginas; nesse
    caso a resposta diz `disponivel: false` e o campo simplesmente não abre.
    """
    termo = (request.GET.get("q") or "").strip()
    if len(termo) < 2 or termo.isdigit():
        return JsonResponse({"disponivel": True, "resultados": []})

    try:
        cliente = cliente_compartilhado()
        parametro = busca.detectar_filtro_servidor(cliente)
        if not parametro:
            return JsonResponse({"disponivel": False, "resultados": []})
        pagina = busca.obter_pagina(cliente, 1, {parametro: termo})
    except ArenaError as exc:
        logger.warning("Autocomplete indisponível: %s", exc)
        return JsonResponse({"disponivel": False, "resultados": []})

    return JsonResponse({
        "disponivel": True,
        "resultados": [
            {
                "id": j.id, "nome": j.nome, "overall": j.overall,
                "posicao": j.posicao, "nacionalidade": j.nacionalidade, "foto": j.foto,
            }
            for j in pagina.jogadores[:8]
        ],
    })
