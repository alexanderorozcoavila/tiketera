from django.contrib import admin
from .models import PaymentMethod, Transaction, PendingMPPayment


@admin.register(PendingMPPayment)
class PendingMPPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'ticket_type', 'amount', 'processed', 'created_at', 'mp_payment_id')
    list_filter = ('processed',)
    search_fields = ('user__email', 'preference_id', 'mp_payment_id')
    readonly_fields = ('preference_id', 'mp_payment_id', 'created_at', 'external_reference')
    ordering = ('-created_at',)


admin.site.register(PaymentMethod)
admin.site.register(Transaction)
