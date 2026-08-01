# Jogadores FC26

Duas camadas independentes sobre a API interna do painel Arena Virtual
(documentada em [api.MD](api.MD)):

| Rota | O que é | Lê de onde |
|---|---|---|
| `/` | Barra de consulta que renderiza os jogadores na hora | API, ao vivo |
| `/players/local/` | Mesmo visual, porém lendo o acervo (instantâneo) | Banco |
| — | Acervo: banco com todos os jogadores, atualizado todo dia | Sincronização agendada |

O painel `/` **não usa o banco** — vai direto à API a cada busca. O acervo é uma
cópia local completa, alimentada pelo agendador; `/players/local/` navega esse
acervo com busca e filtros instantâneos (sem rate limit). O cabeçalho tem um
alternador **Ao vivo / Acervo local** entre os dois.

---

## Como consultar

A barra aceita três coisas:

| O que você digita | O que acontece |
|---|---|
| *(nada)* | Lista ao vivo, 16 por página, navegável |
| `231747` — só dígitos | Vai direto à ficha: **uma** requisição |
| `mbappe`, `Real Madrid`, `ATA` | Busca por texto (veja abaixo) |

A busca por texto ignora acentos e maiúsculas, e aceita vários termos
(`mbappe ata` exige que ambos apareçam).

### Quantos por página

A tela mostra **16 por página** (grade 4×4 nas telas largas), mas a API entrega
10 por página e não aceita `per_page`. Então cada página da tela é montada
juntando páginas da API e recortando a sobra — 2 a 3 requisições, com as páginas
de borda reaproveitadas do cache ao navegar em sequência.

Ajuste com `ARENA_POR_PAGINA`. Múltiplos de 10 encaixam exato e custam menos
requisições (`10` = 1 por tela, `20` = 2, `30` = 3); `16` cai em 2 ou 3
conforme o deslocamento da página.

### O ponto delicado: a API não documenta busca

O `api.MD` descreve apenas `page` em `GET /pcontrole/api/jogadores`, com
`per_page` fixo em 10 — nenhum parâmetro de busca. Como não dá para saber sem
credenciais reais se existe um filtro não documentado, o painel resolve os dois
casos sozinho:

1. **Detecção automática.** Na primeira busca por texto, testa
   `search`, `q`, `nome`, `busca`, `filtro`, `name`, `termo` e compara o `total`
   devolvido com o total sem filtro. Se algum reduzir o total, o filtro é real —
   e o nome fica memorizado por uma hora. A partir daí a busca é instantânea e o
   autocomplete liga sozinho.
2. **Varredura paginada**, se nenhum funcionar. O painel lê um lote de páginas
   (padrão: 15 ≈ 18 s), filtra localmente e mostra até onde olhou, com um botão
   para continuar de onde parou. É honesto sobre a cobertura em vez de fingir
   que varreu tudo.

Se você já souber o nome do parâmetro, pule a detecção com
`ARENA_PARAM_BUSCA=search` no `.env`. Para forçar a varredura, use
`ARENA_PARAM_BUSCA=off`.

---

## Acervo e sincronização diária

O serviço `cron` do Compose roda o agendador: dorme até `SYNC_HORARIO`
(padrão **03:30**, horário de São Paulo), sincroniza e volta a dormir.

Cada rodada faz duas coisas:

1. **Lista completa** — varre as 1.942 páginas (~40 min) e atualiza todos os
   jogadores. É daqui que vêm valor de mercado, multa, dono, à venda, leilão.
2. **Fichas técnicas** — dentro de um orçamento de tempo
   (`SYNC_MINUTOS_DETALHES`, padrão 120 min). A ficha é **1 requisição por
   jogador**: os 19.415 levariam ~6,5 h, então elas rodam em **rodízio** — quem
   está sem ficha primeiro, depois os verificados há mais tempo. Com 120 min/dia
   a base inteira se renova a cada ~3 dias.

### Só grava o que mudou

A sincronização compara campo a campo com o que está no banco. Sem diferença,
nada é reescrito. Com diferença, o campo é atualizado, `alterado_em` avança e a
mudança vira uma linha em `Alteracao` (`de`, `para`, `quando`) — dá para
responder "quanto o passe do Mbappé variou este mês" olhando só o histórico.

Quem some da listagem **não é apagado**: ganha `ausente_desde`, e o carimbo é
limpo se voltar a aparecer.

O payload cru também é guardado (`payload_lista`, `payload_detalhe`), então
nenhum campo devolvido pela API se perde — nem os que ainda não viraram coluna
(o detalhe real traz 202 chaves).

### Comandos

```bash
docker compose logs -f cron                  # acompanhar o agendador

# Avulsos (usam o mesmo banco)
docker compose run --rm painel python manage.py sincronizar_jogadores --paginas 20
docker compose run --rm painel python manage.py sincronizar_jogadores          # ~40 min
docker compose run --rm painel python manage.py sincronizar_detalhes --minutos 30
docker compose run --rm painel python manage.py sincronizar_detalhes --faltantes
docker compose run --rm painel python manage.py descobrir_flags --amostra 5
docker compose run --rm painel python manage.py createsuperuser   # para o /admin
```

Todos são idempotentes e podem ser interrompidos com `Ctrl+C` sem corromper
nada. Cada rodada vira um registro em `Execucao`, visível no `/admin`.

### Onde os dados ficam

SQLite em `/app/dados/jogadores.sqlite3` (volume `dados`), com WAL ligado para o
agendador escrever sem travar leituras. Para usar outro banco, defina
`DATABASE_URL` no `.env`:

```
DATABASE_URL=postgres://usuario:senha@host:5432/jogadores
```

O `/admin` dá uma visão navegável do acervo: jogadores com a ficha embutida,
histórico de alterações e o log das execuções.

### Prefere o cron do sistema?

Desligue o serviço (`docker compose up -d painel`) e agende você mesmo:

```
30 3 * * *  cd /caminho/do/projeto && docker compose run --rm painel python manage.py sincronizar_jogadores
```

---

## Rodando com Docker

```bash
cp .env.example .env      # Windows: copy .env.example .env
docker compose up -d --build
```

Sobem dois contêineres: `painel` (web, porta 8000) e `cron` (agendador). Abra
<http://127.0.0.1:8000/>. Sem credenciais o painel sobe e explica na tela o que
falta — preencha `ARENA_LOGIN` e `ARENA_SENHA` no `.env` e rode
`docker compose up -d` de novo.

```bash
docker compose logs -f painel
docker compose logs -f cron
docker compose up -d painel      # só o painel, sem o agendador
docker compose down              # o volume `dados` (banco) permanece
docker compose down -v           # apaga o banco também
```

O `cron` espera o `painel` ficar saudável antes de subir: assim só um processo
aplica as migrações no banco recém-criado.

O contêiner roda **um worker com threads**, de propósito: o intervalo entre
chamadas, a sessão autenticada e o cache são estado de processo — vários workers
teriam cada um o seu e furariam o rate limit da API. O volume `dados` guarda o
banco do acervo e o cookie de login, que evita relogar a cada `up`.

## Rodando sem Docker

```bash
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

O agendador, fora do Docker, é um processo à parte:

```bash
python manage.py agendar_sincronizacao
```

---

## Estrutura

```
Dockerfile                  gunicorn (1 worker + threads) + whitenoise
docker-compose.yml          serviços `painel` e `cron` + volume `dados`
config/settings.py          banco, cache, config da API e do agendador
jogadores/
  data/fifa_labels.py       rótulos pt-BR das flags C*/E*, grupos de atributos
  services/arena_client.py  login CSRF, rate limit, relogin, cliente do processo
  services/parser.py        JSON da API → dataclasses
  --- painel (ao vivo, sem banco) ---
  dominio.py                dataclasses Jogador / Ficha / Pagina
  services/busca.py         detecção do filtro, varredura, paginação, cache
  views.py                  consulta, detalhe, sugestoes, saude
  templatetags/painel.py    moeda BR, cores por faixa, geometria do radar
  templates/jogadores/      base, consulta, detalhe e parciais
  --- acervo (banco) ---
  models.py                 Jogador, JogadorDetalhe, Alteracao, Execucao
  admin.py                  navegação pelo acervo e pelo histórico
  services/persistencia.py  payload → banco, com detecção de mudanças
  services/agendamento.py   cálculo do próximo disparo
  management/commands/      sincronizar_jogadores, sincronizar_detalhes,
                            agendar_sincronizacao, descobrir_flags
  tests.py, tests_acervo.py
```

### Detalhes que importam

- **`nome`** vem como `"(26) K. Mbappé"` — o parser separa nome e idade.
- **`passe`** e **`valor_a_venda`** vêm no formato BR (`"475.200,00"`).
- **`nome_escudo`** é o clube dentro da liga; **`time`** (só no detalhe) é o
  clube da vida real. São campos diferentes.
- Flags `C*`/`E*` são varridas por regex, não por intervalo fixo: se o site
  passar a mandar códigos novos, eles aparecem com o próprio código em vez de
  sumirem.
- O healthcheck bate em `/saude/`, que não chama a API — checar `/` gastaria uma
  requisição do rate limit a cada 30 s.

### Rótulos das características — precisam de correção

`jogadores/data/fifa_labels.py` traduz `C01`..`C82` e `E01`..`E17` para pt-BR,
mas **só `C01`, `C06`, `E02` e `E14` são confirmados** pela documentação. O
resto foi inferido — e os dados reais já mostram que vários estão errados:
Mbappé e Haaland têm `E17`, que o arquivo chuta como "Goleiro completo".

Com o acervo populado, dá para deduzir os certos:

```bash
docker compose run --rm painel python manage.py sincronizar_detalhes --minutos 20
docker compose run --rm painel python manage.py descobrir_flags --amostra 5
```

O comando mostra cada flag, sua frequência e exemplos de quem a tem — pelos
nomes é fácil identificar o que cada código significa. Códigos sem rótulo nunca
quebram a tela: aparecem como o próprio código.

---

## Testes

```bash
python manage.py test jogadores
```

62 testes, **nenhum toca a rede**: o cliente da API é substituído por um duplo
que simula tanto o cenário com filtro no servidor quanto o sem, além de erros de
autenticação e de rede. Cobrem a paginação de 16, a detecção de mudanças, o
rodízio das fichas e o cálculo do próximo disparo do agendador.

---

## Configuração (`.env`)

| Variável | Padrão | Para quê |
|---|---|---|
| `ARENA_LOGIN` / `ARENA_SENHA` | — | Credenciais da sua conta no painel |
| `ARENA_DELAY` | `1.2` | Segundos entre chamadas (~60 req/min) |
| `ARENA_POR_PAGINA` | `16` | Jogadores por página na tela (veja abaixo) |
| `ARENA_PARAM_BUSCA` | `auto` | `auto`, `off`, ou o nome do parâmetro |
| `ARENA_PAGINAS_POR_VARREDURA` | `15` | Páginas por lote na varredura |
| `ARENA_LIMITE_VARREDURA` | `300` | Teto de páginas numa mesma busca |
| `CACHE_TTL` | `600` | Segundos que uma página/ficha fica em cache |
| `DATABASE_URL` | *(SQLite)* | Banco do acervo |
| `SYNC_HORARIO` | `03:30` | Horário da rodada diária |
| `SYNC_MINUTOS_DETALHES` | `120` | Orçamento das fichas por rodada (0 desliga) |
| `SYNC_AO_INICIAR` | `False` | Sincronizar assim que o agendador sobe |
| `DJANGO_SECRET_KEY` | inseguro | Troque antes de expor em rede |
| `DJANGO_ALLOWED_HOSTS` | `*` | Restrinja em rede |

A API é interna e privada: uso restrito à sua conta autorizada, sem
redistribuir os dados.
