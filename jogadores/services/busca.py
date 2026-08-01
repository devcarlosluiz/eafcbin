"""Consulta ao vivo: fala com a API a cada requisição e devolve o resultado.

Nada é gravado em banco. O único armazenamento é o cache em memória do
processo (`CACHES`), com TTL curto, para que paginar de volta ou repetir uma
busca não gaste requisições do limite de ~60/min.

Sobre a busca por nome
----------------------
O `api.MD` documenta apenas `page` em `GET /pcontrole/api/jogadores` — não há
parâmetro de busca conhecido. Como o painel Vue original tem campo de busca, é
provável que exista um não documentado. Então:

1. `detectar_filtro_servidor` testa uma lista de nomes prováveis uma única vez
   e memoriza o que funcionar — a partir daí a busca é instantânea;
2. se nenhum funcionar, cai para varredura paginada: lê um lote de páginas por
   vez e filtra localmente, deixando o usuário decidir se continua.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache

from ..dominio import Jogador, Pagina
from . import parser
from .arena_client import ArenaClient, ArenaError

logger = logging.getLogger(__name__)

#: Nomes de parâmetro testados ao procurar um filtro server-side.
CANDIDATOS_FILTRO = ["search", "q", "nome", "busca", "filtro", "name", "termo"]

#: Termo que não deve casar com nada — se o total cair, o filtro é real.
_SONDA = "zzqqxjw"

_CHAVE_FILTRO = "arena:param-busca"
_TTL_FILTRO = 3600


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Resultado:
    """O que a view precisa para renderizar uma consulta."""

    termo: str = ""
    #: "listagem" | "servidor" | "varredura" | "id"
    modo: str = "listagem"
    jogadores: list[Jogador] = field(default_factory=list)
    #: Preenchida nos modos "listagem" e "servidor" (a API é quem pagina).
    pagina: Pagina | None = None

    # Estado da varredura local
    paginas_lidas: int = 0
    proxima_pagina: int | None = None
    total_paginas: int = 0
    primeira_pagina: int = 1

    @property
    def tem_mais_para_varrer(self) -> bool:
        return self.modo == "varredura" and self.proxima_pagina is not None

    @property
    def ultima_lida(self) -> int:
        return self.primeira_pagina + max(0, self.paginas_lidas - 1)

    @property
    def paginas_restantes(self) -> int:
        if self.proxima_pagina is None:
            return 0
        return max(0, self.total_paginas - self.proxima_pagina + 1)

    @property
    def jogadores_examinados(self) -> int:
        return self.paginas_lidas * 10


# ---------------------------------------------------------------------------
# Leituras com cache
# ---------------------------------------------------------------------------
def _chave_lista(numero: int, extra: dict | None) -> str:
    sufixo = "&".join(f"{k}={v}" for k, v in sorted((extra or {}).items()))
    return f"arena:lista:{numero}:{sufixo}"


def obter_pagina(cliente: ArenaClient, numero: int, extra: dict | None = None) -> Pagina:
    chave = _chave_lista(numero, extra)
    guardada = cache.get(chave)
    if guardada is not None:
        return guardada
    pagina = parser.pagina(cliente.listar_jogadores(numero, extra))
    cache.set(chave, pagina)
    return pagina


#: Tamanho de página imposto pelo servidor (ver api.MD).
POR_PAGINA_API = 10


def montar_pagina(cliente: ArenaClient, tela: int, extra: dict | None = None) -> Pagina:
    """Monta uma página da tela juntando páginas da API.

    A API fixa 10 por página. Para exibir N por tela, buscamos as páginas que
    cobrem a fatia `[(tela-1)*N, tela*N)` e recortamos o excedente. Com N=16
    são 2 ou 3 requisições, mas as páginas de borda são reaproveitadas do cache
    ao navegar em sequência.
    """
    por_tela = max(1, settings.ARENA["POR_PAGINA"])
    if por_tela == POR_PAGINA_API:
        return obter_pagina(cliente, tela, extra)

    inicio = (tela - 1) * por_tela
    primeira_api = inicio // POR_PAGINA_API + 1
    ultima_api = (inicio + por_tela - 1) // POR_PAGINA_API + 1

    coletados: list[Jogador] = []
    total = 0
    for numero in range(primeira_api, ultima_api + 1):
        parcial = obter_pagina(cliente, numero, extra)
        total = parcial.total
        coletados.extend(parcial.jogadores)
        if numero >= parcial.ultima:
            break

    # Quanto do primeiro bloco de 10 sobra antes do começo da fatia.
    deslocamento = inicio - (primeira_api - 1) * POR_PAGINA_API
    return Pagina(
        numero=tela,
        ultima=max(1, -(-total // por_tela)),
        total=total,
        por_pagina=por_tela,
        jogadores=coletados[deslocamento:deslocamento + por_tela],
    )


def obter_jogador(cliente: ArenaClient, jogador_id: int) -> Jogador:
    """Ficha completa de um jogador — uma requisição."""
    chave = f"arena:jogador:{jogador_id}"
    guardado = cache.get(chave)
    if guardado is not None:
        return guardado
    jogador = parser.jogador_completo(cliente.detalhe_jogador(jogador_id))
    cache.set(chave, jogador)
    return jogador


# ---------------------------------------------------------------------------
# Filtro no servidor
# ---------------------------------------------------------------------------
def detectar_filtro_servidor(cliente: ArenaClient) -> str | None:
    """Descobre se a lista aceita algum parâmetro de busca.

    Custa até `len(CANDIDATOS_FILTRO) + 1` requisições, uma única vez por hora
    (o resultado fica no cache). `ARENA_PARAM_BUSCA` no `.env` pula a detecção:
    informe o nome do parâmetro se já souber, ou `off` para ir direto à
    varredura.
    """
    configurado = (settings.ARENA.get("PARAM_BUSCA") or "auto").strip()
    if configurado.lower() in {"off", "none", "nao", "não"}:
        return None
    if configurado.lower() != "auto":
        return configurado

    memorizado = cache.get(_CHAVE_FILTRO)
    if memorizado is not None:
        return memorizado or None

    try:
        total_base = parser.inteiro(cliente.listar_jogadores(1).get("total"))
    except ArenaError:
        return None

    achado = ""
    for candidato in CANDIDATOS_FILTRO:
        try:
            envelope = cliente.listar_jogadores(1, {candidato: _SONDA})
        except ArenaError:
            continue
        total = parser.inteiro(envelope.get("total"))
        # Se o servidor filtrou de verdade, o total cai (idealmente para 0).
        if total < total_base:
            achado = candidato
            logger.info("Busca server-side disponível pelo parâmetro '%s'.", candidato)
            break

    if not achado:
        logger.info(
            "Nenhum parâmetro de busca aceito pela API; usando varredura paginada."
        )
    cache.set(_CHAVE_FILTRO, achado, _TTL_FILTRO)
    return achado or None


# ---------------------------------------------------------------------------
# Comparação local
# ---------------------------------------------------------------------------
def _normalizar(texto: str) -> str:
    """Minúsculas e sem acento — `"Mbappé"` casa com `"mbappe"`."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()


def combina(jogador: Jogador, termos: list[str]) -> bool:
    """Todos os termos precisam aparecer em algum campo do jogador.

    Só campos que a tela mostra: casar por clube da liga devolveria resultados
    sem nada visível explicando o porquê.
    """
    alvo = _normalizar(f"{jogador.nome} {jogador.nacionalidade} {jogador.posicao}")
    return all(termo in alvo for termo in termos)


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------
def consultar(
    cliente: ArenaClient,
    termo: str = "",
    pagina: int = 1,
    de: int = 1,
) -> Resultado:
    """Ponto de entrada da barra de consulta.

    - termo vazio → lista ao vivo, página a página;
    - só dígitos → busca direta por ID (uma requisição);
    - texto → filtro no servidor, se existir; senão, varredura paginada a
      partir da página `de`.
    """
    termo = (termo or "").strip()

    if not termo:
        pag = montar_pagina(cliente, pagina)
        return Resultado(modo="listagem", pagina=pag, jogadores=pag.jogadores)

    if termo.isdigit():
        jogador = obter_jogador(cliente, int(termo))
        return Resultado(termo=termo, modo="id", jogadores=[jogador])

    parametro = detectar_filtro_servidor(cliente)
    if parametro:
        pag = montar_pagina(cliente, pagina, {parametro: termo})
        return Resultado(termo=termo, modo="servidor", pagina=pag, jogadores=pag.jogadores)

    return _varrer(cliente, termo, de)


def _varrer(cliente: ArenaClient, termo: str, de: int) -> Resultado:
    """Lê um lote de páginas e filtra localmente.

    Cada página custa ~1,2 s, então o lote é pequeno de propósito: a tela
    responde rápido e oferece continuar de onde parou.
    """
    cfg = settings.ARENA
    lote = max(1, cfg["PAGINAS_POR_VARREDURA"])
    teto = max(lote, cfg["LIMITE_VARREDURA"])

    termos = [_normalizar(t) for t in termo.split() if t]
    achados: list[Jogador] = []
    numero = max(1, de)
    primeira = numero
    ultima = numero
    lidas = 0

    while lidas < lote:
        pag = obter_pagina(cliente, numero)
        ultima = pag.ultima or numero
        achados.extend(j for j in pag.jogadores if combina(j, termos))
        lidas += 1
        numero += 1
        if numero > ultima or numero > teto:
            break

    esgotou = numero > ultima or numero > teto
    return Resultado(
        termo=termo,
        modo="varredura",
        jogadores=achados,
        paginas_lidas=lidas,
        primeira_pagina=primeira,
        proxima_pagina=None if esgotou else numero,
        total_paginas=ultima,
    )
