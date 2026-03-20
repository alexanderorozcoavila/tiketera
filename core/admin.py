from django.contrib import admin
from .models import SiteSettings

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    # This prevents creating more than one settings object
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()
