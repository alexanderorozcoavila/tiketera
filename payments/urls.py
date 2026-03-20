from django.urls import path
from .views import webpay_init, webpay_return, crypto_init, crypto_success

urlpatterns = [
    path('webpay/init/<int:ticket_type_id>/', webpay_init, name='webpay_init'),
    path('webpay/return/', webpay_return, name='webpay_return'),
    path('crypto/init/<int:ticket_type_id>/', crypto_init, name='crypto_init'),
    path('crypto/success/', crypto_success, name='crypto_success'),
]
