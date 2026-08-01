"""Agendador diário — roda a sincronização todo dia no horário configurado.

    python manage.py agendar_sincronizacao
    python manage.py agendar_sincronizacao --horario 04:00 --minutos-detalhes 180
    python manage.py agendar_sincronizacao --agora --uma-vez   # testar na hora

É um processo de longa duração: dorme até o horário, roda a lista inteira e
depois as fichas dentro do orçamento de tempo, e volta a dormir. No Docker ele
é o serviço `cron`, com `restart: unless-stopped`.

Preferindo o cron do sistema (ou o Agendador de Tarefas do Windows), ignore este
comando e chame direto:

    30 3 * * *  docker compose run --rm painel python manage.py sincronizar_jogadores
"""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...services.agendamento import ler_horario, proxima_execucao

logger = logging.getLogger("jogadores")


class Command(BaseCommand):
    help = "Roda a sincronização diariamente no horário configurado."

    def add_arguments(self, parser):
        parser.add_argument("--horario", default=None, help="HH:MM (padrão: SYNC_HORARIO).")
        parser.add_argument("--minutos-detalhes", type=float, default=None,
                            help="Orçamento das fichas técnicas por rodada.")
        parser.add_argument("--agora", action="store_true",
                            help="Roda uma vez ao subir, sem esperar o horário.")
        parser.add_argument("--uma-vez", action="store_true",
                            help="Encerra após a primeira rodada (útil para testar).")

    def handle(self, *args, **opcoes):
        cfg = settings.SINCRONIZACAO
        try:
            horario = ler_horario(opcoes["horario"] or cfg["HORARIO"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        minutos = opcoes["minutos_detalhes"]
        if minutos is None:
            minutos = cfg["MINUTOS_DETALHES"]
        rodar_agora = opcoes["agora"] or cfg["AO_INICIAR"]

        self.stdout.write(self.style.SUCCESS(
            f"Agendador ativo — todo dia às {horario:%H:%M} "
            f"({settings.TIME_ZONE}); fichas com {minutos:.0f} min por rodada."
        ))

        while True:
            if rodar_agora:
                rodar_agora = False
            else:
                alvo = proxima_execucao(timezone.localtime(), horario)
                espera = (alvo - timezone.localtime()).total_seconds()
                self.stdout.write(
                    f"Próxima rodada: {alvo:%d/%m/%Y %H:%M} "
                    f"(em {espera / 3600:.1f} h)."
                )
                self._dormir(espera)

            self._rodada(minutos)

            if opcoes["uma_vez"]:
                self.stdout.write("Rodada única concluída; encerrando.")
                return

    def _escrever(self, texto: str, estilo=None) -> None:
        """Imprime sem nunca falhar.

        O console do Windows usa cp1252: um caractere fora dessa tabela levanta
        `UnicodeEncodeError`. Num processo de longa duração, deixar um detalhe
        cosmético derrubar (ou pior, mascarar) a sincronização seria péssimo.
        """
        try:
            self.stdout.write(estilo(texto) if estilo else texto)
        except UnicodeEncodeError:
            self.stdout.write(texto.encode("ascii", "replace").decode("ascii"))

    def _dormir(self, segundos: float) -> None:
        """Dorme em fatias, para responder rápido a um SIGTERM do Docker."""
        fim = time.monotonic() + max(0.0, segundos)
        while True:
            restante = fim - time.monotonic()
            if restante <= 0:
                return
            time.sleep(min(60.0, restante))

    def _etapa(self, rotulo: str, comando: str, **opcoes) -> None:
        """Roda uma etapa isolada: falhar aqui não pode derrubar o agendador,
        que precisa sobreviver para tentar de novo amanhã."""
        self._escrever(f"> {rotulo}")
        try:
            call_command(comando, **opcoes)
        except Exception as exc:  # noqa: BLE001 — rede fora, API instável, etc.
            logger.error("%s falhou: %s", rotulo, exc)
            self._escrever(f"  {rotulo} falhou: {exc}", self.style.ERROR)

    def _rodada(self, minutos_detalhes: float) -> None:
        inicio = timezone.localtime()
        self._escrever(f"\n=== Rodada de {inicio:%d/%m %H:%M} ===", self.style.SUCCESS)

        self._etapa("Lista completa", "sincronizar_jogadores", marcar_ausentes=True)
        if minutos_detalhes > 0:
            self._etapa(
                f"Fichas tecnicas ({minutos_detalhes:.0f} min)",
                "sincronizar_detalhes", minutos=minutos_detalhes,
            )

        duracao = (timezone.localtime() - inicio).total_seconds() / 60
        self._escrever(f"=== Rodada encerrada ({duracao:.0f} min) ===\n", self.style.SUCCESS)
