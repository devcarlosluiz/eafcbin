from django.urls import path

from . import views, views_local

app_name = "jogadores"

urlpatterns = [
    # Painel ao vivo (consulta direto na API)
    path("", views.consulta, name="consulta"),
    path("jogador/<int:pk>/", views.detalhe, name="detalhe"),
    path("api/sugestoes/", views.sugestoes, name="sugestoes"),
    path("saude/", views.saude, name="saude"),

    # Painel local (lê do acervo/banco)
    path("players/local/", views_local.players_local, name="players_local"),
    path("players/local/<int:pk>/", views_local.players_local_detalhe,
         name="players_local_detalhe"),
]
