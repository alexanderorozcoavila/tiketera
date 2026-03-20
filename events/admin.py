from django.contrib import admin
from .models import Event, Venue, Category

admin.site.register(Venue)
admin.site.register(Category)
admin.site.register(Event)
