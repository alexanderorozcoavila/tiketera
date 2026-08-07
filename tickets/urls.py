from django.urls import path
from .views import process_payment, ticket_success, MyTicketsView, TicketScannerView, download_ticket_pdf, my_favorite, checkout
from .api_views import ValidateTicketView
from .views import toggle_favorite

urlpatterns = [
    path('checkout/<int:event_id>/', checkout, name='checkout'),
    path('pay/', process_payment, name='process_payment'),
    path('success/<uuid:ticket_id>/', ticket_success, name='ticket_success'),
    path('mis-boletos/', MyTicketsView.as_view(), name='my_tickets'),
    path('api/validate/', ValidateTicketView.as_view(), name='api_validate_ticket'),
    path('scan/', TicketScannerView.as_view(), name='ticket_scanner'),
    path('download/<uuid:ticket_id>/', download_ticket_pdf, name='download_ticket'),
    
#FAVORITOS
    path('mis-favoritos/', my_favorite, name='my_favorite'),
    path('toggle_favorite/', toggle_favorite, name='toggle_favorite')
]
