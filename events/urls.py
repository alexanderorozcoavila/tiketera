from django.urls import path
from .views import EventListView, EventListViewV2, EventDetailView, EventDetailView2

urlpatterns = [
    # Listas
    path('', EventListView.as_view(), name='event_list'),
    path('v2/', EventListViewV2.as_view(), name='event_listV2'),

    # Detalles
    path('evento/<int:pk>/', EventDetailView.as_view(), name='event_detail'),
    path('v2/evento/<int:pk>/', EventDetailView2.as_view(), name='event_detailV2'),
]