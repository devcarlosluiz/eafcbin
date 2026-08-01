"""Varre a lista paginada da API e atualiza o acervo.

    python manage.py sincronizar_jogadores                  # varredura completa
    python manage.py sincronizar_jogadores --paginas 20      # amostra rápida
    python manage.py sincronizar_jogadores --de 500          # retomar

Com `per_page` fixo em 10 e ~1,2 s entre chamadas, a base inteira (1.942
páginas) leva cerca de 40 min. O comando é idempotente: só grava o que mudou.
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...models import Execucao
from ...services import arena_client, persistencia
from ...services.arena_client import ArenaError


class Command(BaseCommand):
    help = "Atualiza o acervo com a lista de jogadores da API."

    def add_arguments(self, parser):
        parser.add_argument("--de", type=int, default=1, help="Página inicial.")
        parser.add_argument("--paginas", type=int, default=None,
                            help="Quantas páginas ler (padrão: todas).")
        parser.add_argument("--marcar-ausentes", action="store_true",
                            help="Após uma varredura completa, sinalizar quem sumiu.")

    def handle(self, *args, **opcoes):
        pagina = max(1, opcoes["de"])
        limite = opcoes["paginas"]
        completa = pagina == 1 and limite is None

        execucao = Execucao.objects.create(tipo="lista")
        comeco = time.monotonic()
        contagem = {persistencia.CRIADO: 0, persistencia.ALTERADO: 0, persistencia.IGUAL: 0}
        campos = paginas = 0
        vistos: set[int] = set()
        interrompida = False

        try:
            # Resolvido pelo módulo, não pelo nome: mantém o comando testável.
            cliente = arena_client.cliente_compartilhado()
            while True:
                envelope = cliente.listar_jogadores(pagina)
                ultima = envelope.get("last_page") or pagina
                agora = timezone.now()

                for item in envelope.get("data") or []:
                    situacao, quantidade = persistencia.salvar_jogador(item, agora)
                    contagem[situacao] += 1
                    campos += quantidade
                    if item.get("id"):
                        vistos.add(int(item["id"]))

                paginas += 1
                if paginas % 25 == 0 or pagina >= ultima:
                    self.stdout.write(
                        f"  página {pagina}/{ultima} — "
                        f"+{contagem[persistencia.CRIADO]} novos, "
                        f"~{contagem[persistencia.ALTERADO]} alterados, "
                        f"={contagem[persistencia.IGUAL]} iguais"
                    )

                if limite is not None and paginas >= limite:
                    break
                if pagina >= ultima or not envelope.get("next_page_url"):
                    break
                pagina += 1

        except KeyboardInterrupt:
            interrompida = True
            self.stdout.write(self.style.WARNING("\nInterrompido pelo usuário."))
        except ArenaError as exc:
            execucao.situacao = "erro"
            execucao.mensagem = str(exc)
            execucao.erros = 1
            self._encerrar(execucao, paginas, contagem, campos)
            raise CommandError(str(exc)) from exc

        ausentes = 0
        if completa and not interrompida and opcoes["marcar_ausentes"]:
            ausentes = persistencia.marcar_ausentes(vistos)

        execucao.situacao = "interrompida" if interrompida else "ok"
        self._encerrar(execucao, paginas, contagem, campos)

        resumo = (
            f"Concluído em {time.monotonic() - comeco:.0f}s — {paginas} páginas · "
            f"{contagem[persistencia.CRIADO]} novos · "
            f"{contagem[persistencia.ALTERADO]} alterados ({campos} campos) · "
            f"{contagem[persistencia.IGUAL]} sem mudança"
        )
        if ausentes:
            resumo += f" · {ausentes} marcados como ausentes"
        self.stdout.write(self.style.SUCCESS(resumo))

    @staticmethod
    def _encerrar(execucao, paginas, contagem, campos):
        execucao.paginas = paginas
        execucao.criados = contagem[persistencia.CRIADO]
        execucao.atualizados = contagem[persistencia.ALTERADO]
        execucao.inalterados = contagem[persistencia.IGUAL]
        execucao.campos_alterados = campos
        execucao.terminada_em = timezone.now()
        execucao.save()
