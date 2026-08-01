from django.contrib import admin
from django.utils.html import format_html

from .models import Alteracao, Execucao, Jogador, JogadorDetalhe


class FichaInline(admin.StackedInline):
    model = JogadorDetalhe
    can_delete = False
    extra = 0
    readonly_fields = ("verificado_em", "alterado_em", "payload_detalhe")


class AlteracaoInline(admin.TabularInline):
    model = Alteracao
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = ("quando", "origem", "campo", "de", "para")
    ordering = ("-quando",)


@admin.register(Jogador)
class JogadorAdmin(admin.ModelAdmin):
    list_display = ("miniatura", "nome", "overall", "posicao", "nome_escudo",
                    "nacionalidade", "passe", "alterado_em", "verificado_em")
    list_display_links = ("miniatura", "nome")
    list_filter = ("posicao", "a_venda", "in_leilao", "meu_jogador", "favorito",
                   "bola_nome", "nacionalidade", "ausente_desde")
    search_fields = ("nome", "nome_api", "nome_escudo", "nacionalidade", "pk")
    ordering = ("-overall",)
    list_per_page = 50
    inlines = [FichaInline, AlteracaoInline]
    readonly_fields = ("criado_em", "verificado_em", "alterado_em", "payload_lista")

    @admin.display(description="")
    def miniatura(self, obj):
        if not obj.foto:
            return "—"
        return format_html('<img src="{}" style="height:34px;border-radius:6px">', obj.foto)


@admin.register(Alteracao)
class AlteracaoAdmin(admin.ModelAdmin):
    list_display = ("quando", "jogador", "origem", "campo", "de", "para")
    list_filter = ("origem", "campo", "quando")
    search_fields = ("jogador__nome", "campo")
    date_hierarchy = "quando"
    readonly_fields = [f.name for f in Alteracao._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(Execucao)
class ExecucaoAdmin(admin.ModelAdmin):
    list_display = ("iniciada_em", "tipo", "situacao", "duracao_min", "paginas",
                    "criados", "atualizados", "inalterados", "campos_alterados", "erros")
    list_filter = ("tipo", "situacao")
    date_hierarchy = "iniciada_em"
    readonly_fields = [f.name for f in Execucao._meta.fields]

    def has_add_permission(self, request):
        return False
