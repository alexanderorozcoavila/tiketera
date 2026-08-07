from django.urls import path
from .views import (
    webpay_init, webpay_return,
    crypto_init, crypto_success,
    mercadopago_init, mercadopago_success,
    mercadopago_failure, mercadopago_pending,
    mercadopago_webhook, mercadopago_verify,
)

urlpatterns = [
    # --- Webpay Plus ---
    path('webpay/init/', webpay_init, name='webpay_init'),
    path('webpay/return/', webpay_return, name='webpay_return'),

    # --- Crypto / Web3 ---
    path('crypto/init/', crypto_init, name='crypto_init'),
    path('crypto/success/', crypto_success, name='crypto_success'),

    # --- Mercado Pago ---
    path('mp/init/', mercadopago_init, name='mercadopago_init'),
    path('mp/success/', mercadopago_success, name='mercadopago_success'),
    path('mp/failure/', mercadopago_failure, name='mercadopago_failure'),
    path('mp/pending/', mercadopago_pending, name='mercadopago_pending'),
    path('mp/webhook/', mercadopago_webhook, name='mercadopago_webhook'),
    path('mp/verify/', mercadopago_verify, name='mercadopago_verify'),
]
