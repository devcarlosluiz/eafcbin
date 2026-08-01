#!/bin/sh
# Prepara o acervo antes de subir qualquer processo. `migrate` é idempotente,
# então roda tanto no serviço web quanto no agendador e nos comandos avulsos.
set -e

if [ -z "$ARENA_LOGIN" ] || [ -z "$ARENA_SENHA" ]; then
  echo "AVISO: ARENA_LOGIN/ARENA_SENHA nao definidos — o painel sobe, mas as"
  echo "       consultas e a sincronizacao vao falhar ate voce preencher o .env."
fi

echo "> Aplicando migracoes..."
python manage.py migrate --noinput

exec "$@"
