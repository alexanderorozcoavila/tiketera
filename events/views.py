from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView
from .models import Event

#FORMULARIO DE AYUDA
from django.core.mail import EmailMessage
from django.contrib import messages
from django.shortcuts import redirect
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
        region = self.request.GET.get('region')  # 👈 NUEVO

        if category:
            queryset = queryset.filter(
                category__name__iexact=category
            )

        if search:
            queryset = queryset.filter(
                title__icontains=search
            )

        if region:
            queryset = queryset.filter(
                venue__name__iexact=region
            )
            
        return queryset
    
    
    
# ==========================
# CENTRO DE AYUDA
# ==========================

def help_view(request):
    return render(request, 'events/help.html')

def enviar_consulta(request):
    if request.method == "POST":
        nombre = request.POST.get('nombre')
        correo = request.POST.get('correo')
        telefono = request.POST.get('telefono')
        mensaje = request.POST.get('mensaje')

        cuerpo = f"""
Nueva consulta desde FastiTicket

Nombre: {nombre}
Correo: {correo}
Teléfono: {telefono}

Mensaje:
{mensaje}
"""

        email = EmailMessage(
            subject=f"[FASTITICKET] Consulta de {nombre}",
            body=cuerpo,
            from_email='serviciostecnologicoscupo@gmail.com',
            to=['serviciostecnologicoscupo@gmail.com'],
            reply_to=[correo]
        )

        try:
            email.send()
            messages.success(request, 'Consulta enviada correctamente ⚡')
        except Exception as e:
            print(f"Error al enviar email: {e}")
            messages.error(request, 'No fue posible enviar la consulta.')

    return redirect('help')