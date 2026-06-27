from django.db import models
from django.utils import timezone


class Device(models.Model):
    icon = models.CharField(max_length=255, default="plus")
    name = models.CharField(max_length=100, default="Device")
    ip = models.GenericIPAddressField()
    mac = models.CharField(max_length=17, unique=True)
    vendor = models.CharField(max_length=255, blank=True, default="")
    online = models.BooleanField(default=True)
    firstseen = models.DateTimeField(default=timezone.now)
    lastseen = models.DateTimeField(default=timezone.now)
    known = models.BooleanField(default=False)

    class Meta:
        ordering = ["-online", "name", "ip"]

    def __str__(self):
        return f"Device: {self.name} - IP:{self.ip}"


class DevicePort(models.Model):
    device = models.ForeignKey(Device, related_name="ports", on_delete=models.CASCADE)
    port = models.PositiveIntegerField()
    protocol = models.CharField(max_length=8, default="tcp")
    service = models.CharField(max_length=64, blank=True, default="")
    open = models.BooleanField(default=True)
    firstseen = models.DateTimeField(default=timezone.now)
    lastseen = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["port"]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "port", "protocol"],
                name="unique_device_port_protocol",
            )
        ]

    def __str__(self):
        status = "open" if self.open else "closed"
        return f"{self.device.name} {self.protocol}/{self.port} {status}"
