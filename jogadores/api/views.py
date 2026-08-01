"""Endpoints JSON do acervo para consumo externo (painel de campeonatos).

Somente leitura. Reaproveita os mesmos filtros do painel local
(ver `filtros_local`) para listar/buscar, e devolve a ficha completa por
jogador — atributos, radar, características e especialidades já rotuladas.
"""

from __future__ import annotations

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination

from .. import filtros_local
from ..models import Jogador
from .serializers import JogadorSerializer


class JogadoresPaginacao(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class JogadorListaAPIView(ListAPIView):
    """`GET /api/v1/jogadores/` — lista paginada, com os filtros do painel local
    (`q`, `posicao`, `nacionalidade`, `overall_min`, `overall_max`, `situacao`,
    `ordenar`) mais `page`/`page_size`.
    """

    serializer_class = JogadorSerializer
    pagination_class = JogadoresPaginacao

    def get_queryset(self):
        filtros = filtros_local.parametros(self.request.query_params)
        return filtros_local.aplicar(
            Jogador.objects.select_related("detalhe"), filtros
        )


class JogadorDetalheAPIView(RetrieveAPIView):
    """`GET /api/v1/jogadores/{id}/` — jogador com a ficha técnica completa."""

    serializer_class = JogadorSerializer
    queryset = Jogador.objects.select_related("detalhe")
