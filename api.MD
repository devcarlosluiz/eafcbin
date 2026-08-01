# API interna do painel Arena Virtual

Documentação da API **não oficial** consumida pelo painel Vue e usada por este
projeto. Requer autenticação (conta no painel). Sujeita a mudanças pelo site.

- **Host:** `https://sofifabrasil.arenavirtual.net`
- **Base da API:** `/pcontrole/api/`
- **Stack:** Laravel + Vue (SPA). Respostas em JSON.
- **Header obrigatório:** `X-Requested-With: XMLHttpRequest`
  (sem ele, rotas devolvem o HTML da SPA em vez de JSON).
- **Rate limit:** ~60 req/min. Excesso → `HTTP 429` com header `Retry-After`.
  Use ~1,2 s entre requisições.

---

## Autenticação (sessão + CSRF)

Fluxo de login por cookie de sessão, igual ao painel:

1. `GET /` → extrair o token CSRF do HTML:
   `<input name="_token" value="...">` (ou `<meta name="csrf-token" content="...">`).
2. `POST /login` (form-urlencoded), mantendo os cookies da etapa 1:

   | campo | valor |
   |-------|-------|
   | `_token` | token CSRF da etapa 1 |
   | `login` | seu usuário |
   | `password` | sua senha |
   | `remember` | `on` (opcional) |

   **Resposta:** `200` com JSON do usuário e cookie de sessão setado.

   ```json
   { "id": 236193, "login": "letal97", "nome": "Luiz Otávio",
     "email": "...", "dinheiro": "42330.19", "painel_id": 29, ... }
   ```

3. As requisições seguintes reutilizam o cookie de sessão. Se a sessão expira,
   a API devolve o HTML da SPA (não-JSON) — basta refazer o login.

> A rota `/login` (e `/*/login`, `/api/`) está em `Disallow` no `robots.txt`,
> mas o acesso aqui é autenticado, com credenciais próprias.

---

## `GET /pcontrole/api/jogadores` — lista paginada

Lista resumida de todos os jogadores (visão de mercado/liga).

**Query params**
- `page` (int) — página. `per_page` é **fixo em 10** pelo servidor
  (valores maiores são ignorados).

**Envelope (paginação padrão do Laravel)**

```jsonc
{
  "current_page": 1,
  "data": [ /* jogadores */ ],
  "first_page_url": "...?page=1",
  "from": 1,
  "last_page": 1942,
  "last_page_url": "...?page=1942",
  "links": [ { "url": "...", "label": "1", "page": 1, "active": false } ],
  "next_page_url": "...?page=2",
  "prev_page_url": null,
  "path": ".../pcontrole/api/jogadores",
  "per_page": 10,
  "to": 10,
  "total": 19415
}
```

**Objeto de jogador (lista)**

| campo | tipo | ex. / obs. |
|-------|------|-----------|
| `id` | int | `231747` (PK) |
| `nome` | str | `"(26) K. Mbappé"` (com prefixo de idade) |
| `passe` | str | `"475.200,00"` (valor de mercado, formato BR) |
| `posicao` | str | `"ATA"` |
| `overall` | int | `91` |
| `nacionalidade` | str | `"França"` |
| `nacionalidade_flag` | str (url) | bandeira |
| `nome_escudo` | str | `"Manchester United(KelvinAFC)"` — **clube da liga** |
| `link_escudo` | str (url) | escudo |
| `foto` | str (url) | foto do jogador |
| `usuario_id` | int\|null | dono na liga |
| `usuario_id_emprestimo` | int\|null | clube de empréstimo |
| `nome_escudo_emprestimo` | str | pode vir vazio |
| `link_escudo_emprestimo` | str | pode vir vazio |
| `meu_jogador` | bool | é seu |
| `multa` | int | multa rescisória |
| `bola` | obj | `{ "bola_id":1, "bola_nome":"Carta Azul", "bola_link":"..." }` |
| `inLeilao` | bool | em leilão |
| `a_venda` | bool | à venda |
| `valor_a_venda` | num\|null | preço se à venda |
| `favorito` | bool | favoritado |

Total atual: **19.415 jogadores** → **1.942 páginas**.

---

## `GET /pcontrole/api/jogadores/{id}` — detalhe (card FIFA)

Ficha técnica completa de um jogador. **1 requisição por jogador.**
Resposta: `{ "data": { ... } }`.

### Identidade e físico
| campo | ex. | obs. |
|-------|-----|------|
| `id` | `231747` | |
| `nome` / `nome_completo` | `"K. Mbappé"` / `"Kylian Mbappé Lottin"` | |
| **`time`** | `"Real Madrid"` | **time da vida real** (≠ `nome_escudo` da liga) |
| `overall` / `potencial` | `91` / `92` | |
| `idade` / `altura` / `peso` | `26` / `182` / `81` | cm, kg |
| `pe` | `"D"` | D/E |
| `posicao` / `posicao_id` | `"ATA"` / `14` | |
| `pos_ATA`, `pos_PE`, `pos_ME`, … | `0/1` | posições jogáveis (flags) |
| `skillmoves` / `pe_ruim` / `rep_internacional` | `5` / `4` / `5` | estrelas |
| `porte_fisico` | `"Unique"` | |
| `tipo_aceleracao` | `"Geralmente explosiva"` | |
| `face_real` | `1` | tem face real |
| `nacionalidade` / `pais_id` / `ddi` | `"França"` / `61` / `33` | |
| `foto` | url | |
| `nome_escudo` / `link_escudo` | `"Manchester United"` | clube da liga |
| `bola` | obj | carta |
| `slug` | `"k-mbappe"` | |

### Atributos (0–99)
`cruzamento, finalizacao, cabeceio, passe_curto, voleio` ·
`marcacao, roubada_bola, carrinho, interceptacoes` ·
`drible, curva, cobranca_falta, passe_longe, controle_bola` ·
`forca_chute, pulo, resistencia, forca, chute_longe` ·
`agressividade, posicionamento, visao_jogo, penalti, compostura` ·
`aceleracao, velocidade_final, agilidade, reacoes, equilibrio` ·
Goleiro: `salto, gk_habilidade_mao, gk_habilidade_pe, gk_posicionamento, gk_reflexo`

### Gráfico (radar)
`grafico_finalizacao, grafico_passe, grafico_drible, grafico_defesa,
grafico_fisico, grafico_velocidade`

### Características, Especialidades, Funções
- `C01`..`C82` — **características** (flags `0/1`). Nomes legíveis (pt-BR) em
  [jogadores/data/fifa_labels.py](jogadores/data/fifa_labels.py) → `CARACTERISTICAS`.
  Ex.: `C01 = "Chute colocado"`, `C06 = "Acrobata"`.
- `E01`..`E17` — **especialidades** (flags `0/1`). Mapa `ESPECIALIDADES`.
  Ex.: `E02 = "Velocista"`, `E14 = "Matador"`.
- `funcoes` — lista:
  `[{ "posicao":"ATA", "titulo":"Centroavante", "familiaridade":"++", ... }]`

### Campos NÃO usados por este projeto (ficam em `detalhe_raw`)
`passe` (valor de mercado), `sofifa_valor_usd`, `sofifa_salario_usd`,
`sofifa_rescisao_usd`, `gol_temporada`, `gol_carreira`,
`assistencia_temporada`, `assistencia_carreira`, `melhor_em_campo_carreira`.

---

## Outros endpoints observados (mesma base)

Vistos no bundle JS; não usados por este projeto:

- `GET /pcontrole/api/leiloes/jogadores?page=N` — jogadores em leilão (paginado).
- `GET /pcontrole/api/negociacao/historico?page=N` — histórico de negociações.
- `/pcontrole/api/negociacoes`, `/negociacoes/pendentes`, `/negociacoes/trocas`,
  `/negociacoes/historico` — fluxo de negociação (retornam a SPA no GET simples).
- `/pcontrole/api/jogadores-buscando-time` — jogadores sem time.

---

## Notas de uso

- Header `X-Requested-With: XMLHttpRequest` + `Accept: application/json`.
- Respeitar `Retry-After` no `429`; delay ~1,2 s entre chamadas.
- Formato de valores monetários: BR (`"475.200,00"`).
- É uma API interna/privada — uso restrito à sua conta autorizada; não
  redistribuir os dados.

*(Implementação de referência: [jogadores/services/arena_client.py](jogadores/services/arena_client.py).)*
