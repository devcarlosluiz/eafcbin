"""Testes — nenhum toca a rede: o cliente da API é substituído por um duplo."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .services import busca, parser
from .services.arena_client import ArenaAuthError, ArenaError
from .templatetags import painel

TOTAL = 45  # 5 páginas de 10 (a última com 5)


def item_lista(pk: int) -> dict:
    """Um jogador no formato da lista da API."""
    nomes = ["K. Mbappé", "J. Silva", "L. Messi", "R. Lewandowski", "V. Júnior"]
    nome = nomes[pk % len(nomes)]
    return {
        "id": pk,
        "nome": f"({20 + pk % 15}) {nome}",
        "passe": "475.200,00",
        "posicao": ["ATA", "ZAG", "MEI", "GOL", "VOL"][pk % 5],
        "overall": 60 + pk % 32,
        "nacionalidade": ["França", "Brasil", "Argentina"][pk % 3],
        "nacionalidade_flag": "https://exemplo/f.png",
        "nome_escudo": f"Clube {pk % 4}(Dono)",
        "link_escudo": "https://exemplo/e.png",
        "foto": "https://exemplo/foto.png",
        "usuario_id": None if pk % 5 == 0 else 100 + pk,
        "meu_jogador": False,
        "multa": 950_000,
        "bola": {"bola_id": 1, "bola_nome": "Carta Azul", "bola_link": "https://exemplo/b.png"},
        "inLeilao": pk % 7 == 0,
        "a_venda": pk % 3 == 0,
        "valor_a_venda": "600.000,00" if pk % 3 == 0 else None,
        "favorito": False,
    }


def item_detalhe(pk: int = 1) -> dict:
    dados = {
        "id": pk, "nome": "K. Mbappé", "nome_completo": "Kylian Mbappé Lottin",
        "time": "Real Madrid", "overall": 91, "potencial": 92, "idade": 26,
        "altura": 182, "peso": 81, "pe": "D", "posicao": "ATA", "posicao_id": 14,
        "skillmoves": 5, "pe_ruim": 4, "rep_internacional": 5,
        "porte_fisico": "Unique", "tipo_aceleracao": "Geralmente explosiva",
        "face_real": 1, "nacionalidade": "França", "slug": "k-mbappe",
        "foto": "https://exemplo/foto.png", "passe": "475.200,00",
        "pos_ATA": 1, "pos_PE": 1, "pos_ME": 0,
        "C01": 1, "C06": 1, "C17": 0, "C99": 1,
        "E02": 1, "E14": 1,
        "funcoes": [{"posicao": "ATA", "titulo": "Centroavante", "familiaridade": "++"}],
    }
    for indice, campo in enumerate(parser.ATRIBUTOS):
        dados[campo] = 50 + indice % 40
    return dados


class ClienteFalso:
    """Imita `ArenaClient` sem rede.

    `param_busca` define se a API "aceita" filtro no servidor — é exatamente a
    incerteza que o código precisa tolerar nos dois sentidos.
    """

    def __init__(self, param_busca: str | None = None, falha: Exception | None = None):
        self.param_busca = param_busca
        self.falha = falha
        self.chamadas: list[tuple] = []

    def listar_jogadores(self, page=1, extra=None):
        if self.falha:
            raise self.falha
        self.chamadas.append(("lista", page, tuple(sorted((extra or {}).items()))))

        ids = list(range(1, TOTAL + 1))
        if extra:
            if self.param_busca and self.param_busca in extra:
                termo = str(extra[self.param_busca]).casefold()
                ids = [i for i in ids if termo in item_lista(i)["nome"].casefold()]
            elif self.param_busca:
                # Parâmetro desconhecido: o servidor ignora e devolve tudo.
                pass
            else:
                pass

        inicio = (page - 1) * 10
        recorte = ids[inicio:inicio + 10]
        ultima = max(1, -(-len(ids) // 10))
        return {
            "current_page": page,
            "data": [item_lista(i) for i in recorte],
            "last_page": ultima,
            "per_page": 10,
            "total": len(ids),
            "next_page_url": None if page >= ultima else "...",
        }

    def detalhe_jogador(self, jogador_id):
        if self.falha:
            raise self.falha
        self.chamadas.append(("detalhe", jogador_id))
        if jogador_id > TOTAL:
            raise ArenaError(f"Não encontrado na API: /jogadores/{jogador_id}")
        return item_detalhe(jogador_id)


class BaseSemRede(SimpleTestCase):
    """Base comum: limpa o cache e injeta o cliente falso."""

    cliente: ClienteFalso

    def setUp(self):
        cache.clear()
        self.cliente = ClienteFalso()
        self._patch = patch(
            "jogadores.views.cliente_compartilhado", lambda: self.cliente
        )
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(cache.clear)


# ---------------------------------------------------------------------------
# Conversores
# ---------------------------------------------------------------------------
class ConversoresTest(SimpleTestCase):
    def test_valor_br(self):
        self.assertEqual(parser.valor_br("475.200,00"), Decimal("475200.00"))
        self.assertEqual(parser.valor_br("1.250"), Decimal("1250"))
        self.assertEqual(parser.valor_br("42330.19"), Decimal("42330.19"))
        self.assertEqual(parser.valor_br(None), Decimal("0"))
        self.assertEqual(parser.valor_br("lixo"), Decimal("0"))

    def test_separar_nome(self):
        self.assertEqual(parser.separar_nome("(26) K. Mbappé"), ("K. Mbappé", 26))
        self.assertEqual(parser.separar_nome("Sem idade"), ("Sem idade", None))

    def test_jogador_da_lista(self):
        j = parser.jogador(item_lista(3))
        self.assertEqual(j.idade, 23)
        self.assertEqual(j.passe, Decimal("475200.00"))
        self.assertEqual(j.bola_nome, "Carta Azul")
        self.assertTrue(j.a_venda)
        self.assertEqual(j.url, "/jogador/3/")

    def test_ficha_do_detalhe(self):
        f = parser.ficha(item_detalhe())
        self.assertEqual(f.time, "Real Madrid")
        # C99 está fora do intervalo documentado, mas não pode ser perdido.
        self.assertEqual(f.caracteristicas, ["C01", "C06", "C99"])
        self.assertEqual(f.especialidades, ["E02", "E14"])
        self.assertEqual(f.posicoes_jogaveis, ["ATA", "PE"])
        self.assertEqual(f.caracteristicas_rotuladas[0], "Chute colocado")
        self.assertEqual(f.caracteristicas_rotuladas[2], "C99")  # sem rótulo
        self.assertEqual(len(f.radar), 6)

    def test_filtros_de_template(self):
        self.assertEqual(painel.compacto(1_250_000), "1,25 mi")
        self.assertEqual(painel.moeda_br(Decimal("475200")), "475.200")
        self.assertEqual(painel.pe_extenso("E"), "Canhoto")
        self.assertEqual(painel.estrelas(3), "★★★☆☆")


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------
class BuscaTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_normalizacao_ignora_acento(self):
        cliente = ClienteFalso(param_busca=None)
        resultado = busca.consultar(cliente, "mbappe")
        self.assertTrue(resultado.jogadores)
        self.assertEqual(resultado.modo, "varredura")

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "auto"})
    def test_detecta_filtro_no_servidor(self):
        cliente = ClienteFalso(param_busca="search")
        self.assertEqual(busca.detectar_filtro_servidor(cliente), "search")
        # A detecção é memorizada: a segunda chamada não repete as sondagens.
        antes = len(cliente.chamadas)
        self.assertEqual(busca.detectar_filtro_servidor(cliente), "search")
        self.assertEqual(len(cliente.chamadas), antes)

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "auto"})
    def test_sem_filtro_no_servidor_cai_para_varredura(self):
        cliente = ClienteFalso(param_busca=None)
        self.assertIsNone(busca.detectar_filtro_servidor(cliente))

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "off"})
    def test_param_busca_off_nao_sonda(self):
        cliente = ClienteFalso(param_busca="search")
        self.assertIsNone(busca.detectar_filtro_servidor(cliente))
        self.assertEqual(cliente.chamadas, [])

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "search"})
    def test_busca_no_servidor(self):
        cliente = ClienteFalso(param_busca="search")
        resultado = busca.consultar(cliente, "Messi")
        self.assertEqual(resultado.modo, "servidor")
        self.assertTrue(all("Messi" in j.nome for j in resultado.jogadores))

    @override_settings(ARENA={
        **busca.settings.ARENA, "PARAM_BUSCA": "off", "PAGINAS_POR_VARREDURA": 2,
    })
    def test_varredura_em_lotes_e_continuacao(self):
        cliente = ClienteFalso(param_busca=None)
        primeiro = busca.consultar(cliente, "Messi", de=1)
        self.assertEqual(primeiro.modo, "varredura")
        self.assertEqual(primeiro.paginas_lidas, 2)
        self.assertEqual(primeiro.proxima_pagina, 3)
        self.assertTrue(primeiro.tem_mais_para_varrer)

        ultimo = busca.consultar(cliente, "Messi", de=5)
        self.assertIsNone(ultimo.proxima_pagina)
        self.assertFalse(ultimo.tem_mais_para_varrer)

    def test_cache_evita_requisicao_repetida(self):
        cliente = ClienteFalso()
        busca.obter_pagina(cliente, 1)
        busca.obter_pagina(cliente, 1)
        self.assertEqual(len(cliente.chamadas), 1)

    def test_listagem_sem_termo(self):
        resultado = busca.consultar(ClienteFalso(), "")
        self.assertEqual(resultado.modo, "listagem")
        self.assertEqual(len(resultado.jogadores), 16)
        self.assertEqual(resultado.pagina.total, TOTAL)


@override_settings(ARENA={**busca.settings.ARENA, "POR_PAGINA": 16})
class PaginaDe16Test(SimpleTestCase):
    """A API entrega 10 por página; a tela precisa entregar 16."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.cliente = ClienteFalso()

    def ids(self, tela):
        return [j.id for j in busca.montar_pagina(self.cliente, tela).jogadores]

    def test_primeira_pagina(self):
        self.assertEqual(self.ids(1), list(range(1, 17)))

    def test_segunda_pagina_respeita_o_deslocamento(self):
        # Itens 17..32 moram nas páginas 2, 3 e 4 da API.
        self.assertEqual(self.ids(2), list(range(17, 33)))

    def test_terceira_pagina(self):
        self.assertEqual(self.ids(3), list(range(33, TOTAL + 1)))  # última, curta

    def test_sem_sobreposicao_nem_buraco(self):
        vistos = self.ids(1) + self.ids(2) + self.ids(3)
        self.assertEqual(vistos, list(range(1, TOTAL + 1)))

    def test_total_de_paginas(self):
        pagina = busca.montar_pagina(self.cliente, 1)
        self.assertEqual(pagina.total, TOTAL)
        self.assertEqual(pagina.ultima, 3)  # ceil(45 / 16)
        self.assertEqual(pagina.por_pagina, 16)

    def test_reaproveita_paginas_da_api_ao_navegar(self):
        self.ids(1)
        chamadas_primeira = len(self.cliente.chamadas)
        self.ids(2)
        # A página 2 da API é borda das duas telas — vem do cache.
        novas = len(self.cliente.chamadas) - chamadas_primeira
        self.assertEqual(novas, 2)

    @override_settings(ARENA={**busca.settings.ARENA, "POR_PAGINA": 10})
    def test_tamanho_10_nao_fatia(self):
        pagina = busca.montar_pagina(self.cliente, 2)
        self.assertEqual([j.id for j in pagina.jogadores], list(range(11, 21)))
        self.assertEqual(len(self.cliente.chamadas), 1)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
class ConsultaViewTest(BaseSemRede):
    def test_home_lista_ao_vivo(self):
        resposta = self.client.get(reverse("jogadores:consulta"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Consultar")
        self.assertContains(resposta, "K. Mbappé")

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "off"})
    def test_busca_por_texto_renderiza_resultados(self):
        resposta = self.client.get(reverse("jogadores:consulta"), {"q": "Messi"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "L. Messi")
        self.assertContains(resposta, "varredura")

    def test_busca_por_id_abre_a_ficha(self):
        resposta = self.client.get(reverse("jogadores:consulta"), {"q": "7"})
        self.assertRedirects(resposta, "/jogador/7/", fetch_redirect_response=False)

    def test_paginacao(self):
        resposta = self.client.get(reverse("jogadores:consulta"), {"page": "2"})
        self.assertEqual(resposta.context["resultado"].pagina.numero, 2)

    def test_pagina_invalida_cai_na_primeira(self):
        resposta = self.client.get(reverse("jogadores:consulta"), {"page": "abc"})
        self.assertEqual(resposta.context["resultado"].pagina.numero, 1)

    def test_erro_da_api_vira_aviso_na_tela(self):
        self.cliente.falha = ArenaError("API fora do ar")
        resposta = self.client.get(reverse("jogadores:consulta"))
        self.assertEqual(resposta.status_code, 502)
        self.assertContains(resposta, "API fora do ar", status_code=502)

    def test_sem_credenciais_mostra_instrucao(self):
        self.cliente.falha = ArenaAuthError(
            "Credenciais não configuradas. Defina ARENA_LOGIN e ARENA_SENHA no arquivo .env."
        )
        resposta = self.client.get(reverse("jogadores:consulta"))
        self.assertEqual(resposta.status_code, 401)
        self.assertContains(resposta, "ARENA_LOGIN", status_code=401)


class DetalheViewTest(BaseSemRede):
    def test_ficha_completa(self):
        resposta = self.client.get(reverse("jogadores:detalhe", args=[1]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Kylian Mbappé Lottin")
        self.assertContains(resposta, "Real Madrid")
        self.assertContains(resposta, "Chute colocado")
        self.assertContains(resposta, "Velocista")
        self.assertContains(resposta, "Centroavante")
        self.assertContains(resposta, "polygon")  # radar em SVG

    def test_jogador_inexistente_mostra_erro(self):
        resposta = self.client.get(reverse("jogadores:detalhe", args=[999999]))
        self.assertEqual(resposta.status_code, 502)
        self.assertContains(resposta, "Não encontrado na API", status_code=502)


class CamposOcultosTest(BaseSemRede):
    """Clube na liga e valor de mercado não podem vazar para a tela."""

    PROIBIDOS = ["Clube 0", "Clube 1", "Clube na liga", "Valor de mercado",
                 "475.200", "475,2"]

    def _conferir(self, resposta):
        for texto in self.PROIBIDOS:
            self.assertNotContains(resposta, texto)

    def test_listagem_nao_mostra_clube_nem_valor(self):
        self._conferir(self.client.get(reverse("jogadores:consulta")))

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "off"})
    def test_busca_nao_mostra_clube_nem_valor(self):
        self._conferir(self.client.get(reverse("jogadores:consulta"), {"q": "Messi"}))

    def test_ficha_nao_mostra_clube_nem_valor(self):
        resposta = self.client.get(reverse("jogadores:detalhe", args=[1]))
        self._conferir(resposta)
        # O clube da vida real (`time`) é outro campo e continua visível.
        self.assertContains(resposta, "Real Madrid")

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "off"})
    def test_busca_local_nao_casa_por_clube(self):
        cliente = ClienteFalso(param_busca=None)
        self.assertEqual(busca.consultar(cliente, "Clube").jogadores, [])

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "search"})
    def test_sugestoes_nao_expoem_clube(self):
        self.cliente.param_busca = "search"
        dados = self.client.get(reverse("jogadores:sugestoes"), {"q": "Messi"}).json()
        self.assertTrue(dados["resultados"])
        for item in dados["resultados"]:
            self.assertNotIn("nome_escudo", item)


class SugestoesViewTest(BaseSemRede):
    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "search"})
    def test_sugestoes_com_filtro_no_servidor(self):
        self.cliente.param_busca = "search"
        dados = self.client.get(reverse("jogadores:sugestoes"), {"q": "Messi"}).json()
        self.assertTrue(dados["disponivel"])
        self.assertTrue(dados["resultados"])

    @override_settings(ARENA={**busca.settings.ARENA, "PARAM_BUSCA": "off"})
    def test_sugestoes_desligam_sem_filtro_no_servidor(self):
        dados = self.client.get(reverse("jogadores:sugestoes"), {"q": "Messi"}).json()
        self.assertFalse(dados["disponivel"])
        self.assertEqual(dados["resultados"], [])

    def test_termo_curto_nao_consulta(self):
        dados = self.client.get(reverse("jogadores:sugestoes"), {"q": "M"}).json()
        self.assertEqual(dados["resultados"], [])
        self.assertEqual(self.cliente.chamadas, [])
