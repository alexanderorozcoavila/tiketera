from django.contrib import admin
from django.utils.html import format_html
from .models import TicketType, Ticket

admin.site.register(TicketType)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket_type', 'buyer', 'purchase_date', 'is_used', 'download_pdf_link')
    list_filter = ('purchase_date', 'ticket_type')

    def download_pdf_link(self, obj):
        return format_html('<a href="/tickets/download/{}/" target="_blank">PDF</a>', obj.id)
    download_pdf_link.short_description = 'Descargar PDF'
