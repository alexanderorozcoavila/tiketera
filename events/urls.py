from django.urls import path
from .views import EventListView, EventDetailView, AllFilterEventView, help_view, enviar_consulta

urlpatterns = [
    path('', EventListView.as_view(), name='event_list'),
    path('evento/<int:pk>/', EventDetailView.as_view(), name='event_detail'),
    
    #EVENTOS FILTRADOS
    path('eventos/', AllFilterEventView.as_view(), name='all_filter_event'),
    
    #AYUDA
    path('help/', help_view, name='help'),
    path('help/enviar/', enviar_consulta, name='enviar_consulta'),
]
