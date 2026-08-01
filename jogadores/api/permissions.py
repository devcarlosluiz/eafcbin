"""Autorização da API externa — chave por header, administrada no admin.

Consumida pelo painel de campeonatos (outro domínio/servidor), sem sessão de
usuário. Cada chave é um registro de `ChaveApiExterna` (nome + token),
cadastrado e revogado pelo admin do Django — sem precisar reiniciar a
aplicação para uma chave nova entrar em vigor ou uma antiga parar de valer.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from ..models import ChaveApiExterna

CABECALHO_CHAVE = "X-API-Key"


class TemChaveApiValida(BasePermission):
    message = "Chave de API ausente ou inválida (header X-API-Key)."

    def has_permission(self, request, view) -> bool:
        chave = request.headers.get(CABECALHO_CHAVE, "")
        return bool(chave) and ChaveApiExterna.objects.filter(
            token=chave, ativa=True
        ).exists()
