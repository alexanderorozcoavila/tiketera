from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_type import IntegrationType
from transbank.error.transbank_error import TransbankError
from tickets.models import TicketType, Ticket
from payments.models import PendingMPPayment
from django.contrib import messages
from core.models import SiteSettings
import uuid
import logging
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
    except TransbankError:
        messages.error(request, "Error al inicializar Webpay.")
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
    except TransbankError:
        messages.error(request, "Error en transacción (abortada).")
        return redirect('/')


# =====================================================================
# CRYPTO / WEB3 (sin cambios)
# =====================================================================

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


# =====================================================================
# MERCADO PAGO — Checkout Pro (SDK v3.4.0)
# =====================================================================

def _get_mp_sdk():
    """Retorna una instancia configurada del SDK de Mercado Pago."""
    return mercadopago.SDK(django_settings.MERCADOPAGO_ACCESS_TOKEN)


def _create_ticket_from_pending(pending: PendingMPPayment, mp_payment_id: str = None) -> Ticket:
    """
    Crea el Ticket a partir de un PendingMPPayment de forma idempotente.
    Si ya fue procesado, retorna el ticket existente sin crear duplicados.
    """
    if pending.processed and pending.resulting_ticket:
        logger.info("MP: pago %s ya procesado → ticket %s", pending.preference_id, pending.resulting_ticket.id)
        return pending.resulting_ticket

    ticket_type = pending.ticket_type
    if ticket_type.quantity_available <= 0:
        raise ValueError("Boletos agotados.")

    ticket = Ticket.objects.create(ticket_type=ticket_type, buyer=pending.user)
    ticket_type.quantity_available -= 1
    ticket_type.save()

    pending.processed = True
    pending.resulting_ticket = ticket
    if mp_payment_id:
        pending.mp_payment_id = str(mp_payment_id)
    pending.save()

    logger.info("MP: ticket %s creado para preferencia %s", ticket.id, pending.preference_id)
    return ticket


@login_required
def mercadopago_init(request, ticket_type_id):
    """
    Crea una preferencia de pago en Mercado Pago (Checkout Pro) y la persiste
    en la BD para recuperación ante cierre de navegador.
    """
    ticket_type = get_object_or_404(TicketType, id=ticket_type_id)

    if ticket_type.quantity_available <= 0:
        messages.error(request, "Boletos agotados.")
        return redirect('event_detail', pk=ticket_type.event.id)

    sdk = _get_mp_sdk()

    success_url = request.build_absolute_uri('/payments/mp/success/')
    failure_url = request.build_absolute_uri('/payments/mp/failure/')
    pending_url = request.build_absolute_uri('/payments/mp/pending/')

    preference_data = {
        "items": [
            {
                "id": str(ticket_type.id),
                "title": f"{ticket_type.event.title} — {ticket_type.name}",
                "quantity": 1,
                "unit_price": int(ticket_type.price),
                "currency_id": "CLP",
                "description": f"Boleto para {ticket_type.event.title}",
            }
        ],
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
        "external_reference": str(ticket_type_id),
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
                'ticket_type': ticket_type,
                'user': request.user,
                'external_reference': str(ticket_type_id),
                'amount': ticket_type.price,
            }
        )

        # También guardar en sesión (fallback rápido)
        request.session['pending_ticket_type_id'] = ticket_type.id
        request.session['mp_preference_id'] = preference_id

        return render(request, 'payments/mercadopago_redirect.html', {
            'init_point': init_point,
            'ticket_type': ticket_type,
            'preference_id': preference_id,
            'mp_public_key': django_settings.MERCADOPAGO_PUBLIC_KEY,
        })

    except Exception as e:
        logger.exception("Error inesperado al crear preferencia MP: %s", e)
        messages.error(request, "Error inesperado con Mercado Pago.")
        return redirect('event_detail', pk=ticket_type.event.id)


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
            ticket_type_id = request.session.get('pending_ticket_type_id') or external_reference
            if ticket_type_id:
                pending = PendingMPPayment.objects.filter(
                    user=request.user,
                    external_reference=str(ticket_type_id),
                    processed=False,
                ).order_by('-created_at').first()

        if pending:
            try:
                ticket = _create_ticket_from_pending(pending, payment_id)
                request.session.pop('pending_ticket_type_id', None)
                request.session.pop('mp_preference_id', None)
                messages.success(request, "¡Pago aprobado con Mercado Pago!")
                return redirect('ticket_success', ticket_id=ticket.id)
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
    """
    Endpoint de verificación automática consultando la API de MP server-side.

    El frontend llama a este endpoint cada 5 segundos automáticamente mientras
    el usuario está pagando en la otra pestaña. También sirve como recuperación
    si el usuario vuelve más tarde.

    Responde JSON con: {status: 'approved'|'pending'|'error', redirect?, message?}
    """
    # 1. Obtener preference_id y ticket_type_id desde sesión o BD
    preference_id = request.session.get('mp_preference_id')
    ticket_type_id = request.session.get('pending_ticket_type_id')

    # Si no hay sesión, buscar el último pago pendiente del usuario en BD
    pending = None
    if preference_id:
        pending = PendingMPPayment.objects.filter(preference_id=preference_id).first()

    if not pending and request.user.is_authenticated:
        pending = PendingMPPayment.objects.filter(
            user=request.user, processed=False
        ).order_by('-created_at').first()
        if pending:
            preference_id = pending.preference_id
            ticket_type_id = pending.ticket_type_id

    if not pending and not ticket_type_id:
        return JsonResponse({'status': 'error', 'message': 'No hay pago pendiente.'}, status=400)

    # 2. Si ya fue procesado, redirigir al ticket existente (idempotencia)
    if pending and pending.processed and pending.resulting_ticket:
        return JsonResponse({
            'status': 'approved',
            'redirect': f'/tickets/success/{pending.resulting_ticket.id}/'
        })

    sdk = _get_mp_sdk()

    try:
        approved_payment = None

        # Estrategia 1: buscar por preference_id (más preciso)
        if preference_id:
            search_resp = sdk.payment().search({
                "preference_id": preference_id,
                "sort": "date_created",
                "criteria": "desc",
            })
            logger.info("MP verify search by preference_id status: %s", search_resp.get('status'))
            if search_resp.get('status') == 200:
                for p in search_resp.get('response', {}).get('results', []):
                    if p.get('status') == 'approved':
                        approved_payment = p
                        break

        # Estrategia 2: fallback por external_reference (ticket_type_id)
        if not approved_payment and ticket_type_id:
            search_resp2 = sdk.payment().search({
                "external_reference": str(ticket_type_id),
                "sort": "date_created",
                "criteria": "desc",
            })
            logger.info("MP verify search by ext_ref status: %s", search_resp2.get('status'))
            if search_resp2.get('status') == 200:
                for p in search_resp2.get('response', {}).get('results', []):
                    if p.get('status') == 'approved':
                        # Verificar que coincide con nuestra preferencia o usuario
                        if not preference_id or p.get('preference_id') == preference_id:
                            approved_payment = p
                            break

        if approved_payment:
            mp_payment_id = str(approved_payment.get('id', ''))

            # Obtener o crear el PendingMPPayment
            if not pending:
                try:
                    pending = PendingMPPayment.objects.get(preference_id=preference_id)
                except PendingMPPayment.DoesNotExist:
                    # Crear desde sesión si no existe en BD (edge case)
                    ticket_type = TicketType.objects.get(id=ticket_type_id)
                    pending = PendingMPPayment.objects.create(
                        preference_id=preference_id or f"recovered-{mp_payment_id}",
                        ticket_type=ticket_type,
                        user=request.user,
                        external_reference=str(ticket_type_id),
                        amount=ticket_type.price,
                    )

            ticket = _create_ticket_from_pending(pending, mp_payment_id)
            request.session.pop('pending_ticket_type_id', None)
            request.session.pop('mp_preference_id', None)

            return JsonResponse({
                'status': 'approved',
                'redirect': f'/tickets/success/{ticket.id}/'
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
