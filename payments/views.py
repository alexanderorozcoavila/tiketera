from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_type import IntegrationType
from transbank.error.transbank_error import TransbankError
from tickets.models import TicketType, Ticket
from django.contrib import messages
from core.models import SiteSettings
import uuid

def get_transaction_handler():
    options = WebpayOptions(
        commerce_code=IntegrationCommerceCodes.WEBPAY_PLUS,
        api_key=IntegrationApiKeys.WEBPAY,
        integration_type=IntegrationType.TEST
    )
    return Transaction(options)

@login_required
def webpay_init(request, ticket_type_id):
    ticket_type = get_object_or_404(TicketType, id=ticket_type_id)
    if ticket_type.quantity_available <= 0:
        messages.error(request, "Boletos agotados.")
        return redirect('event_detail', pk=ticket_type.event.id)
    
    buy_order = str(uuid.uuid4())[:25]
    session_id = str(request.user.id)
    amount = int(ticket_type.price)
    return_url = request.build_absolute_uri('/payments/webpay/return/')

    try:
        tx = get_transaction_handler()
        response = tx.create(buy_order, session_id, amount, return_url)
        request.session['pending_ticket_type_id'] = ticket_type.id
        return render(request, 'payments/webpay_redirect.html', {'response': response})
    except TransbankError as e:
        messages.error(request, f"Error al inicializar Webpay.")
        return redirect('event_detail', pk=ticket_type.event.id)

@login_required
def webpay_return(request):
    token = request.GET.get('token_ws') or request.POST.get('token_ws')
    if not token:
        messages.error(request, "Pago cancelado o token no recibido.")
        return redirect('/')

    try:
        tx = get_transaction_handler()
        response = tx.commit(token)
        if response.get('status') == 'AUTHORIZED':
            ticket_type_id = request.session.get('pending_ticket_type_id')
            if ticket_type_id:
                ticket_type = TicketType.objects.get(id=ticket_type_id)
                ticket = Ticket.objects.create(ticket_type=ticket_type, buyer=request.user)
                ticket_type.quantity_available -= 1
                ticket_type.save()
                messages.success(request, "Pago exitoso con Webpay Plus.")
                return redirect('ticket_success', ticket_id=ticket.id)
        messages.error(request, "El pago ha sido rechazado.")
        return redirect('/')
    except TransbankError as e:
        messages.error(request, f"Error en transacción (abortada).")
        return redirect('/')

@login_required
def crypto_init(request, ticket_type_id):
    ticket_type = get_object_or_404(TicketType, id=ticket_type_id)
    if ticket_type.quantity_available <= 0:
        messages.error(request, "Boletos agotados.")
        return redirect('event_detail', pk=ticket_type.event.id)
    
    request.session['pending_ticket_type_id'] = ticket_type.id
    return render(request, 'payments/crypto_payment.html', {'ticket_type': ticket_type})

@login_required
def crypto_success(request):
    import random
    if random.choice([True, True, False]):
        ticket_type_id = request.session.get('pending_ticket_type_id')
        if ticket_type_id:
            ticket_type = TicketType.objects.get(id=ticket_type_id)
            ticket = Ticket.objects.create(ticket_type=ticket_type, buyer=request.user)
            ticket_type.quantity_available -= 1
            ticket_type.save()
            messages.success(request, "Pago en Criptomonedas confirmado en la red.")
            return redirect('ticket_success', ticket_id=ticket.id)
    messages.error(request, "Pago en cripto no detectado o fallido.")
    return redirect('/')
