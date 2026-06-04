from django.shortcuts import render
from django.views.generic import ListView, DetailView
from .models import Event


class EventListView(ListView):
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'

    def get_queryset(self):
        # eventos públicos
        return Event.objects.filter(
            is_published=True
        ).order_by('date_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # próximos eventos / ocultos
        context['upcoming_events'] = Event.objects.filter(
            is_published=False
        ).order_by('date_time')

        return context

class EventDetailView(DetailView):
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'
    
class AllFilterEventView(ListView):
    model = Event
    template_name = 'events/all_filter_event.html'
    context_object_name = 'events'

    def get_queryset(self):
        queryset = Event.objects.filter(
            is_published=True
        ).order_by('date_time')

        category = self.request.GET.get('category')
        search = self.request.GET.get('search')

        if category:
            queryset = queryset.filter(
                category__name__iexact=category
            )

        if search:
            queryset = queryset.filter(
                title__icontains=search
            )

        return queryset