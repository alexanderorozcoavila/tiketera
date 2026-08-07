from django.contrib import admin
from .models import PaymentMethod, Transaction, PendingMPPayment


@admin.register(PendingMPPayment)
class PendingMPPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'processed', 'created_at', 'mp_payment_id')
    list_filter = ('processed',)
    search_fields = ('user__email', 'preference_id', 'mp_payment_id')
    readonly_fields = ('preference_id', 'mp_payment_id', 'created_at', 'external_reference', 'cart_data')
    ordering = ('-created_at',)

class TransactionDetailInline(admin.TabularInline):
    from .models import TransactionDetail
    model = TransactionDetail
    extra = 0

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'status', 'timestamp')
    inlines = [TransactionDetailInline]

admin.site.register(PaymentMethod)
