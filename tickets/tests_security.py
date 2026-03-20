from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from events.models import Event, Venue, Category
from tickets.models import TicketType, Ticket
from django.core.signing import Signer

User = get_user_model()

class PentestValidationAPI(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin', password='password')
        self.hacker = User.objects.create_user(username='hacker', password='password')
        self.victim = User.objects.create_user(username='victim', password='password')
        
        venue = Venue.objects.create(name='V', address='A', capacity=10)
        category = Category.objects.create(name='C')
        self.event = Event.objects.create(title='E', description='D', date_time='2030-01-01T12:00:00Z', venue=venue, category=category, organizer=self.admin)
        self.ticket_type = TicketType.objects.create(event=self.event, name='G', price=10, quantity_available=5)
        self.ticket = Ticket.objects.create(ticket_type=self.ticket_type, buyer=self.victim)

        self.url = reverse('api_validate_ticket')
        self.signer = Signer()
        self.valid_token = self.signer.sign(str(self.ticket.id))

    def test_unauthenticated_access_denied(self):
        # Pentest: Verify anonymous users cannot validate
        response = self.client.post(self.url, {'token': self.valid_token})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_access_denied(self):
        # Pentest: Verify regular users cannot validate
        self.client.force_authenticate(user=self.hacker)
        response = self.client.post(self.url, {'token': self.valid_token})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tampered_signature_rejected(self):
        # Pentest: Verify modified signatures fail
        self.client.force_authenticate(user=self.admin)
        tampered_token = self.valid_token + "hacked"
        response = self.client.post(self.url, {'token': tampered_token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid signature", response.data['error'])

    def test_valid_signature_success(self):
        # Ensure it works under normal authorized conditions
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {'token': self.valid_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'valid')
        
    def test_double_spend_prevented(self):
        # Pentest: Cannot use ticket twice
        self.client.force_authenticate(user=self.admin)
        self.client.post(self.url, {'token': self.valid_token}) # First use
        
        response2 = self.client.post(self.url, {'token': self.valid_token}) # Second use
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response2.data['status'], 'already_used')
