from django.urls import path
from .views import buy_ticket, ticket_success, MyTicketsView
from .api_views import ValidateTicketView

urlpatterns = [
    path('buy/<int:ticket_type_id>/', buy_ticket, name='buy_ticket'),
    path('success/<uuid:ticket_id>/', ticket_success, name='ticket_success'),
    path('mis-boletos/', MyTicketsView.as_view(), name='my_tickets'),
    path('api/validate/', ValidateTicketView.as_view(), name='api_validate_ticket'),
]
