from django.contrib import admin
from .models import TicketType, Ticket

admin.site.register(TicketType)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket_type', 'buyer', 'purchase_date', 'is_used')
    list_filter = ('purchase_date', 'ticket_type')
