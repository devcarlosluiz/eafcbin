"""Confere os rótulos de `jogadores/data/fifa_labels.py` contra o acervo.

Só quatro correspondências são confirmadas pela documentação da API (`C01`,
`C06`, `E02`, `E14`); o resto é aproximação. Este comando mostra quais flags
aparecem, com que frequência e em quem — o suficiente para deduzir o rótulo
certo e corrigir o arquivo.

    python manage.py sincronizar_detalhes --limite 300
    python manage.py descobrir_flags --amostra 5
"""

from __future__ import annotations

from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from ...data import fifa_labels
from ...models import JogadorDetalhe


class Command(BaseCommand):
    help = "Lista as flags C*/E* presentes no acervo e seus rótulos atuais."

    def add_arguments(self, parser):
        parser.add_argument("--amostra", type=int, default=3,
                            help="Jogadores de exemplo por flag.")
        parser.add_argument("--sem-rotulo", action="store_true",
                            help="Só as flags que ainda não têm nome.")

    def handle(self, *args, **opcoes):
        amostra = max(0, opcoes["amostra"])
        contagem: Counter[str] = Counter()
        exemplos: dict[str, list[str]] = defaultdict(list)
        total = 0

        fichas = JogadorDetalhe.objects.select_related("jogador").only(
            "caracteristicas", "especialidades", "jogador__nome", "jogador__overall"
        )
        for ficha in fichas.iterator(chunk_size=500):
            total += 1
            etiqueta = f"{ficha.jogador.nome} ({ficha.jogador.overall})"
            for codigo in list(ficha.caracteristicas) + list(ficha.especialidades):
                contagem[codigo] += 1
                if len(exemplos[codigo]) < amostra:
                    exemplos[codigo].append(etiqueta)

        if not total:
            self.stdout.write(self.style.WARNING(
                "Acervo sem fichas. Rode `sincronizar_detalhes` antes."
            ))
            return

        self.stdout.write(f"{total} fichas, {len(contagem)} flags distintas.\n")
        sem_rotulo = []
        for codigo in sorted(contagem):
            mapa = (fifa_labels.CARACTERISTICAS if codigo.startswith("C")
                    else fifa_labels.ESPECIALIDADES)
            rotulo = mapa.get(codigo)
            if not rotulo:
                sem_rotulo.append(codigo)
            elif opcoes["sem_rotulo"]:
                continue

            pct = 100 * contagem[codigo] / total
            linha = (f"{'?' if not rotulo else ' '} {codigo}  {contagem[codigo]:>6} "
                     f"({pct:5.1f}%)  {rotulo or 'SEM ROTULO'}")
            if exemplos[codigo]:
                linha += f"   <- {', '.join(exemplos[codigo])}"
            self.stdout.write(linha)

        if sem_rotulo:
            self.stdout.write(self.style.WARNING(
                f"\n{len(sem_rotulo)} sem rotulo: {', '.join(sem_rotulo)}"
            ))
        self.stdout.write(
            "\nConfirmados pela documentacao: C01, C06, E02, E14. "
            "Os demais rotulos sao aproximacao — ajuste fifa_labels.py."
        )
