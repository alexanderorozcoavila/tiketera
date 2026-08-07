import uuid
from django.db import models
from django.conf import settings
from tickets.models import Ticket


class PaymentMethod(models.Model):
    name = models.CharField(max_length=50)  # e.g. Credit Card, Ethereum
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'Pending'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')],
        default='PENDING'
    )

    def __str__(self):
        return f"Tx {self.id} - {self.status}"


class TransactionDetail(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='details')
    ticket_type = models.ForeignKey('tickets.TicketType', on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.ticket_type} (Tx: {self.transaction.id})"


class PendingMPPayment(models.Model):
    """
    Registro persistente de cada sesión de pago de Mercado Pago.

    Permite recuperar y confirmar el pago aunque el usuario cierre el navegador
    antes de ser redirigido de vuelta al sitio. El webhook y el polling
    automático usan este registro para crear el ticket de forma idempotente.
    """
    preference_id = models.CharField(max_length=400, unique=True, db_index=True)
    mp_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    # Guarda el carrito (ej. {"1": 4, "2": 2}) -> ticket_type_id: qty
    cart_data = models.JSONField(default=dict, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    external_reference = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False, db_index=True)


    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Pago Pendiente MP'
        verbose_name_plural = 'Pagos Pendientes MP'

    def __str__(self):
        icon = '✓' if self.processed else '⏳'
        return f"{icon} {self.user} · {self.preference_id[:30]}..."
