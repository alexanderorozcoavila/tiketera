from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, TemplateView
from django.contrib import messages
from .models import TicketType, Ticket
from django.http import JsonResponse, HttpResponseBadRequest
from events.models import Event, Favorite
from core.models import SiteSettings
import json

@login_required
def checkout(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    settings = SiteSettings.get_settings()
    
    if request.method == 'POST':
        # Recibir el carrito
        cart_json = request.POST.get('cart_json')
        if not cart_json:
            messages.error(request, "El carrito está vacío.")
            return redirect('event_detail', pk=event.id)
            
        try:
            cart = json.loads(cart_json)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid cart JSON")
            
        # Validar y cargar tickets
        cart_items = []
        total = 0
        for tt_id, qty in cart.items():
            qty = int(qty)
            if qty > 0:
                tt = get_object_or_404(TicketType, id=tt_id, event=event)
                if tt.quantity_available < qty:
                    messages.error(request, f"No hay suficientes boletos '{tt.name}'. Disponibles: {tt.quantity_available}")
                    return redirect('event_detail', pk=event.id)
                cart_items.append({'ticket_type': tt, 'qty': qty, 'subtotal': tt.price * qty})
                total += tt.price * qty
                
        if not cart_items:
            messages.error(request, "El carrito está vacío.")
            return redirect('event_detail', pk=event.id)
            
        # Guardar en sesión
        request.session['cart'] = cart
        request.session['checkout_event_id'] = event.id
        
        return render(request, 'tickets/buy_ticket_confirm.html', {
            'event': event,
            'cart_items': cart_items,
            'total': total,
        })
    else:
        # Si ya hay un cart en sesión, mostrar la página de confirmación, 
        # pero es mejor requerir el POST. Si es GET, redirigir al evento.
        return redirect('event_detail', pk=event.id)


@login_required
def process_payment(request):
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        # Validar cart en sesión
        cart = request.session.get('cart')
        if not cart:
            messages.error(request, "Tu sesión de compra ha expirado.")
            return redirect('/')
            
        if payment_method == 'webpay':
            return redirect('webpay_init')
        elif payment_method == 'crypto':
            return redirect('crypto_init')
        elif payment_method == 'mp':
            return redirect('mercadopago_init')
        else:
            messages.error(request, "Por favor seleccione un método de pago.")
            return redirect('/')
    
    return redirect('/')


@login_required
def ticket_success(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, buyer=request.user)
    return render(request, 'tickets/purchase_success.html', {'ticket': ticket})

#FAVORITOS FUNC
@login_required
def my_favorite(request):

    favorites = Favorite.objects.filter(
        user=request.user
    ).select_related(
        'event',
        'event__venue'
    )

    return render(request, 'tickets/my_favorite.html', {
        'favorites': favorites
    })

@login_required
def toggle_favorite(request):

    if request.method == 'POST':

        event_id = request.POST.get('event_id')

        event = get_object_or_404(Event, id=event_id)

        favorite = Favorite.objects.filter(
            user=request.user,
            event=event
        ).first()

        if favorite:

            favorite.delete()

            return JsonResponse({
                'status': 'removed'
            })

        else:

            Favorite.objects.create(
                user=request.user,
                event=event
            )

            return JsonResponse({
                'status': 'added'
            })

    return JsonResponse({
        'error': 'Invalid request'
    }, status=400)
class MyTicketsView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'tickets/my_tickets.html'
    context_object_name = 'tickets'

    def get_queryset(self):
        return Ticket.objects.filter(buyer=self.request.user).order_by('-purchase_date')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Verificar si hay un pago de MP pendiente de confirmar
        from payments.models import PendingMPPayment
        ctx['pending_mp_payment'] = PendingMPPayment.objects.filter(
            user=self.request.user, processed=False
        ).order_by('-created_at').first()
        return ctx


class TicketScannerView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'tickets/scanner.html'

    def test_func(self):
        return self.request.user.is_staff

@login_required
def download_ticket_pdf(request, ticket_id):
    import base64
    from io import BytesIO
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader

    if request.user.is_staff:
        ticket = get_object_or_404(Ticket, id=ticket_id)
    else:
        ticket = get_object_or_404(Ticket, id=ticket_id, buyer=request.user)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, height - 80, "Boleto Oficial - Tiketera")
    
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 120, f"Evento: {ticket.ticket_type.event.title}")
    p.drawString(50, height - 140, f"Ubicación: {ticket.ticket_type.event.venue.name}")
    p.drawString(50, height - 160, f"Comprador: {ticket.buyer.first_name} {ticket.buyer.last_name} ({ticket.buyer.email})")
    p.drawString(50, height - 180, f"Fecha de compra: {ticket.purchase_date.strftime('%Y-%m-%d %H:%M')}")
    p.drawString(50, height - 200, f"Tipo de Boleto: {ticket.ticket_type.name}")
    p.drawString(50, height - 220, f"ID de Boleto: {ticket.id}")
    
    qr_b64 = ticket.get_qr_base64()
    img_data = base64.b64decode(qr_b64)
    img_buffer = BytesIO(img_data)
    img = ImageReader(img_buffer)
    
    p.drawImage(img, 50, height - 450, width=200, height=200)

    p.showPage()
    p.save()
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="boleto_{ticket.id}.pdf"'
    return response
