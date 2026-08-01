"""Objetos de apresentação — vivem só durante a requisição.

Substituem os antigos models: nada aqui é gravado. O cliente da API devolve
JSON, o `parser` converte para estas dataclasses e o template renderiza.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .data import fifa_labels


@dataclass(slots=True)
class Ficha:
    """Ficha técnica de `GET /pcontrole/api/jogadores/{id}`."""

    nome_completo: str = ""
    slug: str = ""
    #: Clube da vida real — não confundir com `nome_escudo` (clube da liga).
    time: str = ""
    potencial: int | None = None
    altura: int | None = None
    peso: int | None = None
    pe: str = ""
    skillmoves: int | None = None
    pe_ruim: int | None = None
    rep_internacional: int | None = None
    porte_fisico: str = ""
    tipo_aceleracao: str = ""
    face_real: bool = False

    atributos: dict[str, int] = field(default_factory=dict)
    posicoes_jogaveis: list[str] = field(default_factory=list)
    caracteristicas: list[str] = field(default_factory=list)
    especialidades: list[str] = field(default_factory=list)
    funcoes: list[dict] = field(default_factory=list)

    #: Posição do jogador, para saber se mostra o bloco de goleiro.
    posicao: str = ""

    def valor(self, campo: str) -> int:
        return self.atributos.get(campo, 0)

    @property
    def e_goleiro(self) -> bool:
        return (self.posicao or "").upper() == "GOL"

    @property
    def radar(self) -> list[dict]:
        return fifa_labels.montar_radar(self.valor)

    @property
    def grupos_atributos(self) -> list[dict]:
        return fifa_labels.montar_grupos(self.valor, self.e_goleiro)

    @property
    def caracteristicas_rotuladas(self) -> list[str]:
        return [fifa_labels.rotulo_caracteristica(c) for c in self.caracteristicas]

    @property
    def especialidades_rotuladas(self) -> list[str]:
        return [fifa_labels.rotulo_especialidade(e) for e in self.especialidades]


@dataclass(slots=True)
class Jogador:
    """Jogador como vem de `GET /pcontrole/api/jogadores` (lista)."""

    id: int
    nome: str = ""
    nome_api: str = ""
    idade: int | None = None
    overall: int = 0
    posicao: str = ""
    passe: Decimal = Decimal("0")
    multa: int = 0
    nacionalidade: str = ""
    nacionalidade_flag: str = ""
    foto: str = ""
    nome_escudo: str = ""
    link_escudo: str = ""
    usuario_id: int | None = None
    nome_escudo_emprestimo: str = ""
    link_escudo_emprestimo: str = ""
    bola_nome: str = ""
    bola_link: str = ""
    meu_jogador: bool = False
    favorito: bool = False
    in_leilao: bool = False
    a_venda: bool = False
    valor_a_venda: Decimal | None = None

    #: Preenchida só na tela de detalhe (uma requisição a mais por jogador).
    detalhe: Ficha | None = None

    @property
    def url(self) -> str:
        return f"/jogador/{self.id}/"

    @property
    def posicao_nome(self) -> str:
        return fifa_labels.nome_posicao(self.posicao)

    @property
    def setor(self) -> str:
        return fifa_labels.setor(self.posicao)

    @property
    def livre(self) -> bool:
        return self.usuario_id is None

    @property
    def tem_detalhe(self) -> bool:
        return self.detalhe is not None


@dataclass(slots=True)
class Pagina:
    """Envelope de paginação do Laravel, já traduzido."""

    numero: int = 1
    ultima: int = 1
    total: int = 0
    por_pagina: int = 10
    jogadores: list[Jogador] = field(default_factory=list)

    @property
    def tem_anterior(self) -> bool:
        return self.numero > 1

    @property
    def tem_proxima(self) -> bool:
        return self.numero < self.ultima

    @property
    def anterior(self) -> int:
        return max(1, self.numero - 1)

    @property
    def proxima(self) -> int:
        return min(self.ultima, self.numero + 1)

    @property
    def intervalo(self) -> list[int | str]:
        """Números de página ao redor do atual, com reticências nas bordas."""
        if self.ultima <= 9:
            return list(range(1, self.ultima + 1))
        paginas: list[int | str] = [1]
        inicio, fim = max(2, self.numero - 2), min(self.ultima - 1, self.numero + 2)
        if inicio > 2:
            paginas.append("…")
        paginas.extend(range(inicio, fim + 1))
        if fim < self.ultima - 1:
            paginas.append("…")
        paginas.append(self.ultima)
        return paginas
