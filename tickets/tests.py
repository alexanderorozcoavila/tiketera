from django.test import TestCase
from django.contrib.auth import get_user_model
from events.models import Event, Venue, Category
from tickets.models import TicketType, Ticket
from django.utils import timezone
import datetime

User = get_user_model()

class TicketBlockchainTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.venue = Venue.objects.create(name='Test Venue', address='123 Test St', capacity=100)
        self.category = Category.objects.create(name='Concert')
        self.event = Event.objects.create(
            title='Test Event',
            description='A test event',
            date_time=timezone.now() + datetime.timedelta(days=1),
            venue=self.venue,
            category=self.category,
            organizer=self.user,
            is_published=True
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name='General',
            price=50.00,
            quantity_available=100
        )

    def test_ticket_creation_loads_blockchain_data(self):
        # Create a ticket which should trigger the save() method and blockchain logic
        ticket = Ticket.objects.create(
            ticket_type=self.ticket_type,
            buyer=self.user
        )
        
        # Verify that blockchain data was loaded upon save
        self.assertIsNotNone(ticket.eth_transaction_hash, "El hash de transacción de Ethereum no debería ser nulo")
        self.assertTrue(ticket.eth_transaction_hash.startswith("0x"), "El hash debe comenzar con 0x")
        
        self.assertIsNotNone(ticket.eth_token_id, "El ID del token generado no debería ser nulo")
        self.assertTrue(ticket.eth_token_id.startswith("TK-"), "El ID del token debe comenzar con TK-")
