"""Cálculo do próximo disparo do agendador diário.

Isolado do comando para poder ser testado sem relógio nem sono.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta


def ler_horario(texto: str) -> time:
    """`"03:30"` → `time(3, 30)`. Aceita `"3:5"` e `"03:30:00"`."""
    partes = (texto or "").strip().split(":")
    try:
        hora = int(partes[0])
        minuto = int(partes[1]) if len(partes) > 1 else 0
        segundo = int(partes[2]) if len(partes) > 2 else 0
        return time(hora, minuto, segundo)
    except (ValueError, IndexError) as exc:
        raise ValueError(
            f"Horário inválido: {texto!r}. Use HH:MM (ex.: 03:30)."
        ) from exc


def proxima_execucao(agora: datetime, horario: time) -> datetime:
    """Próxima ocorrência de `horario` a partir de `agora` (mesmo fuso).

    Se o horário de hoje já passou — ou é exatamente agora — vai para amanhã,
    para não disparar duas vezes no mesmo dia.
    """
    alvo = agora.replace(
        hour=horario.hour, minute=horario.minute,
        second=horario.second, microsecond=0,
    )
    if alvo <= agora:
        alvo += timedelta(days=1)
    return alvo
