"""Preenche `busca_norm` para os jogadores já gravados antes do campo existir.

Roda em lote, sem depender de código do app (data migration reexecutável).
"""

from __future__ import annotations

import unicodedata

from django.db import migrations


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in base if not unicodedata.combining(c)).casefold()


def povoar(apps, schema_editor):
    Jogador = apps.get_model("jogadores", "Jogador")
    lote = []
    for j in Jogador.objects.all().only("pk", "nome", "nacionalidade", "posicao"):
        j.busca_norm = _norm(f"{j.nome} {j.nacionalidade} {j.posicao}")[:400]
        lote.append(j)
        if len(lote) >= 500:
            Jogador.objects.bulk_update(lote, ["busca_norm"])
            lote.clear()
    if lote:
        Jogador.objects.bulk_update(lote, ["busca_norm"])


def reverter(apps, schema_editor):
    pass  # nada a desfazer — o campo é derivado.


class Migration(migrations.Migration):
    dependencies = [("jogadores", "0002_jogador_busca_norm")]
    operations = [migrations.RunPython(povoar, reverter)]
