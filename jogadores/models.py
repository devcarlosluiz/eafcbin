"""Acervo local dos jogadores.

Estes models são o *armazenamento*, alimentado pelos comandos de sincronização.
O painel de consulta não os usa — ele continua indo direto à API a cada busca.

Cada model guarda também o payload cru (`payload_lista` / `payload_detalhe`),
para que nenhum campo devolvido pela API se perca, mesmo os que ainda não foram
modelados em coluna.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from .data import fifa_labels


class JogadorQuerySet(models.QuerySet):
    def com_ficha(self):
        return self.select_related("detalhe")

    def sem_ficha(self):
        return self.filter(detalhe__isnull=True)

    def desatualizados_primeiro(self):
        """Fichas mais antigas na frente — base do rodízio diário."""
        return self.order_by(
            models.F("detalhe__verificado_em").asc(nulls_first=True), "-overall"
        )


class Jogador(models.Model):
    """Resumo de `GET /pcontrole/api/jogadores` (visão de mercado/liga)."""

    id = models.BigIntegerField(primary_key=True, verbose_name="ID")

    # `nome` chega como "(26) K. Mbappé": guardamos o original e o separado.
    nome_api = models.CharField("nome (bruto)", max_length=180)
    nome = models.CharField("nome", max_length=180, db_index=True)
    idade = models.PositiveSmallIntegerField("idade", null=True, blank=True)

    overall = models.PositiveSmallIntegerField("overall", default=0, db_index=True)
    posicao = models.CharField("posição", max_length=8, blank=True, db_index=True)

    passe = models.DecimalField(
        "valor de mercado", max_digits=16, decimal_places=2, default=Decimal("0")
    )
    multa = models.BigIntegerField("multa rescisória", default=0)

    nacionalidade = models.CharField("nacionalidade", max_length=80, blank=True, db_index=True)
    nacionalidade_flag = models.URLField("bandeira", max_length=500, blank=True)
    foto = models.URLField("foto", max_length=500, blank=True)

    # Clube dentro da liga — diferente de `detalhe.time` (clube da vida real).
    nome_escudo = models.CharField("clube na liga", max_length=180, blank=True, db_index=True)
    link_escudo = models.URLField("escudo", max_length=500, blank=True)
    usuario_id = models.BigIntegerField("dono na liga", null=True, blank=True, db_index=True)

    usuario_id_emprestimo = models.BigIntegerField("clube de empréstimo", null=True, blank=True)
    nome_escudo_emprestimo = models.CharField(max_length=180, blank=True)
    link_escudo_emprestimo = models.URLField(max_length=500, blank=True)

    bola_id = models.IntegerField("carta", null=True, blank=True)
    bola_nome = models.CharField("nome da carta", max_length=80, blank=True)
    bola_link = models.URLField("imagem da carta", max_length=500, blank=True)

    meu_jogador = models.BooleanField("é meu", default=False)
    favorito = models.BooleanField("favorito", default=False)
    in_leilao = models.BooleanField("em leilão", default=False, db_index=True)
    a_venda = models.BooleanField("à venda", default=False, db_index=True)
    valor_a_venda = models.DecimalField(
        "preço à venda", max_digits=16, decimal_places=2, null=True, blank=True
    )

    #: nome + nacionalidade + posição, minúsculo e sem acento. Existe porque o
    #: SQLite não faz busca sem acento em `icontains` — aqui a comparação é
    #: direta contra o termo já normalizado.
    busca_norm = models.CharField(max_length=400, blank=True, db_index=True)

    payload_lista = models.JSONField("payload da lista", default=dict, blank=True)

    criado_em = models.DateTimeField("visto pela primeira vez", auto_now_add=True)
    #: Toda vez que a API foi consultada para este jogador.
    verificado_em = models.DateTimeField("verificado em", db_index=True)
    #: Só quando algum campo realmente mudou.
    alterado_em = models.DateTimeField("alterado em", null=True, blank=True, db_index=True)
    #: Marcado quando o jogador some da listagem da API.
    ausente_desde = models.DateTimeField("ausente desde", null=True, blank=True)

    objects = JogadorQuerySet.as_manager()

    class Meta:
        verbose_name = "jogador"
        verbose_name_plural = "jogadores"
        ordering = ["-overall", "nome"]
        indexes = [
            models.Index(fields=["-overall", "nome"]),
            models.Index(fields=["posicao", "-overall"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.overall})"

    # As três propriedades abaixo espelham `dominio.Jogador`, para que o acervo
    # possa reusar os mesmos templates do painel ao vivo (card, detalhe).
    @property
    def url(self) -> str:
        return f"/players/local/{self.pk}/"

    @property
    def posicao_nome(self) -> str:
        return fifa_labels.nome_posicao(self.posicao)

    @property
    def setor(self) -> str:
        return fifa_labels.setor(self.posicao)

    @property
    def tem_ficha(self) -> bool:
        return hasattr(self, "detalhe")

    #: Alias — o card usa `tem_detalhe`, como no objeto do painel ao vivo.
    @property
    def tem_detalhe(self) -> bool:
        return self.tem_ficha


class JogadorDetalhe(models.Model):
    """Ficha técnica de `GET /pcontrole/api/jogadores/{id}`."""

    jogador = models.OneToOneField(
        Jogador, on_delete=models.CASCADE, related_name="detalhe", primary_key=True
    )

    nome_completo = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=200, blank=True)
    #: Clube da vida real — não confundir com `Jogador.nome_escudo`.
    time = models.CharField("time (vida real)", max_length=180, blank=True)
    potencial = models.PositiveSmallIntegerField(null=True, blank=True)
    altura = models.PositiveSmallIntegerField("altura (cm)", null=True, blank=True)
    peso = models.PositiveSmallIntegerField("peso (kg)", null=True, blank=True)
    pe = models.CharField("pé preferido", max_length=2, blank=True)
    posicao_id = models.IntegerField(null=True, blank=True)
    skillmoves = models.PositiveSmallIntegerField(null=True, blank=True)
    pe_ruim = models.PositiveSmallIntegerField(null=True, blank=True)
    rep_internacional = models.PositiveSmallIntegerField(null=True, blank=True)
    porte_fisico = models.CharField(max_length=60, blank=True)
    tipo_aceleracao = models.CharField(max_length=80, blank=True)
    face_real = models.BooleanField(default=False)
    pais_id = models.IntegerField(null=True, blank=True)
    ddi = models.CharField(max_length=8, blank=True)

    # Atributos de linha (0–99)
    cruzamento = models.PositiveSmallIntegerField(default=0)
    finalizacao = models.PositiveSmallIntegerField(default=0)
    cabeceio = models.PositiveSmallIntegerField(default=0)
    passe_curto = models.PositiveSmallIntegerField(default=0)
    voleio = models.PositiveSmallIntegerField(default=0)
    marcacao = models.PositiveSmallIntegerField(default=0)
    roubada_bola = models.PositiveSmallIntegerField(default=0)
    carrinho = models.PositiveSmallIntegerField(default=0)
    interceptacoes = models.PositiveSmallIntegerField(default=0)
    drible = models.PositiveSmallIntegerField(default=0)
    curva = models.PositiveSmallIntegerField(default=0)
    cobranca_falta = models.PositiveSmallIntegerField(default=0)
    passe_longe = models.PositiveSmallIntegerField(default=0)
    controle_bola = models.PositiveSmallIntegerField(default=0)
    forca_chute = models.PositiveSmallIntegerField(default=0)
    pulo = models.PositiveSmallIntegerField(default=0)
    resistencia = models.PositiveSmallIntegerField(default=0)
    forca = models.PositiveSmallIntegerField(default=0)
    chute_longe = models.PositiveSmallIntegerField(default=0)
    agressividade = models.PositiveSmallIntegerField(default=0)
    posicionamento = models.PositiveSmallIntegerField(default=0)
    visao_jogo = models.PositiveSmallIntegerField(default=0)
    penalti = models.PositiveSmallIntegerField(default=0)
    compostura = models.PositiveSmallIntegerField(default=0)
    aceleracao = models.PositiveSmallIntegerField(default=0)
    velocidade_final = models.PositiveSmallIntegerField(default=0)
    agilidade = models.PositiveSmallIntegerField(default=0)
    reacoes = models.PositiveSmallIntegerField(default=0)
    equilibrio = models.PositiveSmallIntegerField(default=0)

    # Goleiro
    salto = models.PositiveSmallIntegerField(default=0)
    gk_habilidade_mao = models.PositiveSmallIntegerField(default=0)
    gk_habilidade_pe = models.PositiveSmallIntegerField(default=0)
    gk_posicionamento = models.PositiveSmallIntegerField(default=0)
    gk_reflexo = models.PositiveSmallIntegerField(default=0)

    # Radar
    grafico_finalizacao = models.PositiveSmallIntegerField(default=0)
    grafico_passe = models.PositiveSmallIntegerField(default=0)
    grafico_drible = models.PositiveSmallIntegerField(default=0)
    grafico_defesa = models.PositiveSmallIntegerField(default=0)
    grafico_fisico = models.PositiveSmallIntegerField(default=0)
    grafico_velocidade = models.PositiveSmallIntegerField(default=0)

    # Listas e flags
    posicoes_jogaveis = models.JSONField(default=list, blank=True)   # ["ATA", "PE"]
    caracteristicas = models.JSONField(default=list, blank=True)     # ["C01", "C06"]
    especialidades = models.JSONField(default=list, blank=True)      # ["E02", "E14"]
    funcoes = models.JSONField(default=list, blank=True)

    payload_detalhe = models.JSONField(default=dict, blank=True)

    verificado_em = models.DateTimeField("verificado em", db_index=True)
    alterado_em = models.DateTimeField("alterado em", null=True, blank=True)

    class Meta:
        verbose_name = "ficha técnica"
        verbose_name_plural = "fichas técnicas"

    def __str__(self) -> str:
        return f"Ficha de {self.jogador_id}"

    # Propriedades de apresentação, iguais às de `dominio.Ficha` — os atributos
    # aqui moram em colunas, então `valor` lê via getattr.
    def valor(self, campo: str) -> int:
        return getattr(self, campo, 0) or 0

    @property
    def e_goleiro(self) -> bool:
        return (self.jogador.posicao or "").upper() == "GOL"

    @property
    def radar(self) -> list[dict]:
        return fifa_labels.montar_radar(self.valor)

    @property
    def grupos_atributos(self) -> list[dict]:
        return fifa_labels.montar_grupos(self.valor, self.e_goleiro)

    @property
    def caracteristicas_rotuladas(self) -> list[str]:
        return [fifa_labels.rotulo_caracteristica(c) for c in self.caracteristicas or []]

    @property
    def especialidades_rotuladas(self) -> list[str]:
        return [fifa_labels.rotulo_especialidade(e) for e in self.especialidades or []]


class Alteracao(models.Model):
    """Um campo que mudou de valor entre duas sincronizações."""

    ORIGEM = [("lista", "Lista"), ("detalhe", "Ficha técnica")]

    jogador = models.ForeignKey(
        Jogador, on_delete=models.CASCADE, related_name="alteracoes"
    )
    origem = models.CharField(max_length=10, choices=ORIGEM, default="lista")
    campo = models.CharField(max_length=60, db_index=True)
    de = models.TextField("valor anterior", blank=True)
    para = models.TextField("valor novo", blank=True)
    quando = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "alteração"
        verbose_name_plural = "alterações"
        ordering = ["-quando", "campo"]
        indexes = [models.Index(fields=["-quando", "jogador"])]

    def __str__(self) -> str:
        return f"{self.jogador_id}.{self.campo}: {self.de} → {self.para}"


class Execucao(models.Model):
    """Registro de cada rodada de sincronização."""

    TIPO = [("lista", "Lista"), ("detalhe", "Fichas técnicas")]
    SITUACAO = [
        ("rodando", "Rodando"),
        ("ok", "Concluída"),
        ("erro", "Falhou"),
        ("interrompida", "Interrompida"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO)
    situacao = models.CharField(max_length=14, choices=SITUACAO, default="rodando")
    iniciada_em = models.DateTimeField(auto_now_add=True, db_index=True)
    terminada_em = models.DateTimeField(null=True, blank=True)

    paginas = models.IntegerField("páginas lidas", default=0)
    criados = models.IntegerField(default=0)
    atualizados = models.IntegerField("com alteração", default=0)
    inalterados = models.IntegerField("sem alteração", default=0)
    campos_alterados = models.IntegerField(default=0)
    erros = models.IntegerField(default=0)
    mensagem = models.TextField(blank=True)

    class Meta:
        verbose_name = "execução"
        verbose_name_plural = "execuções"
        ordering = ["-iniciada_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.iniciada_em:%d/%m/%Y %H:%M}"

    @property
    def duracao_min(self) -> float:
        if not self.terminada_em:
            return 0.0
        return round((self.terminada_em - self.iniciada_em).total_seconds() / 60, 1)
