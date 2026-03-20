from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # Additional custom fields can be added here later
    telephone = models.CharField(max_length=20, blank=True, null=True)
