"""Testes do acervo: gravação, detecção de mudanças, comandos e agendador.

Reaproveita os dados falsos de `tests.py` — nenhum teste toca a rede.
"""

from __future__ import annotations

import io
from datetime import datetime, time as hora_do_dia
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Alteracao, Execucao, Jogador, JogadorDetalhe
from .services import agendamento, persistencia
from .services.arena_client import ArenaError
from .tests import TOTAL, ClienteFalso, item_detalhe, item_lista


class ConsoleCp1252(io.StringIO):
    """Imita o console do Windows: rejeita o que não couber em cp1252."""

    def write(self, texto):
        texto.encode("cp1252")
        return super().write(texto)


class PersistenciaTest(TestCase):
    def test_criar_jogador(self):
        situacao, campos = persistencia.salvar_jogador(item_lista(1))
        self.assertEqual(situacao, persistencia.CRIADO)
        self.assertGreater(campos, 0)

        jogador = Jogador.objects.get(pk=1)
        self.assertEqual(jogador.nome, "J. Silva")
        self.assertEqual(jogador.idade, 21)
        self.assertEqual(jogador.bola_nome, "Carta Azul")
        self.assertFalse(hasattr(jogador, "passe"))
        self.assertFalse(hasattr(jogador, "nome_escudo"))
        # O payload cru fica guardado inteiro.
        self.assertEqual(jogador.payload_lista["id"], 1)

    def test_regravar_sem_mudanca_nao_gera_alteracao(self):
        persistencia.salvar_jogador(item_lista(1))
        situacao, campos = persistencia.salvar_jogador(item_lista(1))

        self.assertEqual(situacao, persistencia.IGUAL)
        self.assertEqual(campos, 0)
        self.assertEqual(Alteracao.objects.count(), 0)

    def test_mudanca_e_detectada_e_registrada(self):
        persistencia.salvar_jogador(item_lista(1))
        antes = Jogador.objects.get(pk=1).alterado_em

        modificado = item_lista(1)
        modificado["overall"] = 99
        modificado["a_venda"] = True
        situacao, campos = persistencia.salvar_jogador(modificado)

        self.assertEqual(situacao, persistencia.ALTERADO)
        self.assertEqual(campos, 2)

        jogador = Jogador.objects.get(pk=1)
        self.assertEqual(jogador.overall, 99)
        # >= e não >: no Windows duas chamadas podem cair no mesmo tick do relógio.
        self.assertGreaterEqual(jogador.alterado_em, antes)

        mudancas = {a.campo: (a.de, a.para) for a in Alteracao.objects.all()}
        self.assertEqual(set(mudancas), {"overall", "a_venda"})
        self.assertEqual(mudancas["overall"][1], "99")
        self.assertEqual(mudancas["a_venda"], ("False", "True"))

    def test_verificado_em_avanca_mesmo_sem_mudanca(self):
        persistencia.salvar_jogador(item_lista(1))
        primeiro = Jogador.objects.get(pk=1).verificado_em
        persistencia.salvar_jogador(item_lista(1))
        self.assertGreaterEqual(Jogador.objects.get(pk=1).verificado_em, primeiro)

    def test_salvar_ficha_completa(self):
        persistencia.salvar_jogador(item_lista(1))
        situacao, _ = persistencia.salvar_ficha(1, item_detalhe(1))
        self.assertEqual(situacao, persistencia.CRIADO)

        ficha = JogadorDetalhe.objects.get(pk=1)
        self.assertEqual(ficha.time, "Real Madrid")
        self.assertEqual(ficha.caracteristicas, ["C01", "C06", "C99"])
        self.assertEqual(ficha.posicoes_jogaveis, ["ATA", "PE"])
        self.assertEqual(ficha.payload_detalhe["nome_completo"], "Kylian Mbappé Lottin")
        # O detalhe corrige o overall que veio da lista.
        self.assertEqual(Jogador.objects.get(pk=1).overall, 91)

    def test_regravar_ficha_identica_nao_altera(self):
        persistencia.salvar_jogador(item_lista(1))
        persistencia.salvar_ficha(1, item_detalhe(1))
        situacao, campos = persistencia.salvar_ficha(1, item_detalhe(1))
        self.assertEqual((situacao, campos), (persistencia.IGUAL, 0))

    def test_mudanca_de_atributo_na_ficha(self):
        persistencia.salvar_jogador(item_lista(1))
        persistencia.salvar_ficha(1, item_detalhe(1))

        alterado = item_detalhe(1)
        alterado["finalizacao"] = 99
        situacao, campos = persistencia.salvar_ficha(1, alterado)

        self.assertEqual(situacao, persistencia.ALTERADO)
        self.assertEqual(campos, 1)
        registro = Alteracao.objects.get(campo="finalizacao")
        self.assertEqual(registro.origem, "detalhe")
        self.assertEqual(registro.para, "99")

    def test_marcar_ausentes_nao_apaga(self):
        for pk in (1, 2, 3):
            persistencia.salvar_jogador(item_lista(pk))
        marcados = persistencia.marcar_ausentes({1, 2})

        self.assertEqual(marcados, 1)
        self.assertEqual(Jogador.objects.count(), 3)
        self.assertIsNotNone(Jogador.objects.get(pk=3).ausente_desde)
        self.assertIsNone(Jogador.objects.get(pk=1).ausente_desde)

    def test_reaparecer_limpa_a_ausencia(self):
        persistencia.salvar_jogador(item_lista(1))
        persistencia.marcar_ausentes(set())
        self.assertIsNotNone(Jogador.objects.get(pk=1).ausente_desde)

        persistencia.salvar_jogador(item_lista(1))
        self.assertIsNone(Jogador.objects.get(pk=1).ausente_desde)


class ComandoBase(TestCase):
    """Substitui o cliente da API pelo duplo, para os comandos."""

    def setUp(self):
        cache.clear()
        self.cliente = ClienteFalso()
        patcher = patch(
            "jogadores.services.arena_client.cliente_compartilhado",
            lambda: self.cliente,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(cache.clear)


class SincronizarListaTest(ComandoBase):
    def test_popula_o_acervo(self):
        call_command("sincronizar_jogadores", verbosity=0)
        self.assertEqual(Jogador.objects.count(), TOTAL)

        execucao = Execucao.objects.get(tipo="lista")
        self.assertEqual(execucao.situacao, "ok")
        self.assertEqual(execucao.criados, TOTAL)
        self.assertEqual(execucao.paginas, 5)
        self.assertIsNotNone(execucao.terminada_em)

    def test_segunda_rodada_nao_recria_nada(self):
        call_command("sincronizar_jogadores", verbosity=0)
        call_command("sincronizar_jogadores", verbosity=0)

        execucao = Execucao.objects.filter(tipo="lista").first()
        self.assertEqual(execucao.criados, 0)
        self.assertEqual(execucao.inalterados, TOTAL)
        self.assertEqual(Jogador.objects.count(), TOTAL)
        self.assertEqual(Alteracao.objects.count(), 0)

    def test_limite_de_paginas(self):
        call_command("sincronizar_jogadores", paginas=2, verbosity=0)
        self.assertEqual(Jogador.objects.count(), 20)

    def test_erro_da_api_registra_execucao_com_falha(self):
        self.cliente.falha = ArenaError("API fora do ar")
        with self.assertRaises(CommandError):
            call_command("sincronizar_jogadores", verbosity=0)
        self.assertEqual(Execucao.objects.get(tipo="lista").situacao, "erro")


class SincronizarFichasTest(ComandoBase):
    def test_respeita_o_limite(self):
        call_command("sincronizar_jogadores", paginas=1, verbosity=0)
        call_command("sincronizar_detalhes", limite=3, verbosity=0)

        self.assertEqual(JogadorDetalhe.objects.count(), 3)
        self.assertEqual(Execucao.objects.get(tipo="detalhe").criados, 3)

    def test_rodizio_pega_quem_esta_ha_mais_tempo_sem_verificar(self):
        call_command("sincronizar_jogadores", paginas=1, verbosity=0)
        call_command("sincronizar_detalhes", limite=4, verbosity=0)
        primeira = set(JogadorDetalhe.objects.values_list("jogador_id", flat=True))

        call_command("sincronizar_detalhes", limite=4, verbosity=0)
        segunda = set(JogadorDetalhe.objects.values_list("jogador_id", flat=True))

        # Quem ainda não tinha ficha entra antes de reverificar as já feitas.
        self.assertEqual(len(segunda), 8)
        self.assertTrue(primeira < segunda)

    def test_apenas_faltantes(self):
        call_command("sincronizar_jogadores", paginas=1, verbosity=0)
        call_command("sincronizar_detalhes", limite=10, verbosity=0)
        chamadas = len(self.cliente.chamadas)

        call_command("sincronizar_detalhes", faltantes=True, verbosity=0)
        self.assertEqual(len(self.cliente.chamadas), chamadas)  # nada a fazer


class AgendamentoTest(SimpleTestCase):
    def test_ler_horario(self):
        self.assertEqual(agendamento.ler_horario("03:30"), hora_do_dia(3, 30))
        self.assertEqual(agendamento.ler_horario("4"), hora_do_dia(4, 0))
        with self.assertRaises(ValueError):
            agendamento.ler_horario("meia-noite")

    def test_horario_ainda_por_vir_hoje(self):
        alvo = agendamento.proxima_execucao(datetime(2026, 7, 31, 1, 0), hora_do_dia(3, 30))
        self.assertEqual(alvo, datetime(2026, 7, 31, 3, 30))

    def test_horario_ja_passou_vai_para_amanha(self):
        alvo = agendamento.proxima_execucao(datetime(2026, 7, 31, 9, 0), hora_do_dia(3, 30))
        self.assertEqual(alvo, datetime(2026, 8, 1, 3, 30))

    def test_horario_exato_nao_dispara_duas_vezes(self):
        alvo = agendamento.proxima_execucao(datetime(2026, 7, 31, 3, 30), hora_do_dia(3, 30))
        self.assertEqual(alvo, datetime(2026, 8, 1, 3, 30))

    def test_virada_de_mes(self):
        alvo = agendamento.proxima_execucao(datetime(2026, 7, 31, 23, 50), hora_do_dia(3, 30))
        self.assertEqual(alvo, datetime(2026, 8, 1, 3, 30))


class AgendadorTest(ComandoBase):
    def test_rodada_unica_sincroniza_lista_e_fichas(self):
        call_command("agendar_sincronizacao", agora=True, uma_vez=True,
                     minutos_detalhes=0.05, verbosity=0)

        self.assertEqual(Jogador.objects.count(), TOTAL)
        self.assertTrue(Execucao.objects.filter(tipo="lista", situacao="ok").exists())
        self.assertTrue(Execucao.objects.filter(tipo="detalhe").exists())

    def test_falha_da_api_nao_derruba_o_agendador(self):
        self.cliente.falha = ArenaError("API fora do ar")
        # Não pode levantar: amanhã ele precisa tentar de novo.
        call_command("agendar_sincronizacao", agora=True, uma_vez=True,
                     minutos_detalhes=0, verbosity=0)
        self.assertTrue(Execucao.objects.filter(tipo="lista", situacao="erro").exists())

    def test_horario_invalido_falha_cedo(self):
        with self.assertRaises(CommandError):
            call_command("agendar_sincronizacao", horario="qualquer", verbosity=0)

    def test_rodada_sobrevive_a_console_sem_utf8(self):
        """Regressão: um caractere fora do cp1252 chegou a abortar a rodada.

        No console do Windows, `stdout.write("→")` levanta UnicodeEncodeError.
        Como as etapas rodam dentro de um `except Exception`, o erro cosmético
        era confundido com falha da API e a sincronização era pulada em silêncio.
        """
        saida = ConsoleCp1252()
        call_command("agendar_sincronizacao", agora=True, uma_vez=True,
                     minutos_detalhes=0, stdout=saida)

        self.assertEqual(Jogador.objects.count(), TOTAL)
        self.assertTrue(Execucao.objects.filter(tipo="lista", situacao="ok").exists())


# ---------------------------------------------------------------------------
# Painel local (/players/local) — lê do acervo
# ---------------------------------------------------------------------------
class PainelLocalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 25 jogadores no acervo; ficha só para o primeiro.
        for pk in range(1, 26):
            persistencia.salvar_jogador(item_lista(pk))
        persistencia.salvar_ficha(1, item_detalhe(1))

    def test_lista_renderiza_do_banco(self):
        r = self.client.get(reverse("jogadores:players_local"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Acervo local")
        # 16 por página.
        self.assertEqual(len(r.context["pagina"].object_list), 16)
        self.assertEqual(r.context["resumo"]["total"], 25)

    def test_segunda_pagina(self):
        r = self.client.get(reverse("jogadores:players_local"), {"page": 2})
        self.assertEqual(len(r.context["pagina"].object_list), 9)

    def test_busca_por_nome(self):
        r = self.client.get(reverse("jogadores:players_local"), {"q": "Messi"})
        nomes = {j.nome for j in r.context["pagina"].object_list}
        self.assertTrue(nomes)
        self.assertTrue(all("Messi" in n for n in nomes))

    def test_busca_ignora_acento(self):
        # "Mbappe" (sem acento) deve casar com "K. Mbappé".
        r = self.client.get(reverse("jogadores:players_local"), {"q": "mbappe"})
        self.assertTrue(r.context["pagina"].object_list)

    def test_filtro_overall_e_posicao(self):
        r = self.client.get(reverse("jogadores:players_local"),
                            {"overall_min": 80, "posicao": "ATA"})
        for j in r.context["pagina"].object_list:
            self.assertGreaterEqual(j.overall, 80)
            self.assertEqual(j.posicao, "ATA")

    def test_situacao_com_ficha(self):
        r = self.client.get(reverse("jogadores:players_local"), {"situacao": "com_ficha"})
        self.assertEqual(r.context["pagina"].paginator.count, 1)

    def test_ordenacao_invalida_cai_no_padrao(self):
        r = self.client.get(reverse("jogadores:players_local"), {"ordenar": "; drop"})
        self.assertEqual(r.context["filtros"]["ordenar"], "overall")

    def test_detalhe_do_acervo(self):
        r = self.client.get(reverse("jogadores:players_local_detalhe", args=[1]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Kylian Mbappé Lottin")
        self.assertContains(r, "Chute colocado")     # caracteristica rotulada
        self.assertContains(r, "Velocista")          # especialidade rotulada
        self.assertContains(r, "Centroavante")       # funcao
        self.assertContains(r, "polygon")            # radar SVG

    def test_detalhe_sem_ficha_nao_quebra(self):
        r = self.client.get(reverse("jogadores:players_local_detalhe", args=[2]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ainda não sincronizada")

    def test_detalhe_inexistente_404(self):
        r = self.client.get(reverse("jogadores:players_local_detalhe", args=[999999]))
        self.assertEqual(r.status_code, 404)

    def test_card_aponta_para_o_detalhe_local(self):
        r = self.client.get(reverse("jogadores:players_local"))
        self.assertContains(r, 'href="/players/local/')

    def test_nao_expoe_clube_nem_valor(self):
        proibidos = ["Clube 0", "Clube 1", "Clube na liga", "Valor de mercado", "475.200"]
        for url in [reverse("jogadores:players_local"),
                    reverse("jogadores:players_local_detalhe", args=[1])]:
            r = self.client.get(url)
            for texto in proibidos:
                self.assertNotContains(r, texto)

    def test_radar_do_banco_igual_ao_do_parser(self):
        from jogadores.services import parser
        ficha_banco = JogadorDetalhe.objects.get(pk=1)
        ficha_live = parser.ficha(item_detalhe(1))
        self.assertEqual(
            [(e["sigla"], e["valor"]) for e in ficha_banco.radar],
            [(e["sigla"], e["valor"]) for e in ficha_live.radar],
        )

    def test_acervo_vazio_mostra_instrucao(self):
        Jogador.objects.all().delete()
        r = self.client.get(reverse("jogadores:players_local"))
        self.assertContains(r, "Acervo vazio")
        self.assertContains(r, "sincronizar_jogadores")
