"""Testes da API externa (painel de campeonatos): autorização e payload.

Reaproveita os fixtures de `jogadores.tests` (nenhum toca a rede) e grava os
jogadores direto pelo `persistencia`, como em `tests_acervo.py`.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from ..models import ChaveApiExterna
from ..services import persistencia
from ..tests import item_detalhe, item_lista


class AutorizacaoTest(TestCase):
    def setUp(self):
        persistencia.salvar_jogador(item_lista(1))
        self.chave = ChaveApiExterna.objects.create(nome="Painel de testes")

    def test_sem_chave_devolve_403(self):
        resposta = self.client.get(reverse("jogadores:jogadores_api:lista"))
        self.assertEqual(resposta.status_code, 403)

    def test_chave_errada_devolve_403(self):
        resposta = self.client.get(
            reverse("jogadores:jogadores_api:lista"), headers={"X-API-Key": "errada"}
        )
        self.assertEqual(resposta.status_code, 403)

    def test_chave_desativada_devolve_403(self):
        self.chave.ativa = False
        self.chave.save()
        resposta = self.client.get(
            reverse("jogadores:jogadores_api:lista"),
            headers={"X-API-Key": self.chave.token},
        )
        self.assertEqual(resposta.status_code, 403)

    def test_chave_correta_devolve_200(self):
        resposta = self.client.get(
            reverse("jogadores:jogadores_api:lista"),
            headers={"X-API-Key": self.chave.token},
        )
        self.assertEqual(resposta.status_code, 200)

    def test_token_e_gerado_sozinho(self):
        self.assertTrue(self.chave.token)


class ListaAPITest(TestCase):
    def setUp(self):
        for pk in range(1, 6):
            persistencia.salvar_jogador(item_lista(pk))
        chave = ChaveApiExterna.objects.create(nome="Painel de testes")
        self.cabecalhos = {"X-API-Key": chave.token}

    def test_lista_pagina_e_devolve_todos_jogadores_criados(self):
        resposta = self.client.get(
            reverse("jogadores:jogadores_api:lista"), headers=self.cabecalhos
        )
        corpo = resposta.json()
        self.assertEqual(corpo["count"], 5)
        self.assertEqual(len(corpo["results"]), 5)

    def test_filtro_de_posicao_reaproveita_filtros_local(self):
        resposta = self.client.get(
            reverse("jogadores:jogadores_api:lista"),
            {"posicao": "ATA"},
            headers=self.cabecalhos,
        )
        corpo = resposta.json()
        self.assertTrue(all(j["posicao"] == "ATA" for j in corpo["results"]))

    def test_jogador_sem_ficha_nao_traz_detalhe(self):
        resposta = self.client.get(
            reverse("jogadores:jogadores_api:lista"), headers=self.cabecalhos
        )
        corpo = resposta.json()
        primeiro = next(j for j in corpo["results"] if j["id"] == 1)
        self.assertFalse(primeiro["tem_ficha"])
        self.assertIsNone(primeiro["detalhe"])


class DetalheAPITest(TestCase):
    def setUp(self):
        persistencia.salvar_jogador(item_lista(1))
        persistencia.salvar_ficha(1, item_detalhe(1))
        chave = ChaveApiExterna.objects.create(nome="Painel de testes")
        self.cabecalhos = {"X-API-Key": chave.token}

    def test_404_para_jogador_inexistente(self):
        resposta = self.client.get(
            reverse("jogadores:jogadores_api:detalhe", args=[999]),
            headers=self.cabecalhos,
        )
        self.assertEqual(resposta.status_code, 404)

    def test_devolve_todos_os_dados_do_jogador(self):
        resposta = self.client.get(
            reverse("jogadores:jogadores_api:detalhe", args=[1]),
            headers=self.cabecalhos,
        )
        corpo = resposta.json()

        self.assertEqual(corpo["id"], 1)
        self.assertTrue(corpo["tem_ficha"])
        # Campos crus e derivados do resumo (Jogador).
        self.assertIn("payload_lista", corpo)
        self.assertEqual(corpo["posicao_nome"], "Atacante")

        # Ficha técnica completa (JogadorDetalhe), aninhada.
        ficha = corpo["detalhe"]
        self.assertEqual(ficha["nome_completo"], "Kylian Mbappé Lottin")
        self.assertEqual(ficha["time"], "Real Madrid")
        self.assertIn("payload_detalhe", ficha)
        self.assertIn("Chute colocado", ficha["caracteristicas_rotuladas"])
        self.assertIn("Velocista", ficha["especialidades_rotuladas"])
        self.assertEqual(len(ficha["radar"]), 6)
