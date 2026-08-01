# API externa — acervo de jogadores

Documentação da API **própria deste projeto**, para consumo pelo painel de
campeonatos de liga virtual (ou qualquer outro consumidor externo). Devolve os
jogadores do acervo (banco local), já sincronizados a partir da API interna do
Arena Virtual (ver [api.MD](api.MD)).

Implementação: [jogadores/api/](jogadores/api/) (Django REST Framework).

- **Base:** `/api/v1/`
- **Formato:** JSON
- **Somente leitura** (`GET`)
- **Autenticação:** header `X-API-Key`

---

## Autenticação

Toda requisição precisa do header:

```
X-API-Key: <token>
```

As chaves são cadastradas no **admin do Django**, em
**Jogadores → Chaves de API externa**: cada registro tem um `nome` (para
identificar quem está usando, ex.: "Painel de Campeonatos X") e um `token`,
gerado sozinho ao salvar — não dá para digitar o token, só copiar o que foi
gerado. Um checkbox `ativa` permite suspender o acesso de um consumidor sem
excluir o registro (e sem afetar as outras chaves).

Sem o header, com um token que não existe, ou com uma chave desativada, a API
devolve:

```
HTTP 403 Forbidden
{ "detail": "Chave de API ausente ou inválida (header X-API-Key)." }
```

---

## `GET /api/v1/jogadores/` — lista paginada

Lista o acervo, com os mesmos filtros e ordenações do painel local
(`jogadores/filtros_local.py`).

### Query params

| param | tipo | obs. |
|-------|------|------|
| `q` | str | busca por nome/nacionalidade/posição (sem acento) ou nome completo/time (via ficha) |
| `posicao` | str | ex.: `ATA`, `ZAG`, `MEI`, `GOL`, `VOL` |
| `nacionalidade` | str | valor exato, ex.: `Brasil` |
| `overall_min` / `overall_max` | int | 0–99 |
| `situacao` | str | `meus`, `a_venda`, `leilao`, `favoritos`, `livres`, `com_ficha`, `ausentes` |
| `ordenar` | str | `overall` (padrão), `overall_asc`, `idade`, `idade_asc`, `nome`, `multa`, `recentes` |
| `page` | int | página (padrão `1`) |
| `page_size` | int | itens por página (padrão `50`, máx. `200`) |

### Exemplo

```bash
curl "https://SEU-DOMINIO/api/v1/jogadores/?posicao=ATA&overall_min=85&ordenar=overall" \
  -H "X-API-Key: SUA_CHAVE"
```

### Resposta — envelope de paginação (padrão DRF)

```jsonc
{
  "count": 132,
  "next": "https://SEU-DOMINIO/api/v1/jogadores/?page=2&posicao=ATA...",
  "previous": null,
  "results": [ /* jogadores — mesmo formato do detalhe, ver abaixo */ ]
}
```

Cada item de `results` tem o **mesmo formato completo** do endpoint de
detalhe (ver abaixo) — inclusive a ficha técnica (`detalhe`), quando o
jogador já tiver sido sincronizada.

---

## `GET /api/v1/jogadores/{id}/` — jogador completo

Devolve todos os dados de um jogador: os campos do resumo (lista/mercado) e,
quando disponível, a ficha técnica completa (atributos, radar, características
e especialidades já com nome legível).

### Exemplo

```bash
curl "https://SEU-DOMINIO/api/v1/jogadores/231747/" \
  -H "X-API-Key: SUA_CHAVE"
```

`404` se o `id` não existir no acervo.

### Resposta — campos do jogador (resumo)

| campo | tipo | obs. |
|-------|------|------|
| `id` | int | PK |
| `nome` | str | nome, sem o prefixo de idade |
| `nome_api` | str | nome bruto, como veio da API (`"(26) K. Mbappé"`) |
| `idade` | int\|null | |
| `overall` | int | |
| `posicao` | str | sigla (`"ATA"`) |
| `posicao_nome` | str | nome legível (`"Atacante"`) |
| `setor` | str | `"ataque"` / `"meio"` / `"defesa"` / `"goleiro"` |
| `multa` | int | multa rescisória |
| `nacionalidade` | str | |
| `nacionalidade_flag` | str (url) | |
| `foto` | str (url) | |
| `usuario_id` | int\|null | dono na liga |
| `usuario_id_emprestimo` | int\|null | clube de empréstimo |
| `nome_escudo_emprestimo` / `link_escudo_emprestimo` | str | podem vir vazios |
| `bola_id` / `bola_nome` / `bola_link` | int/str/str | carta |
| `meu_jogador` / `favorito` / `in_leilao` / `a_venda` | bool | |
| `valor_a_venda` | num\|null | |
| `tem_ficha` | bool | se `detalhe` vem preenchido |
| `payload_lista` | obj | payload cru da API interna, sem perder nenhum campo |
| `criado_em` | datetime | visto pela 1ª vez no acervo |
| `verificado_em` | datetime | última sincronização |
| `alterado_em` | datetime\|null | última mudança real de algum campo |
| `ausente_desde` | datetime\|null | preenchido quando some da API interna |
| `detalhe` | obj\|null | ficha técnica — ver abaixo |

### Resposta — `detalhe` (ficha técnica, quando `tem_ficha=true`)

| campo | tipo | obs. |
|-------|------|------|
| `nome_completo` | str | |
| `slug` | str | |
| `time` | str | clube **da vida real** (≠ clube da liga) |
| `potencial` | int | |
| `altura` / `peso` | int | cm / kg |
| `pe` | str | `"D"` / `"E"` |
| `posicao_id` | int | |
| `skillmoves` / `pe_ruim` / `rep_internacional` | int | estrelas |
| `porte_fisico` / `tipo_aceleracao` | str | |
| `face_real` | bool | |
| `pais_id` / `ddi` | int/str | |
| *atributos (0–99)* | int | `cruzamento`, `finalizacao`, `cabeceio`, `passe_curto`, `voleio`, `marcacao`, `roubada_bola`, `carrinho`, `interceptacoes`, `drible`, `curva`, `cobranca_falta`, `passe_longe`, `controle_bola`, `forca_chute`, `pulo`, `resistencia`, `forca`, `chute_longe`, `agressividade`, `posicionamento`, `visao_jogo`, `penalti`, `compostura`, `aceleracao`, `velocidade_final`, `agilidade`, `reacoes`, `equilibrio` |
| *goleiro (0–99)* | int | `salto`, `gk_habilidade_mao`, `gk_habilidade_pe`, `gk_posicionamento`, `gk_reflexo` |
| *radar (0–99)* | int | `grafico_finalizacao`, `grafico_passe`, `grafico_drible`, `grafico_defesa`, `grafico_fisico`, `grafico_velocidade` |
| `radar` | list[obj] | os 6 valores de radar já traduzidos: `{ "sigla", "rotulo", "valor" }` |
| `grupos_atributos` | list[obj] | atributos agrupados por categoria (Ataque, Habilidade, Movimento, Potência, Mentalidade, Defesa), cada um com `itens` (`rotulo`/`valor`) e `media` |
| `posicoes_jogaveis` | list[str] | ex.: `["ATA", "PE"]` |
| `caracteristicas` | list[str] | códigos brutos (`C01`..`C82`) |
| `caracteristicas_rotuladas` | list[str] | nomes legíveis (`"Chute colocado"`, `"Acrobata"`, ...) |
| `especialidades` | list[str] | códigos brutos (`E01`..`E17`) |
| `especialidades_rotuladas` | list[str] | nomes legíveis (`"Velocista"`, `"Matador"`, ...) |
| `funcoes` | list[obj] | `[{ "posicao", "titulo", "familiaridade" }]` |
| `payload_detalhe` | obj | payload cru da ficha técnica, sem perder nenhum campo |
| `verificado_em` / `alterado_em` | datetime | |

### Exemplo de resposta (resumida)

```jsonc
{
  "id": 231747,
  "nome": "K. Mbappé",
  "posicao": "ATA",
  "posicao_nome": "Atacante",
  "setor": "ataque",
  "overall": 91,
  "tem_ficha": true,
  "usuario_id": 100236,
  "meu_jogador": false,
  "a_venda": false,
  "detalhe": {
    "nome_completo": "Kylian Mbappé Lottin",
    "time": "Real Madrid",
    "potencial": 92,
    "altura": 182,
    "peso": 81,
    "finalizacao": 91,
    "aceleracao": 97,
    "radar": [
      { "sigla": "RIT", "rotulo": "Ritmo", "valor": 97 },
      { "sigla": "FIN", "rotulo": "Finalização", "valor": 91 }
    ],
    "caracteristicas_rotuladas": ["Chute colocado", "Acrobata"],
    "especialidades_rotuladas": ["Velocista", "Matador"],
    "funcoes": [{ "posicao": "ATA", "titulo": "Centroavante", "familiaridade": "++" }]
  },
  "payload_lista": { "...": "..." }
}
```

---

## Erros

| status | quando |
|--------|--------|
| `403` | header `X-API-Key` ausente, com um token inexistente, ou de uma chave desativada |
| `404` | jogador com esse `id` não existe no acervo |

---

## Notas

- A API só lê o **acervo local** (banco). Jogadores ainda não sincronizados
  não aparecem — a cobertura depende da rotina diária (ver `README.md` /
  `SINCRONIZACAO` em `config/settings.py`).
- `tem_ficha=false` → `detalhe` vem `null` (jogador com resumo sincronizado,
  mas sem ficha técnica ainda).
- Não redistribuir os dados fora do painel de campeonatos autorizado — a
  origem (`api.MD`) é uma API privada de terceiros.
