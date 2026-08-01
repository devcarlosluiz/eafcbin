"""Serialização do acervo para a API externa — devolve o jogador por inteiro.

Reaproveita as mesmas colunas e propriedades do painel local
(ver `models.Jogador` / `models.JogadorDetalhe`), incluindo os payloads crus,
para que o painel de campeonatos consumidor não perca nenhum campo.
"""

from __future__ import annotations

from rest_framework import serializers

from ..models import Jogador, JogadorDetalhe


class JogadorDetalheSerializer(serializers.ModelSerializer):
    radar = serializers.SerializerMethodField()
    grupos_atributos = serializers.SerializerMethodField()
    caracteristicas_rotuladas = serializers.SerializerMethodField()
    especialidades_rotuladas = serializers.SerializerMethodField()

    class Meta:
        model = JogadorDetalhe
        exclude = ["jogador"]

    def get_radar(self, obj: JogadorDetalhe) -> list[dict]:
        return obj.radar

    def get_grupos_atributos(self, obj: JogadorDetalhe) -> list[dict]:
        return obj.grupos_atributos

    def get_caracteristicas_rotuladas(self, obj: JogadorDetalhe) -> list[str]:
        return obj.caracteristicas_rotuladas

    def get_especialidades_rotuladas(self, obj: JogadorDetalhe) -> list[str]:
        return obj.especialidades_rotuladas


class JogadorSerializer(serializers.ModelSerializer):
    posicao_nome = serializers.CharField(read_only=True)
    setor = serializers.CharField(read_only=True)
    tem_ficha = serializers.BooleanField(read_only=True)
    detalhe = JogadorDetalheSerializer(read_only=True)

    class Meta:
        model = Jogador
        #: `busca_norm` é um índice de busca interno, sem valor para quem consome a API.
        exclude = ["busca_norm"]
