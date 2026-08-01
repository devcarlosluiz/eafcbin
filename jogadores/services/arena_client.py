"""Cliente da API interna do painel Arena Virtual.

Implementa o fluxo descrito em `api.MD`:

* login por sessão + token CSRF extraído do HTML da home;
* header obrigatório `X-Requested-With: XMLHttpRequest` (sem ele as rotas
  devolvem o HTML da SPA em vez de JSON);
* respeito ao rate limit (~60 req/min) e ao header `Retry-After` no `429`;
* relogin automático quando a sessão expira (resposta deixa de ser JSON).

O cliente é compartilhado pelo processo (`cliente_compartilhado`) para
reaproveitar a sessão autenticada entre requisições HTTP do painel. Como o
servidor WSGI atende em threads, todo acesso à rede passa por um lock — que
também serializa o intervalo entre chamadas, mantendo o rate limit honesto.

Uso restrito à conta autorizada do próprio usuário — os dados não devem ser
redistribuídos.
"""

from __future__ import annotations

import http.cookiejar
import logging
import re
import threading
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_RE_TOKEN_INPUT = re.compile(
    r'<input[^>]+name=["\']_token["\'][^>]+value=["\']([^"\']+)["\']', re.I
)
_RE_TOKEN_INPUT_INV = re.compile(
    r'<input[^>]+value=["\']([^"\']+)["\'][^>]+name=["\']_token["\']', re.I
)
_RE_TOKEN_META = re.compile(
    r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']', re.I
)


class ArenaError(RuntimeError):
    """Falha genérica de comunicação com a API."""


class ArenaAuthError(ArenaError):
    """Credenciais ausentes/inválidas ou sessão que não pôde ser renovada."""


class ArenaClient:
    """Sessão autenticada contra `https://sofifabrasil.arenavirtual.net`."""

    API = "/pcontrole/api"

    def __init__(
        self,
        login: str,
        senha: str,
        host: str = "https://sofifabrasil.arenavirtual.net",
        delay: float = 1.2,
        timeout: float = 20.0,
        cookies_path: str | None = None,
    ) -> None:
        if not login or not senha:
            raise ArenaAuthError(
                "Credenciais não configuradas. Defina ARENA_LOGIN e ARENA_SENHA "
                "no arquivo .env."
            )
        self.login_usuario = login
        self.senha = senha
        self.host = host.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self._ultima_chamada = 0.0
        self._autenticado = False
        # Reentrante: `_get_json` pode chamar `autenticar`, que também espera.
        self._trava = threading.RLock()

        self.session = requests.Session()
        self.session.headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        })

        if cookies_path:
            jar = http.cookiejar.LWPCookieJar(cookies_path)
            try:
                jar.load(ignore_discard=True, ignore_expires=True)
                self._autenticado = True
                logger.debug("Sessão reaproveitada de %s", cookies_path)
            except (FileNotFoundError, http.cookiejar.LoadError):
                pass
            self.session.cookies = jar  # type: ignore[assignment]
        self._cookies_path = cookies_path

    # -- infraestrutura -----------------------------------------------------
    def _url(self, caminho: str) -> str:
        if caminho.startswith("http"):
            return caminho
        return f"{self.host}/{caminho.lstrip('/')}"

    def _aguardar(self) -> None:
        """Espaça as chamadas para não estourar o rate limit."""
        espera = self.delay - (time.monotonic() - self._ultima_chamada)
        if espera > 0:
            time.sleep(espera)
        self._ultima_chamada = time.monotonic()

    def _salvar_cookies(self) -> None:
        jar = self.session.cookies
        if self._cookies_path and isinstance(jar, http.cookiejar.LWPCookieJar):
            try:
                jar.save(ignore_discard=True, ignore_expires=True)
            except OSError as exc:
                logger.warning("Não foi possível gravar os cookies: %s", exc)

    # -- autenticação -------------------------------------------------------
    def _csrf_token(self) -> str:
        self._aguardar()
        resp = self.session.get(
            self._url("/"), timeout=self.timeout, headers={"Accept": "text/html"}
        )
        resp.raise_for_status()
        for padrao in (_RE_TOKEN_INPUT, _RE_TOKEN_INPUT_INV, _RE_TOKEN_META):
            achado = padrao.search(resp.text)
            if achado:
                return achado.group(1)
        raise ArenaAuthError("Token CSRF não encontrado no HTML da home.")

    def autenticar(self) -> dict[str, Any]:
        """Faz `POST /login` reaproveitando os cookies da home."""
        with self._trava:
            token = self._csrf_token()
            self._aguardar()
            resp = self.session.post(
                self._url("/login"),
                data={
                    "_token": token,
                    "login": self.login_usuario,
                    "password": self.senha,
                    "remember": "on",
                },
                headers={"X-CSRF-TOKEN": token, "Referer": self._url("/")},
                timeout=self.timeout,
            )
            if resp.status_code in (401, 403, 419, 422):
                raise ArenaAuthError(
                    f"Login recusado (HTTP {resp.status_code}). "
                    "Confira ARENA_LOGIN/ARENA_SENHA."
                )
            resp.raise_for_status()
            try:
                usuario = resp.json()
            except ValueError:
                raise ArenaAuthError(
                    "O login não devolveu JSON — provavelmente as credenciais "
                    "estão incorretas ou o fluxo do site mudou."
                ) from None
            self._autenticado = True
            self._salvar_cookies()
            logger.info("Autenticado como %s", usuario.get("login"))
            return usuario

    def garantir_sessao(self) -> None:
        if not self._autenticado:
            self.autenticar()

    # -- requisições --------------------------------------------------------
    def _get_json(self, caminho: str, params: dict | None = None) -> Any:
        """GET com backoff no 429 e um relogin automático se a sessão caiu."""
        with self._trava:
            for tentativa in range(4):
                self._aguardar()
                try:
                    resp = self.session.get(
                        self._url(caminho), params=params, timeout=self.timeout
                    )
                except requests.RequestException as exc:
                    raise ArenaError(f"Falha de rede ao chamar {caminho}: {exc}") from exc

                if resp.status_code == 429:
                    espera = float(resp.headers.get("Retry-After", 5) or 5)
                    logger.warning("429 recebido; aguardando %.1fs.", espera)
                    time.sleep(espera + 0.5)
                    continue

                if resp.status_code == 404:
                    raise ArenaError(f"Não encontrado na API: {caminho}")

                if resp.status_code >= 500:
                    time.sleep(2 ** tentativa)
                    continue

                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    # HTML no lugar de JSON = sessão expirada (veio a SPA).
                    if tentativa == 0 or not self._autenticado:
                        logger.info("Sessão expirada; refazendo login.")
                        self._autenticado = False
                        self.autenticar()
                        continue
                    raise ArenaAuthError(
                        f"Resposta não-JSON em {caminho}; sessão não renovada."
                    ) from None

            raise ArenaError(f"Falha ao obter {caminho} após várias tentativas.")

    # -- endpoints ----------------------------------------------------------
    def listar_jogadores(self, page: int = 1, extra: dict | None = None) -> dict[str, Any]:
        """`GET /pcontrole/api/jogadores?page=N` — envelope do Laravel.

        `per_page` é fixo em 10 no servidor. `extra` permite testar parâmetros
        de filtro não documentados (ver `busca.detectar_filtro_servidor`).
        """
        self.garantir_sessao()
        params = {"page": page}
        if extra:
            params.update(extra)
        dados = self._get_json(f"{self.API}/jogadores", params)
        if not isinstance(dados, dict) or "data" not in dados:
            raise ArenaError(f"Envelope inesperado na página {page}.")
        return dados

    def detalhe_jogador(self, jogador_id: int) -> dict[str, Any]:
        """`GET /pcontrole/api/jogadores/{id}` — 1 requisição por jogador."""
        self.garantir_sessao()
        dados = self._get_json(f"{self.API}/jogadores/{jogador_id}")
        if isinstance(dados, dict) and "data" in dados:
            return dados["data"]
        if isinstance(dados, dict) and dados.get("id"):
            return dados
        raise ArenaError(f"Detalhe inesperado para o jogador {jogador_id}.")


# ---------------------------------------------------------------------------
# Instância compartilhada pelo processo
# ---------------------------------------------------------------------------
_cliente: ArenaClient | None = None
_trava_criacao = threading.Lock()


def cliente_compartilhado() -> ArenaClient:
    """Devolve o cliente do processo, criando-o na primeira chamada.

    Reaproveitar a mesma instância mantém a sessão autenticada e o controle de
    rate limit centralizados — criar um cliente por requisição relogaria toda
    hora e furaria o limite de ~60 req/min.
    """
    global _cliente
    if _cliente is None:
        with _trava_criacao:
            if _cliente is None:
                from django.conf import settings

                cfg = settings.ARENA
                _cliente = ArenaClient(
                    login=cfg["LOGIN"],
                    senha=cfg["SENHA"],
                    host=cfg["HOST"],
                    delay=cfg["DELAY"],
                    timeout=cfg["TIMEOUT"],
                    cookies_path=cfg["COOKIES"],
                )
    return _cliente


def redefinir_cliente() -> None:
    """Descarta a instância compartilhada (usado nos testes)."""
    global _cliente
    _cliente = None
