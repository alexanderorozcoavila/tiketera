import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from django.db import models
from django.conf import settings
from events.models import Event

class TicketType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_types')
    name = models.CharField(max_length=100) # e.g. VIP, General
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.IntegerField()

    def __str__(self):
        return f"{self.event.title} - {self.name}"

class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    purchase_date = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    
    # Blockchain details
    eth_transaction_hash = models.CharField(max_length=100, blank=True, null=True)
    eth_token_id = models.CharField(max_length=100, blank=True, null=True)

    def get_qr_base64(self):
        from django.core.signing import Signer
        import json
        import base64
        from io import BytesIO

        signer = Signer()
        signed_token = signer.sign(str(self.id))
        payload = json.dumps({"token": signed_token})

        qr = qrcode.QRCode(version=1, box_size=10, border=1) # border=1 para mejor lectura en moviles
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        if not self.eth_transaction_hash:
            from core.blockchain import register_ticket_on_blockchain
            tx_hash, token_id = register_ticket_on_blockchain(self.id)
            if tx_hash:
                self.eth_transaction_hash = tx_hash
                self.eth_token_id = token_id
            
        super().save(*args, **kwargs)
