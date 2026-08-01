from django.urls import path

from . import views

app_name = "jogadores_api"

urlpatterns = [
    path("jogadores/", views.JogadorListaAPIView.as_view(), name="lista"),
    path("jogadores/<int:pk>/", views.JogadorDetalheAPIView.as_view(), name="detalhe"),
]
