"""Converte o JSON da API nos objetos de apresentação. Nada é persistido."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from ..dominio import Ficha, Jogador, Pagina

_RE_NOME_IDADE = re.compile(r"^\s*\((\d{1,2})\)\s*(.+)$")
_RE_FLAG_C = re.compile(r"^C\d{2,3}$")
_RE_FLAG_E = re.compile(r"^E\d{2,3}$")

#: Atributos numéricos do detalhe que o card usa (0–99).
ATRIBUTOS = [
    "cruzamento", "finalizacao", "cabeceio", "passe_curto", "voleio",
    "marcacao", "roubada_bola", "carrinho", "interceptacoes",
    "drible", "curva", "cobranca_falta", "passe_longe", "controle_bola",
    "forca_chute", "pulo", "resistencia", "forca", "chute_longe",
    "agressividade", "posicionamento", "visao_jogo", "penalti", "compostura",
    "aceleracao", "velocidade_final", "agilidade", "reacoes", "equilibrio",
    "salto", "gk_habilidade_mao", "gk_habilidade_pe", "gk_posicionamento",
    "gk_reflexo",
    "grafico_finalizacao", "grafico_passe", "grafico_drible",
    "grafico_defesa", "grafico_fisico", "grafico_velocidade",
]


# ---------------------------------------------------------------------------
# Conversores
# ---------------------------------------------------------------------------
def valor_br(valor: Any) -> Decimal:
    """Converte `"475.200,00"` (formato BR) para `Decimal("475200.00")`."""
    if valor in (None, "", "-"):
        return Decimal("0")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    texto = str(valor).strip().replace("R$", "").strip()
    if "," in texto:
        # Ponto é separador de milhar; vírgula é o decimal.
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        # Sem vírgula, pontos só são milhar se agruparem de 3 em 3.
        texto = texto.replace(".", "")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return Decimal("0")


def inteiro(valor: Any, padrao: int = 0) -> int:
    if valor in (None, "", False):
        return padrao
    try:
        return int(float(str(valor).replace(",", ".")))
    except (TypeError, ValueError):
        return padrao


def booleano(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in {"1", "true", "sim", "yes", "on"}


def separar_nome(nome_api: str) -> tuple[str, int | None]:
    """`"(26) K. Mbappé"` → `("K. Mbappé", 26)`."""
    achado = _RE_NOME_IDADE.match(nome_api or "")
    if achado:
        return achado.group(2).strip(), int(achado.group(1))
    return (nome_api or "").strip(), None


# ---------------------------------------------------------------------------
# Lista
# ---------------------------------------------------------------------------
def jogador(item: dict) -> Jogador:
    nome_api = item.get("nome") or ""
    nome, idade = separar_nome(nome_api)
    bola = item.get("bola") or {}
    venda = item.get("valor_a_venda")

    return Jogador(
        id=inteiro(item.get("id")),
        nome=nome,
        nome_api=nome_api,
        idade=idade,
        overall=inteiro(item.get("overall")),
        posicao=(item.get("posicao") or "").upper(),
        passe=valor_br(item.get("passe")),
        multa=inteiro(item.get("multa")),
        nacionalidade=item.get("nacionalidade") or "",
        nacionalidade_flag=item.get("nacionalidade_flag") or "",
        foto=item.get("foto") or "",
        nome_escudo=item.get("nome_escudo") or "",
        link_escudo=item.get("link_escudo") or "",
        usuario_id=item.get("usuario_id") or None,
        nome_escudo_emprestimo=item.get("nome_escudo_emprestimo") or "",
        link_escudo_emprestimo=item.get("link_escudo_emprestimo") or "",
        bola_nome=bola.get("bola_nome") or "",
        bola_link=bola.get("bola_link") or "",
        meu_jogador=booleano(item.get("meu_jogador")),
        favorito=booleano(item.get("favorito")),
        in_leilao=booleano(item.get("inLeilao")),
        a_venda=booleano(item.get("a_venda")),
        valor_a_venda=valor_br(venda) if venda not in (None, "") else None,
    )


def pagina(envelope: dict) -> Pagina:
    """Traduz o envelope de paginação padrão do Laravel."""
    return Pagina(
        numero=inteiro(envelope.get("current_page"), 1),
        ultima=inteiro(envelope.get("last_page"), 1),
        total=inteiro(envelope.get("total")),
        por_pagina=inteiro(envelope.get("per_page"), 10),
        jogadores=[jogador(i) for i in (envelope.get("data") or [])],
    )


# ---------------------------------------------------------------------------
# Detalhe
# ---------------------------------------------------------------------------
def _flags(dados: dict, padrao: re.Pattern) -> list[str]:
    """Flags marcadas (`C01..C82`, `E01..E17`).

    Varre as chaves em vez de percorrer um intervalo fixo: se o site passar a
    enviar códigos novos, eles aparecem no painel com o próprio código.
    """
    return sorted(
        chave for chave, valor in dados.items()
        if padrao.match(chave) and booleano(valor)
    )


def ficha(dados: dict) -> Ficha:
    return Ficha(
        nome_completo=dados.get("nome_completo") or "",
        slug=dados.get("slug") or "",
        time=dados.get("time") or "",
        potencial=inteiro(dados.get("potencial")) or None,
        altura=inteiro(dados.get("altura")) or None,
        peso=inteiro(dados.get("peso")) or None,
        pe=dados.get("pe") or "",
        skillmoves=inteiro(dados.get("skillmoves")) or None,
        pe_ruim=inteiro(dados.get("pe_ruim")) or None,
        rep_internacional=inteiro(dados.get("rep_internacional")) or None,
        porte_fisico=dados.get("porte_fisico") or "",
        tipo_aceleracao=dados.get("tipo_aceleracao") or "",
        face_real=booleano(dados.get("face_real")),
        posicao=(dados.get("posicao") or "").upper(),
        atributos={c: max(0, min(99, inteiro(dados.get(c)))) for c in ATRIBUTOS},
        posicoes_jogaveis=sorted(
            chave[4:] for chave, valor in dados.items()
            if chave.startswith("pos_") and booleano(valor)
        ),
        caracteristicas=_flags(dados, _RE_FLAG_C),
        especialidades=_flags(dados, _RE_FLAG_E),
        funcoes=dados.get("funcoes") or [],
    )


def jogador_completo(dados: dict) -> Jogador:
    """Monta um `Jogador` a partir do detalhe, já com a ficha anexada.

    O detalhe traz identidade e atributos, mas não os campos de mercado da liga
    (à venda, leilão, multa) — quem os tem é a lista.
    """
    alvo = jogador({
        "id": dados.get("id"),
        "nome": dados.get("nome"),
        "overall": dados.get("overall"),
        "posicao": dados.get("posicao"),
        "nacionalidade": dados.get("nacionalidade"),
        "nacionalidade_flag": dados.get("nacionalidade_flag"),
        "foto": dados.get("foto"),
        "nome_escudo": dados.get("nome_escudo"),
        "link_escudo": dados.get("link_escudo"),
        "passe": dados.get("passe"),
        "bola": dados.get("bola") or {},
    })
    if not alvo.idade:
        alvo.idade = inteiro(dados.get("idade")) or None
    alvo.detalhe = ficha(dados)
    return alvo


def mesclar(base: Jogador, completo: Jogador) -> Jogador:
    """Completa um jogador da lista com o que veio do detalhe."""
    base.detalhe = completo.detalhe
    base.idade = base.idade or completo.idade
    base.overall = completo.overall or base.overall
    base.posicao = completo.posicao or base.posicao
    base.foto = completo.foto or base.foto
    return base
