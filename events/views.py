from django.shortcuts import render
from django.views.generic import ListView, DetailView
from .models import Event

class EventListView(ListView):
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'

    def get_queryset(self):
        return Event.objects.filter(is_published=True).order_by('date_time')
# DISEÑO
class EventListViewV2(ListView):
    model = Event
    template_name = 'events/event_listV2.html'
    context_object_name = 'events'

    def get_queryset(self):
        return Event.objects.filter(is_published=True).order_by('date_time')

class EventDetailView(DetailView):
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'

class EventDetailView2(DetailView):
    model = Event
    template_name = 'events/event_detailV2.html'
    context_object_name = 'event'
