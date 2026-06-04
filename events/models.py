from django.db import models
from django.conf import settings

class Venue(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    capacity = models.IntegerField()

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Event(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    date_time = models.DateTimeField()
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organized_events')
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class Favorite(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites'
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'event')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} -> {self.event.title}"
