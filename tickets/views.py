from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.contrib import messages
from .models import TicketType, Ticket
from core.models import SiteSettings

@login_required
def buy_ticket(request, ticket_type_id):
    ticket_type = get_object_or_404(TicketType, id=ticket_type_id)
    settings = SiteSettings.get_settings()

    if request.method == 'POST':
        # Check quantities
        if ticket_type.quantity_available <= 0:
            messages.error(request, "Lo sentimos, los boletos están agotados.")
            return redirect('event_detail', pk=ticket_type.event.id)

        if settings.debug_bypass_payments:
            # Bypass payment entirely
            ticket = Ticket.objects.create(
                ticket_type=ticket_type,
                buyer=request.user
            )
            ticket_type.quantity_available -= 1
            ticket_type.save()
            messages.success(request, "¡Boleto generado exitosamente en modo Debug (Sin Pago)!")
            return redirect('ticket_success', ticket_id=ticket.id)
        
        # Payment flow logic
        payment_method = request.POST.get('payment_method')
        if payment_method == 'webpay':
            return redirect('webpay_init', ticket_type_id=ticket_type.id)
        elif payment_method == 'crypto':
            return redirect('crypto_init', ticket_type_id=ticket_type.id)
        else:
            messages.error(request, "Por favor seleccione un método de pago.")
            return redirect('buy_ticket', ticket_type_id=ticket_type.id)

    return render(request, 'tickets/buy_ticket_confirm.html', {'ticket_type': ticket_type})

@login_required
def ticket_success(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, buyer=request.user)
    return render(request, 'tickets/purchase_success.html', {'ticket': ticket})

class MyTicketsView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'tickets/my_tickets.html'
    context_object_name = 'tickets'

    def get_queryset(self):
        return Ticket.objects.filter(buyer=self.request.user).order_by('-purchase_date')
