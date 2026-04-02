from django.urls import path
from .views import EventListView, EventDetailView, EventListViewV2

urlpatterns = [
    path('', EventListView.as_view(), name='event_list'),
    path('v2/', EventListViewV2.as_view(), name='event_listV2'),
    path('evento/<int:pk>/', EventDetailView.as_view(), name='event_detail'),
]
