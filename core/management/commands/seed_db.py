from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from events.models import Venue, Category, Event
import datetime

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with initial admin user, venues, categories, and events.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting database seeding...")

        # Create Admin
        admin_email = 'admin@tiketera.com'
        if not User.objects.filter(username=admin_email).exists():
            admin = User.objects.create_superuser(
                username=admin_email,
                email=admin_email,
                password='admin123',
                first_name='Admin',
                last_name='Tiketera'
            )
            self.stdout.write(self.style.SUCCESS(f"Created Superuser: {admin_email}"))
        else:
            admin = User.objects.get(username=admin_email)
            self.stdout.write(f"Superuser {admin_email} already exists.")

        # Create Venue
        venue, created = Venue.objects.get_or_create(
            name='Estadio Nacional',
            defaults={
                'address': 'Av. Grecia 2001, Ñuñoa, Santiago',
                'capacity': 50000
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Venue: {venue.name}"))

        # Create Category
        category, created = Category.objects.get_or_create(
            name='Conciertos'
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Category: {category.name}"))

        # Create Event
        # We will create it 30 days in the future
        event_date = timezone.now() + datetime.timedelta(days=30)
        
        event, created = Event.objects.get_or_create(
            title='Gran Concierto de Apertura',
            defaults={
                'description': 'Ven a disfrutar del mejor concierto del año.',
                'date_time': event_date,
                'venue': venue,
                'category': category,
                'organizer': admin,
                'is_published': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Event: {event.title}"))
        else:
            self.stdout.write(f"Event {event.title} already exists.")

        # Create TicketType
        from tickets.models import TicketType
        ticket_type, created = TicketType.objects.get_or_create(
            event=event,
            name='General',
            defaults={
                'price': 15000.00,
                'quantity_available': 100
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created TicketType: {ticket_type.name} for {event.title}"))

        # Create Payment Methods
        from payments.models import PaymentMethod
        for pm_name in ['Mercado Pago', 'Webpay Plus', 'Crypto']:
            pm, created = PaymentMethod.objects.get_or_create(name=pm_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created PaymentMethod: {pm_name}"))

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))

