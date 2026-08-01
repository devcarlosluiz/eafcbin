FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    # Só o cookie da sessão da API vive aqui — o projeto não tem banco.
    DJANGO_DATA_DIR=/app/dados

WORKDIR /app

# Dependências primeiro: só reinstala quando os requirements mudam.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuário sem privilégios; `dados` precisa ser dele para gravar os cookies.
RUN useradd --create-home --uid 1000 painel \
    && mkdir -p /app/dados /app/staticfiles \
    && chown -R painel:painel /app

USER painel

# `collectstatic` roda no build para o WhiteNoise ter o manifesto pronto.
# SECRET_KEY e DATABASE_URL são só para satisfazer o settings aqui — não chega
# a conectar no banco; em runtime os valores reais vêm do .env.
RUN DJANGO_SECRET_KEY=build DJANGO_DATA_DIR=/tmp \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    python manage.py collectstatic --noinput --clear

EXPOSE 8000

# `/saude/` não chama a API — checar `/` gastaria uma requisição do rate limit.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/saude/')"

ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]

# Um worker com threads, de propósito: o controle de rate limit (~60 req/min),
# a sessão autenticada e o cache de consultas são estado de processo. Vários
# workers teriam cada um o seu e furariam o limite da API.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "180", \
     "--access-logfile", "-"]
