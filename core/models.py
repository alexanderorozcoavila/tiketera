from django.db import models

class SiteSettings(models.Model):
    debug_bypass_payments = models.BooleanField(
        default=False,
        help_text="Enable to generate tickets without going through the payment gateway."
    )
    web3_provider_url = models.URLField(
        default='http://127.0.0.1:8545',
        help_text="URL del nodo Web3 (Ej: Infura, Alchemy o local Ganache/Hardhat)."
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Global Site Settings"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if SiteSettings.objects.exists() and not self.pk:
            return
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(id=1)
        return settings
