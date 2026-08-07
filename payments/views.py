from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_type import IntegrationType
from transbank.error.transbank_error import TransbankError
from tickets.models import TicketType, Ticket
from payments.models import PendingMPPayment, Transaction, TransactionDetail, PaymentMethod
from django.contrib import messages
from core.models import SiteSettings
import uuid
import logging
import json
import mercadopago
from django.conf import settings as django_settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse

logger = logging.getLogger(__name__)


# =====================================================================
# WEBPAY PLUS (sin cambios)
# =====================================================================

def get_transaction_handler():
    options = WebpayOptions(
        commerce_code=IntegrationCommerceCodes.WEBPAY_PLUS,
        api_key=IntegrationApiKeys.WEBPAY,
        integration_type=IntegrationType.TEST
    )
    return Transaction(options)


@login_required
def webpay_init(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "El carrito está vacío.")
        return redirect('/')

    amount = 0
    for tt_id, qty in cart.items():
        qty = int(qty)
        if qty > 0:
            tt = get_object_or_404(TicketType, id=tt_id)
            if tt.quantity_available < qty:
                messages.error(request, f"Boletos agotados para {tt.name}.")
                return redirect('event_detail', pk=tt.event.id)
            amount += int(tt.price) * qty

    buy_order = str(uuid.uuid4())[:25]
    session_id = str(request.user.id)
    return_url = request.build_absolute_uri('/payments/webpay/return/')

    try:
        tx = get_transaction_handler()
        response = tx.create(buy_order, session_id, amount, return_url)
        return render(request, 'payments/webpay_redirect.html', {'response': response})
    except TransbankError:
        messages.error(request, "Error al inicializar Webpay.")
        return redirect('/')


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
            cart = request.session.get('cart', {})
            if cart:
                pm, _ = PaymentMethod.objects.get_or_create(name='Webpay Plus')
                # Calcular total
                total_amount = sum(TicketType.objects.get(id=tt_id).price * int(qty) for tt_id, qty in cart.items() if int(qty) > 0)
                
                # Crear transacción
                transaction = Transaction.objects.create(
                    user=request.user,
                    payment_method=pm,
                    amount=total_amount,
                    status='COMPLETED'
                )

                created_tickets = []
                for tt_id, qty in cart.items():
                    qty = int(qty)
                    if qty > 0:
                        tt = TicketType.objects.get(id=tt_id)
                        # Crear Detalle de Transacción
                        TransactionDetail.objects.create(
                            transaction=transaction,
                            ticket_type=tt,
                            quantity=qty,
                            price=tt.price
                        )
                        # Crear Tickets físicos
                        for _ in range(qty):
                            ticket = Ticket.objects.create(ticket_type=tt, buyer=request.user, transaction=transaction)
                            created_tickets.append(ticket)
                        
                        tt.quantity_available -= qty
                        tt.save()
                
                request.session.pop('cart', None)
                request.session.pop('checkout_event_id', None)
                messages.success(request, "Pago exitoso con Webpay Plus.")
                if created_tickets:
                    return redirect('ticket_success', ticket_id=created_tickets[0].id)
                else:
                    return redirect('my_tickets')

        messages.error(request, "El pago ha sido rechazado.")
        return redirect('/')
    except TransbankError:
        messages.error(request, "Error en transacción (abortada).")
        return redirect('/')


# =====================================================================
# CRYPTO / WEB3 (sin cambios)
# =====================================================================

@login_required
def crypto_init(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "El carrito está vacío.")
        return redirect('/')

    # Solo para renderizar algo relacionado al evento (asumimos el primer ticket_type)
    first_tt = None
    for tt_id, qty in cart.items():
        if int(qty) > 0:
            first_tt = TicketType.objects.get(id=tt_id)
            break
            
    if not first_tt:
        return redirect('/')
        
    return render(request, 'payments/crypto_payment.html', {'ticket_type': first_tt})


@login_required
def crypto_success(request):
    import random
    if random.choice([True, True, False]):
        cart = request.session.get('cart', {})
        if cart:
            pm, _ = PaymentMethod.objects.get_or_create(name='Crypto')
            total_amount = sum(TicketType.objects.get(id=tt_id).price * int(qty) for tt_id, qty in cart.items() if int(qty) > 0)
            
            transaction = Transaction.objects.create(
                user=request.user,
                payment_method=pm,
                amount=total_amount,
                status='COMPLETED'
            )

            created_tickets = []
            for tt_id, qty in cart.items():
                qty = int(qty)
                if qty > 0:
                    tt = TicketType.objects.get(id=tt_id)
                    TransactionDetail.objects.create(
                        transaction=transaction,
                        ticket_type=tt,
                        quantity=qty,
                        price=tt.price
                    )
                    for _ in range(qty):
                        ticket = Ticket.objects.create(ticket_type=tt, buyer=request.user, transaction=transaction)
                        created_tickets.append(ticket)
                    
                    tt.quantity_available -= qty
                    tt.save()
            
            request.session.pop('cart', None)
            request.session.pop('checkout_event_id', None)
            messages.success(request, "Pago en Criptomonedas confirmado en la red.")
            if created_tickets:
                return redirect('ticket_success', ticket_id=created_tickets[0].id)
            else:
                return redirect('my_tickets')
    messages.error(request, "Pago en cripto no detectado o fallido.")
    return redirect('/')


# =====================================================================
# MERCADO PAGO — Checkout Pro (SDK v3.4.0)
# =====================================================================

def _get_mp_sdk():
    """Retorna una instancia configurada del SDK de Mercado Pago."""
    return mercadopago.SDK(django_settings.MERCADOPAGO_ACCESS_TOKEN)


def _create_ticket_from_pending(pending: PendingMPPayment, mp_payment_id: str = None):
    """
    Crea los Tickets a partir de un PendingMPPayment (carrito) de forma idempotente.
    Retorna el primer ticket creado o una lista.
    """
    if pending.processed:
        logger.info("MP: pago %s ya procesado", pending.preference_id)
        # Buscar el primer ticket generado por esta preferencia (buscando en las tx)
        # Pero como no tenemos un enlace directo entre PendingMPPayment y Transaction, 
        # podríamos buscar los tickets del usuario más recientes, pero para mantenerlo simple,
        # retornaremos None y la vista manejará la redirección a my_tickets.
        return None

    cart = pending.cart_data
    if not cart:
        raise ValueError("El carrito guardado está vacío.")

    # Validar existencias
    for tt_id, qty in cart.items():
        qty = int(qty)
        if qty > 0:
            tt = TicketType.objects.get(id=tt_id)
            if tt.quantity_available < qty:
                raise ValueError(f"Boletos agotados para {tt.name}.")

    pm, _ = PaymentMethod.objects.get_or_create(name='Mercado Pago')
    transaction = Transaction.objects.create(
        user=pending.user,
        payment_method=pm,
        amount=pending.amount,
        status='COMPLETED'
    )

    created_tickets = []
    for tt_id, qty in cart.items():
        qty = int(qty)
        if qty > 0:
            tt = TicketType.objects.get(id=tt_id)
            TransactionDetail.objects.create(
                transaction=transaction,
                ticket_type=tt,
                quantity=qty,
                price=tt.price
            )
            for _ in range(qty):
                ticket = Ticket.objects.create(ticket_type=tt, buyer=pending.user, transaction=transaction)
                created_tickets.append(ticket)
            
            tt.quantity_available -= qty
            tt.save()

    pending.processed = True
    if mp_payment_id:
        pending.mp_payment_id = str(mp_payment_id)
    pending.save()

    logger.info("MP: %d tickets creados para preferencia %s", len(created_tickets), pending.preference_id)
    return created_tickets[0] if created_tickets else None


@login_required
def mercadopago_init(request):
    """
    Crea una preferencia de pago en Mercado Pago (Checkout Pro) con múltiples items.
    """
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "El carrito está vacío.")
        return redirect('/')

    sdk = _get_mp_sdk()

    success_url = request.build_absolute_uri('/payments/mp/success/')
    failure_url = request.build_absolute_uri('/payments/mp/failure/')
    pending_url = request.build_absolute_uri('/payments/mp/pending/')

    items = []
    total_amount = 0
    event_ref = None
    for tt_id, qty in cart.items():
        qty = int(qty)
        if qty > 0:
            tt = TicketType.objects.get(id=tt_id)
            if tt.quantity_available < qty:
                messages.error(request, f"Boletos agotados para {tt.name}.")
                return redirect('event_detail', pk=tt.event.id)
            event_ref = tt.event.id
            items.append({
                "id": str(tt.id),
                "title": f"{tt.event.title} — {tt.name}",
                "quantity": qty,
                "unit_price": int(tt.price),
                "currency_id": "CLP",
                "description": f"Boleto para {tt.event.title}",
            })
            total_amount += int(tt.price) * qty

    preference_data = {
        "items": items,
        "payer": {
            "name": request.user.first_name or request.user.username,
            "surname": request.user.last_name or "",
            "email": request.user.email,
            "identification": {"type": "RUT", "number": "12345678"},
        },
        "back_urls": {
            "success": success_url,
            "failure": failure_url,
            "pending": pending_url,
        },
        "payment_methods": {
            "installments": 1,
            "default_installments": 1,
            "excluded_payment_types": [
                {"id": "ticket"},
                {"id": "atm"},
            ],
        },
        "binary_mode": True,
        "external_reference": f"evt-{event_ref}-{request.user.id}",
        "statement_descriptor": "TIKETERA",
    }

    # auto_return solo funciona con URLs públicas (no localhost)
    if not django_settings.DEBUG:
        preference_data["auto_return"] = "approved"

    try:
        preference_response = sdk.preference().create(preference_data)
        http_status = preference_response.get("status")
        preference = preference_response.get("response", {})

        if http_status not in (200, 201):
            logger.error("MP preference creation failed (status=%s): %s", http_status, preference)
            messages.error(request, "Error al conectar con Mercado Pago. Intenta de nuevo.")
            return redirect('event_detail', pk=ticket_type.event.id)

        preference_id = preference.get('id')
        init_point = preference.get('init_point')

        # Persistir en BD para recuperación ante cierre de navegador
        PendingMPPayment.objects.get_or_create(
            preference_id=preference_id,
            defaults={
                'user': request.user,
                'cart_data': cart,
                'external_reference': f"evt-{event_ref}-{request.user.id}",
                'amount': total_amount,
            }
        )

        request.session['mp_preference_id'] = preference_id
        
        # Para el frontend render
        first_tt = TicketType.objects.get(id=list(cart.keys())[0])

        return render(request, 'payments/mercadopago_redirect.html', {
            'init_point': init_point,
            'ticket_type': first_tt,
            'preference_id': preference_id,
            'mp_public_key': django_settings.MERCADOPAGO_PUBLIC_KEY,
        })

    except Exception as e:
        logger.exception("Error inesperado al crear preferencia MP: %s", e)
        messages.error(request, "Error inesperado con Mercado Pago.")
        return redirect('/')


@login_required
def mercadopago_success(request):
    """
    Callback de retorno de MP con status aprobado.
    También sirve como punto de entrada cuando MP redirige de vuelta.
    Es idempotente gracias a PendingMPPayment.
    """
    payment_id = request.GET.get('payment_id')
    status = request.GET.get('status')
    preference_id_param = request.GET.get('preference_id')
    external_reference = request.GET.get('external_reference')

    logger.info("MP success callback: payment_id=%s status=%s pref=%s",
                payment_id, status, preference_id_param)

    if status == 'approved':
        # Buscar PendingMPPayment por preference_id o sesión
        preference_id = (
            preference_id_param or
            request.session.get('mp_preference_id')
        )
        pending = None
        if preference_id:
            pending = PendingMPPayment.objects.filter(preference_id=preference_id).first()
        if not pending:
            # Fallback: buscar por usuario + external_reference
            ext_ref = external_reference or f"evt-{request.session.get('checkout_event_id')}-{request.user.id}"
            if ext_ref:
                pending = PendingMPPayment.objects.filter(
                    user=request.user,
                    external_reference=ext_ref,
                    processed=False,
                ).order_by('-created_at').first()

        if pending:
            try:
                ticket = _create_ticket_from_pending(pending, payment_id)
                request.session.pop('cart', None)
                request.session.pop('mp_preference_id', None)
                request.session.pop('checkout_event_id', None)
                messages.success(request, "¡Pago aprobado con Mercado Pago!")
                if ticket:
                    return redirect('ticket_success', ticket_id=ticket.id)
                else:
                    return redirect('my_tickets')
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('/')
            except Exception as e:
                logger.exception("Error creando ticket desde success callback: %s", e)
                messages.error(request, "Error procesando tu compra.")
                return redirect('/')
        else:
            messages.error(request, "No se encontró el pago pendiente.")
            return redirect('/')

    elif status == 'pending':
        messages.info(request, "Tu pago está pendiente de acreditación.")
        return redirect('mercadopago_pending')
    else:
        messages.error(request, "El pago no fue aprobado.")
        return redirect('mercadopago_failure')


@login_required
def mercadopago_failure(request):
    """Retorno de MP con pago rechazado."""
    return render(request, 'payments/mercadopago_failure.html')


@login_required
def mercadopago_pending(request):
    """Retorno de MP con pago pendiente."""
    return render(request, 'payments/mercadopago_pending.html')


@login_required
def mercadopago_verify(request):
    preference_id = request.session.get('mp_preference_id')
    event_id = request.session.get('checkout_event_id')

    pending = None
    if preference_id:
        pending = PendingMPPayment.objects.filter(preference_id=preference_id).first()

    if not pending and request.user.is_authenticated:
        pending = PendingMPPayment.objects.filter(
            user=request.user, processed=False
        ).order_by('-created_at').first()
        if pending:
            preference_id = pending.preference_id
            
    if not pending and not event_id:
        return JsonResponse({'status': 'error', 'message': 'No hay pago pendiente.'}, status=400)

    if pending and pending.processed:
        # Ya está procesado, redirigimos genéricamente
        return JsonResponse({
            'status': 'approved',
            'redirect': '/tickets/mis-boletos/'
        })

    sdk = _get_mp_sdk()
    try:
        approved_payment = None
        if preference_id:
            search_resp = sdk.payment().search({
                "preference_id": preference_id,
                "sort": "date_created",
                "criteria": "desc",
            })
            if search_resp.get('status') == 200:
                for p in search_resp.get('response', {}).get('results', []):
                    if p.get('status') == 'approved':
                        approved_payment = p
                        break

        if not approved_payment and event_id:
            ext_ref = f"evt-{event_id}-{request.user.id}"
            search_resp2 = sdk.payment().search({
                "external_reference": ext_ref,
                "sort": "date_created",
                "criteria": "desc",
            })
            if search_resp2.get('status') == 200:
                for p in search_resp2.get('response', {}).get('results', []):
                    if p.get('status') == 'approved':
                        if not preference_id or p.get('preference_id') == preference_id:
                            approved_payment = p
                            break

        if approved_payment:
            mp_payment_id = str(approved_payment.get('id', ''))
            
            if not pending:
                # Caso extremo de recuperación sin pending existente y sin sesión...
                return JsonResponse({'status': 'error', 'message': 'Pago no registrado localmente'}, status=400)

            ticket = _create_ticket_from_pending(pending, mp_payment_id)
            request.session.pop('cart', None)
            request.session.pop('mp_preference_id', None)
            request.session.pop('checkout_event_id', None)
            
            return JsonResponse({
                'status': 'approved',
                'redirect': f'/tickets/success/{ticket.id}/' if ticket else '/tickets/mis-boletos/'
            })
        else:
            return JsonResponse({
                'status': 'pending',
                'message': 'Pago aún no confirmado por Mercado Pago.'
            })

    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    except Exception as e:
        logger.exception("Error en mercadopago_verify: %s", e)
        return JsonResponse({'status': 'error', 'message': 'Error al verificar el pago.'}, status=500)


@csrf_exempt
def mercadopago_webhook(request):
    """
    Endpoint IPN/Webhook de Mercado Pago — crea el ticket automáticamente
    cuando MP notifica un pago aprobado (funciona en producción con URL pública).
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    import json

    try:
        body = json.loads(request.body or '{}')
        topic = body.get('type') or request.GET.get('topic', '')
        resource_id = (
            body.get('data', {}).get('id') or
            request.GET.get('id')
        )

        logger.info("MP webhook received: type=%s id=%s", topic, resource_id)

        if topic == 'payment' and resource_id:
            sdk = _get_mp_sdk()
            payment_info = sdk.payment().get(resource_id)
            payment = payment_info.get('response', {})
            pay_status = payment.get('status')
            preference_id = payment.get('preference_id', '')
            mp_payment_id = str(payment.get('id', ''))

            logger.info("MP webhook payment: status=%s pref=%s", pay_status, preference_id)

            if pay_status == 'approved' and preference_id:
                pending = PendingMPPayment.objects.filter(preference_id=preference_id).first()
                if pending and not pending.processed:
                    try:
                        ticket = _create_ticket_from_pending(pending, mp_payment_id)
                        logger.info("MP webhook: ticket %s creado via webhook", ticket.id)
                    except Exception as e:
                        logger.exception("MP webhook error creando ticket: %s", e)

    except Exception as e:
        logger.exception("Error procesando webhook MP: %s", e)

    return HttpResponse(status=200)
