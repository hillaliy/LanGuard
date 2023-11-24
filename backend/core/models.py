from django.db import models
from django.utils import timezone


class Device(models.Model):
    icon = models.CharField(max_length=255)
    name = models.CharField(max_length=50)
    ip = models.TextField()
    mac = models.TextField()
    vendor = models.TextField()
    online = models.BooleanField(default=True)
    lastseen = models.DateTimeField(default=timezone.now)
    known = models.BooleanField(default=False)

    def __str__(self):
        return f"Device: {self.name} - IP:{self.ip}"
