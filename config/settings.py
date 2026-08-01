"""Configuração do projeto — jogadores FC26.

São duas camadas independentes:

* **Painel de consulta** — continua *ao vivo*: cada busca vai direto à API
  interna (ver api.MD) e é renderizada na hora, sem passar pelo banco.
* **Acervo** — um banco com todos os jogadores, alimentado pelos comandos de
  sincronização e mantido em dia por um agendador diário.
"""
from pathlib import Path
from urllib.parse import unquote, urlparse
import os

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# .env (carregador mínimo, sem dependências externas)
# ---------------------------------------------------------------------------
def _carregar_env(caminho: Path) -> None:
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env(BASE_DIR / ".env")


def env(chave, padrao=None):
    return os.environ.get(chave, padrao)


def env_bool(chave, padrao=False):
    valor = os.environ.get(chave)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "on", "sim"}


def env_int(chave, padrao):
    try:
        return int(os.environ.get(chave, padrao))
    except (TypeError, ValueError):
        return padrao


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-inseguro-troque-em-producao")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

#: Diretório para estado que não é banco: o cookie da sessão da API.
DADOS_DIR = Path(env("DJANGO_DATA_DIR", str(BASE_DIR)))
DADOS_DIR.mkdir(parents=True, exist_ok=True)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "jogadores",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Banco do acervo (Postgres)
# ---------------------------------------------------------------------------
def _banco_de_url(url: str) -> dict:
    """Traduz uma URL de conexão. Suporta postgres e mysql."""
    partes = urlparse(url)
    esquema = partes.scheme.replace("postgresql", "postgres")
    motores = {
        "postgres": "django.db.backends.postgresql",
        "mysql": "django.db.backends.mysql",
    }
    if esquema not in motores:
        raise ValueError(f"DATABASE_URL com esquema não suportado: {partes.scheme}")
    return {
        "ENGINE": motores[esquema],
        "NAME": (partes.path or "").lstrip("/"),
        "USER": unquote(partes.username or ""),
        "PASSWORD": unquote(partes.password or ""),
        "HOST": partes.hostname or "",
        "PORT": str(partes.port or ""),
        "CONN_MAX_AGE": 60,
    }


_URL_BANCO = env("DATABASE_URL", "")
if not _URL_BANCO:
    raise RuntimeError(
        "DATABASE_URL não definida. Configure um Postgres, ex.: "
        "postgres://usuario:senha@host:5432/nome"
    )
DATABASES = {"default": _banco_de_url(_URL_BANCO)}

#: Cache em memória do processo. Guarda páginas e fichas já buscadas por alguns
#: minutos, para que paginar de volta não gaste requisições do rate limit.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "arena",
        "TIMEOUT": env_int("CACHE_TTL", 600),
        "OPTIONS": {"MAX_ENTRIES": 4000, "CULL_FREQUENCY": 4},
    }
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATIC_ROOT = BASE_DIR / "staticfiles"

# Com DEBUG=False o runserver não serve estáticos; no contêiner quem faz isso é
# o WhiteNoise. Fora do Docker ele costuma não estar instalado — daí o guard.
try:
    import whitenoise  # noqa: F401
except ImportError:
    pass
else:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# API interna do painel Arena Virtual (ver api.MD)
# ---------------------------------------------------------------------------
ARENA = {
    "HOST": env("ARENA_HOST", "https://sofifabrasil.arenavirtual.net"),
    "LOGIN": env("ARENA_LOGIN", ""),
    "SENHA": env("ARENA_SENHA", ""),
    # Rate limit do servidor: ~60 req/min → ~1,2 s entre chamadas.
    "DELAY": float(env("ARENA_DELAY", "1.2")),
    "TIMEOUT": float(env("ARENA_TIMEOUT", "20")),
    # Cookie da sessão, reaproveitado entre requisições para não relogar sempre.
    "COOKIES": str(DADOS_DIR / ".arena_cookies.txt"),
    # Jogadores por página na tela. A API fixa 10 por página, então valores
    # diferentes de 10 são montados juntando páginas dela: 16 custa 2–3
    # requisições por tela (múltiplos de 10 encaixam exato e custam menos).
    "POR_PAGINA": env_int("ARENA_POR_PAGINA", 16),
    # Parâmetro de busca da API. "auto" = detectar sozinho na primeira busca;
    # "off" = ir direto à varredura; ou informe o nome, se já souber.
    "PARAM_BUSCA": env("ARENA_PARAM_BUSCA", "auto"),
    # Quantas páginas varrer por vez quando a API não filtra no servidor.
    # Cada página custa ~1,2 s — 15 páginas ≈ 18 s de espera na tela.
    "PAGINAS_POR_VARREDURA": env_int("ARENA_PAGINAS_POR_VARREDURA", 15),
    # Teto absoluto de páginas varridas numa mesma busca.
    "LIMITE_VARREDURA": env_int("ARENA_LIMITE_VARREDURA", 300),
}

# ---------------------------------------------------------------------------
# Agendador diário (comando `agendar_sincronizacao`)
# ---------------------------------------------------------------------------
SINCRONIZACAO = {
    # Horário local (TIME_ZONE) em que a varredura diária começa.
    "HORARIO": env("SYNC_HORARIO", "03:30"),
    # Minutos dedicados às fichas técnicas depois de atualizar a lista.
    # A lista inteira leva ~40 min; as fichas são 1 requisição por jogador, então
    # elas rodam por rodízio (as mais antigas primeiro) dentro deste orçamento.
    "MINUTOS_DETALHES": env_int("SYNC_MINUTOS_DETALHES", 120),
    # Rodar uma sincronização assim que o agendador sobe, sem esperar o horário.
    "AO_INICIAR": env_bool("SYNC_AO_INICIAR", False),
}

# ---------------------------------------------------------------------------
# API externa do acervo (painel de campeonatos — ver jogadores/api/)
# ---------------------------------------------------------------------------
#: Chaves aceitas no header `X-API-Key` — cadastradas no admin do Django, em
#: `ChaveApiExterna` (nome + token), não aqui.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["jogadores.api.permissions.TemChaveApiValida"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simples": {"format": "[{levelname}] {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simples"}},
    "loggers": {"jogadores": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")}},
}
