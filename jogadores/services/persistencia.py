"""Grava os payloads da API no acervo, registrando o que mudou.

Uma sincronização não sobrescreve cegamente: compara campo a campo com o que já
está no banco, grava só quando há diferença e registra cada mudança em
`Alteracao`. Assim o "atualizar caso tenha modificação" fica auditável.

O payload cru é sempre regravado (`payload_lista` / `payload_detalhe`), mesmo
sem mudança nos campos modelados — é a rede de segurança para campos que a API
devolve e que ainda não viraram coluna.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..models import Alteracao, Jogador, JogadorDetalhe
from .parser import booleano, inteiro, separar_nome, valor_br
from .parser import ATRIBUTOS, ficha as ficha_do_payload


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento — base da busca sem acento no acervo."""
    base = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in base if not unicodedata.combining(c)).casefold()

#: Resultado possível de gravar um registro.
CRIADO, ALTERADO, IGUAL = "criado", "alterado", "igual"

#: Campos que nunca entram na comparação (são metadados ou espelho do payload).
IGNORADOS = {
    "payload_lista", "payload_detalhe", "criado_em", "verificado_em",
    "alterado_em", "ausente_desde", "jogador", "jogador_id", "id",
    # derivado de nome/nacionalidade/posição — muda junto com eles, não sozinho.
    "busca_norm",
}


def campos_da_lista(item: dict) -> dict:
    """Payload de `/jogadores` → colunas de `Jogador`."""
    nome_api = item.get("nome") or ""
    nome, idade = separar_nome(nome_api)
    bola = item.get("bola") or {}
    venda = item.get("valor_a_venda")
    nacionalidade = (item.get("nacionalidade") or "")[:80]
    posicao = (item.get("posicao") or "").upper()[:8]

    return {
        "nome_api": nome_api[:180],
        "nome": nome[:180],
        "idade": idade,
        "busca_norm": normalizar(f"{nome} {nacionalidade} {posicao}")[:400],
        "overall": inteiro(item.get("overall")),
        "posicao": posicao,
        "multa": inteiro(item.get("multa")),
        "nacionalidade": nacionalidade,
        "nacionalidade_flag": (item.get("nacionalidade_flag") or "")[:500],
        "foto": (item.get("foto") or "")[:500],
        # time da liga (nome_escudo/link_escudo) e valor de mercado (passe) não
        # entram no acervo, de propósito.
        "usuario_id": item.get("usuario_id") or None,
        "usuario_id_emprestimo": item.get("usuario_id_emprestimo") or None,
        "nome_escudo_emprestimo": (item.get("nome_escudo_emprestimo") or "")[:180],
        "link_escudo_emprestimo": (item.get("link_escudo_emprestimo") or "")[:500],
        "bola_id": bola.get("bola_id"),
        "bola_nome": (bola.get("bola_nome") or "")[:80],
        "bola_link": (bola.get("bola_link") or "")[:500],
        "meu_jogador": booleano(item.get("meu_jogador")),
        "favorito": booleano(item.get("favorito")),
        "in_leilao": booleano(item.get("inLeilao")),
        "a_venda": booleano(item.get("a_venda")),
        "valor_a_venda": valor_br(venda) if venda not in (None, "") else None,
    }


def campos_do_detalhe(dados: dict) -> dict:
    """Payload de `/jogadores/{id}` → colunas de `JogadorDetalhe`.

    Aproveita o mesmo extrator usado pelo painel (`parser.ficha`), para que
    acervo e tela leiam o payload exatamente da mesma forma.
    """
    ficha = ficha_do_payload(dados)
    campos: dict[str, Any] = {
        "nome_completo": ficha.nome_completo[:200],
        "slug": ficha.slug[:200],
        "time": ficha.time[:180],
        "potencial": ficha.potencial,
        "altura": ficha.altura,
        "peso": ficha.peso,
        "pe": ficha.pe[:2],
        "skillmoves": ficha.skillmoves,
        "pe_ruim": ficha.pe_ruim,
        "rep_internacional": ficha.rep_internacional,
        "porte_fisico": ficha.porte_fisico[:60],
        "tipo_aceleracao": ficha.tipo_aceleracao[:80],
        "face_real": ficha.face_real,
        "posicoes_jogaveis": ficha.posicoes_jogaveis,
        "caracteristicas": ficha.caracteristicas,
        "especialidades": ficha.especialidades,
        "funcoes": ficha.funcoes,
        # Campos que a tela não usa, mas o acervo guarda.
        "posicao_id": dados.get("posicao_id"),
        "pais_id": dados.get("pais_id"),
        "ddi": str(dados.get("ddi") or "")[:8],
    }
    campos.update({atributo: ficha.valor(atributo) for atributo in ATRIBUTOS})
    return campos


def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor)


def _diferencas(instancia, novos: dict) -> list[tuple[str, Any, Any]]:
    """Campos cujo valor no banco difere do que a API acabou de devolver."""
    mudancas = []
    for campo, novo in novos.items():
        if campo in IGNORADOS:
            continue
        atual = getattr(instancia, campo, None)
        if atual != novo:
            mudancas.append((campo, atual, novo))
    return mudancas


def _registrar(jogador_id: int, origem: str, mudancas, agora) -> None:
    Alteracao.objects.bulk_create([
        Alteracao(
            jogador_id=jogador_id, origem=origem, campo=campo,
            de=_texto(antes)[:2000], para=_texto(depois)[:2000], quando=agora,
        )
        for campo, antes, depois in mudancas
    ])


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------
@transaction.atomic
def salvar_jogador(item: dict, agora=None) -> tuple[str, int]:
    """Grava um item da lista. Devolve `(situação, nº de campos alterados)`."""
    jogador_id = inteiro(item.get("id"))
    if not jogador_id:
        return IGUAL, 0

    agora = agora or timezone.now()
    novos = campos_da_lista(item)

    existente = Jogador.objects.filter(pk=jogador_id).first()
    if existente is None:
        Jogador.objects.create(
            pk=jogador_id, payload_lista=item, verificado_em=agora,
            alterado_em=agora, **novos,
        )
        return CRIADO, len(novos)

    mudancas = _diferencas(existente, novos)
    for campo, _, novo in mudancas:
        setattr(existente, campo, novo)
    existente.payload_lista = item
    existente.verificado_em = agora
    existente.ausente_desde = None
    if mudancas:
        existente.alterado_em = agora
    existente.save()

    if mudancas:
        _registrar(jogador_id, "lista", mudancas, agora)
        return ALTERADO, len(mudancas)
    return IGUAL, 0


@transaction.atomic
def salvar_ficha(jogador_id: int, dados: dict, agora=None) -> tuple[str, int]:
    """Grava a ficha técnica. Devolve `(situação, nº de campos alterados)`."""
    agora = agora or timezone.now()
    novos = campos_do_detalhe(dados)

    existente = JogadorDetalhe.objects.filter(jogador_id=jogador_id).first()
    if existente is None:
        JogadorDetalhe.objects.create(
            jogador_id=jogador_id, payload_detalhe=dados,
            verificado_em=agora, alterado_em=agora, **novos,
        )
        situacao, quantidade = CRIADO, len(novos)
    else:
        mudancas = _diferencas(existente, novos)
        for campo, _, novo in mudancas:
            setattr(existente, campo, novo)
        existente.payload_detalhe = dados
        existente.verificado_em = agora
        if mudancas:
            existente.alterado_em = agora
        existente.save()

        if mudancas:
            _registrar(jogador_id, "detalhe", mudancas, agora)
            situacao, quantidade = ALTERADO, len(mudancas)
        else:
            situacao, quantidade = IGUAL, 0

    # O detalhe é a fonte mais confiável para overall/posição/idade.
    espelho = {
        campo: valor for campo, valor in (
            ("overall", inteiro(dados.get("overall"))),
            ("posicao", (dados.get("posicao") or "").upper()[:8]),
            ("idade", inteiro(dados.get("idade")) or None),
        ) if valor
    }
    if espelho:
        Jogador.objects.filter(pk=jogador_id).update(**espelho)

    return situacao, quantidade


def marcar_ausentes(vistos: set[int], agora=None) -> int:
    """Sinaliza quem não apareceu na varredura — sem apagar nada do acervo."""
    agora = agora or timezone.now()
    return (
        Jogador.objects.filter(ausente_desde__isnull=True)
        .exclude(pk__in=vistos)
        .update(ausente_desde=agora)
    )
