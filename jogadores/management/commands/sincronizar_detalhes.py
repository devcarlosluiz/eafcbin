"""Atualiza as fichas técnicas — 1 requisição por jogador.

    python manage.py sincronizar_detalhes --minutos 120   # orçamento de tempo
    python manage.py sincronizar_detalhes --limite 500
    python manage.py sincronizar_detalhes --faltantes      # só quem nunca teve ficha

A ficha é uma chamada por jogador: a 1,2 s cada, os 19.415 jogadores levariam
~6,5 h. Por isso o padrão é **rodízio por orçamento de tempo**: a fila começa
por quem está sem ficha e segue pelos verificados há mais tempo, de modo que
algumas rodadas diárias cobrem a base inteira.
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import Execucao, Jogador
from ...services import arena_client, persistencia
from ...services.arena_client import ArenaError


class Command(BaseCommand):
    help = "Atualiza as fichas técnicas do acervo, em rodízio."

    def add_arguments(self, parser):
        parser.add_argument("--minutos", type=float, default=None,
                            help="Para quando o tempo acabar (rodízio).")
        parser.add_argument("--limite", type=int, default=None,
                            help="Máximo de jogadores nesta rodada.")
        parser.add_argument("--faltantes", action="store_true",
                            help="Só quem ainda não tem ficha.")
        parser.add_argument("--overall-min", type=int, default=None)
        parser.add_argument("--meus", action="store_true")

    def handle(self, *args, **opcoes):
        qs = Jogador.objects.all()
        if opcoes["faltantes"]:
            qs = qs.sem_ficha()
        if opcoes["overall_min"] is not None:
            qs = qs.filter(overall__gte=opcoes["overall_min"])
        if opcoes["meus"]:
            qs = qs.filter(meu_jogador=True)

        # Sem ficha primeiro; depois as verificadas há mais tempo.
        ids = list(
            qs.desatualizados_primeiro().values_list("pk", flat=True)[: opcoes["limite"]]
        )
        if not ids:
            self.stdout.write(self.style.WARNING("Nenhum jogador na fila."))
            return

        minutos = opcoes["minutos"]
        prazo = time.monotonic() + minutos * 60 if minutos else None
        self.stdout.write(
            f"{len(ids)} na fila"
            + (f"; orçamento de {minutos:.0f} min (~{minutos * 50:.0f} fichas)." if minutos
               else f" (~{len(ids) * 1.25 / 60:.0f} min).")
        )

        execucao = Execucao.objects.create(tipo="detalhe")
        comeco = time.monotonic()
        contagem = {persistencia.CRIADO: 0, persistencia.ALTERADO: 0, persistencia.IGUAL: 0}
        campos = erros = processados = 0
        interrompida = False

        try:
            # Resolvido pelo módulo, não pelo nome: mantém o comando testável.
            cliente = arena_client.cliente_compartilhado()
            for indice, jogador_id in enumerate(ids, start=1):
                if prazo and time.monotonic() >= prazo:
                    self.stdout.write("  orçamento de tempo esgotado; parando.")
                    break
                try:
                    dados = cliente.detalhe_jogador(jogador_id)
                    situacao, quantidade = persistencia.salvar_ficha(jogador_id, dados)
                    contagem[situacao] += 1
                    campos += quantidade
                except ArenaError as exc:
                    erros += 1
                    self.stderr.write(f"  [{jogador_id}] {exc}")
                    if erros >= 10 and erros > processados:
                        execucao.situacao = "erro"
                        execucao.mensagem = f"Erros demais em sequência: {exc}"
                        break
                processados += 1
                if indice % 50 == 0:
                    self.stdout.write(
                        f"  {indice}/{len(ids)} — "
                        f"+{contagem[persistencia.CRIADO]} novas, "
                        f"~{contagem[persistencia.ALTERADO]} alteradas, "
                        f"{erros} erros"
                    )
        except KeyboardInterrupt:
            interrompida = True
            self.stdout.write(self.style.WARNING("\nInterrompido pelo usuário."))

        if execucao.situacao == "rodando":
            execucao.situacao = "interrompida" if interrompida else "ok"
        execucao.criados = contagem[persistencia.CRIADO]
        execucao.atualizados = contagem[persistencia.ALTERADO]
        execucao.inalterados = contagem[persistencia.IGUAL]
        execucao.campos_alterados = campos
        execucao.erros = erros
        execucao.terminada_em = timezone.now()
        execucao.save()

        self.stdout.write(self.style.SUCCESS(
            f"Concluído em {time.monotonic() - comeco:.0f}s — "
            f"{contagem[persistencia.CRIADO]} novas · "
            f"{contagem[persistencia.ALTERADO]} alteradas ({campos} campos) · "
            f"{contagem[persistencia.IGUAL]} sem mudança · {erros} erros"
        ))
