"""
Tests para la pasarela Mercado Pago en el proyecto Tiketera.

Cubre:
  - Inicialización de preferencia (éxito y error SDK)
  - Callbacks de retorno: approved, pending, failure
  - Protección: stock agotado, autenticación requerida
  - Webhook IPN
  - Integración: routing desde buy_ticket + Webpay/Crypto sin cambios

Los tests mockean el SDK de Mercado Pago para ser completamente
independientes de la red y de las credenciales reales.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from tickets.models import TicketType, Ticket
from events.models import Event, Venue, Category
import json

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mp_preference_response(preference_id='TEST-PREF-123', status=201):
    """Construye una respuesta de preferencia MP simulada."""
    return {
        'status': status,
        'response': {
            'id': preference_id,
            'init_point': 'https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=TEST-PREF-123',
            'sandbox_init_point': 'https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=TEST-PREF-123',
        }
    }


def create_test_fixtures(username='testmp', email=None):
    """
    Crea un conjunto de fixtures (usuario, venue, category, event, ticket_type)
    respetando todos los NOT NULL del modelo.
    """
    email = email or f'{username}@example.com'
    user = User.objects.create_user(
        username=username,
        email=email,
        password='testpass123',
        first_name='Test',
        last_name='User',
    )
    venue = Venue.objects.create(
        name='Estadio Test',
        address='Av. Principal 123',
        capacity=5000,
    )
    category = Category.objects.create(name='Música')
    event = Event.objects.create(
        title='Concierto de Prueba',
        description='Descripción del concierto de prueba.',
        date_time='2030-12-31 20:00:00',
        venue=venue,
        category=category,
        organizer=user,
        is_published=True,
    )
    ticket_type = TicketType.objects.create(
        event=event,
        name='General',
        price=15000,
        quantity_available=10,
    )
    return user, venue, category, event, ticket_type


# ---------------------------------------------------------------------------
# Tests: mercadopago_init
# ---------------------------------------------------------------------------

class MercadoPagoInitViewTests(TestCase):
    """Tests para la vista mercadopago_init."""

    def setUp(self):
        self.client = Client()
        (self.user, self.venue, self.category,
         self.event, self.ticket_type) = create_test_fixtures('mpinit')

    def test_init_requires_login(self):
        """Usuarios no autenticados son redirigidos al login."""
        url = reverse('mercadopago_init', args=[self.ticket_type.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response['Location'])

    @patch('payments.views._get_mp_sdk')
    def test_init_creates_preference_and_shows_redirect(self, mock_get_sdk):
        """Con SDK ok, init crea preferencia y renderiza mercadopago_redirect.html."""
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = make_mp_preference_response()
        mock_get_sdk.return_value = mock_sdk

        self.client.login(username='mpinit', password='testpass123')
        url = reverse('mercadopago_init', args=[self.ticket_type.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/mercadopago_redirect.html')
        self.assertIn('init_point', response.context)
        self.assertIn('mercadopago', response.context['init_point'])

        # Sesión debe guardar ticket_type_id
        session = self.client.session
        self.assertEqual(session.get('pending_ticket_type_id'), self.ticket_type.id)

    @patch('payments.views._get_mp_sdk')
    def test_init_sdk_exception_redirects_to_event(self, mock_get_sdk):
        """Si el SDK lanza excepción, redirige al detalle del evento con error."""
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.side_effect = Exception("Connection error")
        mock_get_sdk.return_value = mock_sdk

        self.client.login(username='mpinit', password='testpass123')
        url = reverse('mercadopago_init', args=[self.ticket_type.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        storage = list(response.wsgi_request._messages)
        self.assertTrue(any('Error' in str(m) for m in storage))

    @patch('payments.views._get_mp_sdk')
    def test_init_bad_status_redirects_to_event(self, mock_get_sdk):
        """Si MP retorna status != 200/201, redirige al evento con error."""
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = make_mp_preference_response(status=400)
        mock_get_sdk.return_value = mock_sdk

        self.client.login(username='mpinit', password='testpass123')
        url = reverse('mercadopago_init', args=[self.ticket_type.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)

    def test_init_no_stock_redirects(self):
        """Si no hay stock, redirige al evento con mensaje de error."""
        self.ticket_type.quantity_available = 0
        self.ticket_type.save()

        self.client.login(username='mpinit', password='testpass123')
        url = reverse('mercadopago_init', args=[self.ticket_type.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        storage = list(response.wsgi_request._messages)
        self.assertTrue(any('agotado' in str(m).lower() for m in storage))


# ---------------------------------------------------------------------------
# Tests: mercadopago_success
# ---------------------------------------------------------------------------

class MercadoPagoSuccessViewTests(TestCase):
    """Tests para el callback mercadopago_success."""

    def setUp(self):
        self.client = Client()
        (self.user, self.venue, self.category,
         self.event, self.ticket_type) = create_test_fixtures('mpsuccess', 'mpsuccess@example.com')
        self.preference_id = 'TEST-PREF-SUCCESS-001'

    def _create_pending(self):
        """Crea un PendingMPPayment y lo guarda en la sesión del cliente."""
        from payments.models import PendingMPPayment
        pending = PendingMPPayment.objects.create(
            preference_id=self.preference_id,
            ticket_type=self.ticket_type,
            user=self.user,
            external_reference=str(self.ticket_type.id),
            amount=self.ticket_type.price,
        )
        self.client.login(username='mpsuccess', password='testpass123')
        session = self.client.session
        session['pending_ticket_type_id'] = self.ticket_type.id
        session['mp_preference_id'] = self.preference_id
        session.save()
        return pending

    def test_success_approved_creates_ticket(self):
        """Status approved → crea un ticket y descuenta stock."""
        self._create_pending()
        initial_stock = self.ticket_type.quantity_available

        url = reverse('mercadopago_success')
        response = self.client.get(url, {
            'payment_id': 'PAY-001',
            'status': 'approved',
            'preference_id': self.preference_id,
            'external_reference': str(self.ticket_type.id),
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Ticket.objects.filter(buyer=self.user).count(), 1)

        self.ticket_type.refresh_from_db()
        self.assertEqual(self.ticket_type.quantity_available, initial_stock - 1)

    def test_success_pending_redirects_to_pending_page(self):
        """Status pending → redirige a mercadopago_pending."""
        self._create_pending()

        url = reverse('mercadopago_success')
        response = self.client.get(url, {
            'payment_id': 'PAY-002',
            'status': 'pending',
            'external_reference': str(self.ticket_type.id),
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn('pending', response['Location'])
        self.assertEqual(Ticket.objects.filter(buyer=self.user).count(), 0)

    def test_success_rejected_redirects_to_failure_page(self):
        """Status rejected → redirige a mercadopago_failure."""
        self._create_pending()

        url = reverse('mercadopago_success')
        response = self.client.get(url, {
            'payment_id': 'PAY-003',
            'status': 'rejected',
            'external_reference': str(self.ticket_type.id),
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn('failure', response['Location'])
        self.assertEqual(Ticket.objects.filter(buyer=self.user).count(), 0)

    def test_success_approved_uses_preference_id_param(self):
        """Cuando MP envía preference_id en la URL, se usa para encontrar el PendingMPPayment."""
        self._create_pending()

        url = reverse('mercadopago_success')
        response = self.client.get(url, {
            'payment_id': 'PAY-004',
            'status': 'approved',
            'preference_id': self.preference_id,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Ticket.objects.filter(buyer=self.user).count(), 1)

    def test_success_requires_login(self):
        """Usuario no autenticado es redirigido al login."""
        url = reverse('mercadopago_success')
        response = self.client.get(url, {'status': 'approved'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response['Location'])


# ---------------------------------------------------------------------------
# Tests: páginas de resultado (failure, pending)
# ---------------------------------------------------------------------------

class MercadoPagoResultPagesTests(TestCase):
    """Tests para las páginas de resultado (failure, pending)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='resultuser',
            email='result@example.com',
            password='testpass123',
        )
        self.client.login(username='resultuser', password='testpass123')

    def test_failure_page_renders(self):
        """La página de fallo renderiza correctamente."""
        url = reverse('mercadopago_failure')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/mercadopago_failure.html')

    def test_pending_page_renders(self):
        """La página de pago pendiente renderiza correctamente."""
        url = reverse('mercadopago_pending')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/mercadopago_pending.html')

    def test_failure_requires_login(self):
        self.client.logout()
        url = reverse('mercadopago_failure')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response['Location'])

    def test_pending_requires_login(self):
        self.client.logout()
        url = reverse('mercadopago_pending')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response['Location'])


# ---------------------------------------------------------------------------
# Tests: Webhook IPN
# ---------------------------------------------------------------------------

class MercadoPagoWebhookTests(TestCase):
    """Tests para el endpoint de Webhook/IPN."""

    def setUp(self):
        self.client = Client()

    def test_webhook_get_returns_405(self):
        """El webhook sólo acepta POST."""
        url = reverse('mercadopago_webhook')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    @patch('payments.views._get_mp_sdk')
    def test_webhook_post_payment_notification_returns_200(self, mock_get_sdk):
        """Notificación de pago válida retorna 200 OK."""
        mock_sdk = MagicMock()
        mock_sdk.payment.return_value.get.return_value = {
            'response': {
                'status': 'approved',
                'external_reference': '1',
            }
        }
        mock_get_sdk.return_value = mock_sdk

        url = reverse('mercadopago_webhook')
        payload = json.dumps({'type': 'payment', 'data': {'id': '12345678'}})
        response = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_webhook_post_empty_body_returns_200(self):
        """Cuerpo vacío no rompe el webhook; siempre retorna 200."""
        url = reverse('mercadopago_webhook')
        response = self.client.post(url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_webhook_accessible_without_session(self):
        """El webhook es accesible sin autenticación (llamada desde MP)."""
        url = reverse('mercadopago_webhook')
        response = self.client.post(url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Tests: Integración routing buy_ticket → MP / Webpay / Crypto
# ---------------------------------------------------------------------------

class BuyTicketMPRoutingTests(TestCase):
    """
    Tests de integración: verifica que la selección de 'mp' en el formulario
    de compra redirige correctamente a mercadopago_init,
    y que Webpay y Crypto siguen funcionando sin cambios.
    """

    def setUp(self):
        self.client = Client()
        (self.user, self.venue, self.category,
         self.event, self.ticket_type) = create_test_fixtures('buyroute', 'buyroute@example.com')
        self.client.login(username='buyroute', password='testpass123')

    def test_post_mp_redirects_to_mercadopago_init(self):
        """payment_method='mp' → redirige a mercadopago_init."""
        url = reverse('buy_ticket', args=[self.ticket_type.id])
        response = self.client.post(url, {'payment_method': 'mp'})
        expected = reverse('mercadopago_init', args=[self.ticket_type.id])
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_post_webpay_still_works(self):
        """Webpay sigue funcionando sin cambios."""
        url = reverse('buy_ticket', args=[self.ticket_type.id])
        response = self.client.post(url, {'payment_method': 'webpay'})
        expected = reverse('webpay_init', args=[self.ticket_type.id])
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_post_crypto_still_works(self):
        """Crypto sigue funcionando sin cambios."""
        url = reverse('buy_ticket', args=[self.ticket_type.id])
        response = self.client.post(url, {'payment_method': 'crypto'})
        expected = reverse('crypto_init', args=[self.ticket_type.id])
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_post_unknown_method_shows_error(self):
        """Método desconocido → mensaje de error y redirige de vuelta."""
        url = reverse('buy_ticket', args=[self.ticket_type.id])
        response = self.client.post(url, {'payment_method': 'unknown'})
        self.assertEqual(response.status_code, 302)
        storage = list(response.wsgi_request._messages)
        self.assertTrue(any('método' in str(m).lower() or 'seleccione' in str(m).lower()
                            for m in storage))
