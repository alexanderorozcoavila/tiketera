from django.contrib import admin
from .models import PaymentMethod, Transaction

admin.site.register(PaymentMethod)
admin.site.register(Transaction)
