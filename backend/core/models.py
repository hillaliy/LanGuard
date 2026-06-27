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


class ScanRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    ip_range = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    devices_seen = models.PositiveIntegerField(default=0)
    new_devices = models.PositiveIntegerField(default=0)
    online_devices = models.PositiveIntegerField(default=0)
    ports_opened = models.PositiveIntegerField(default=0)
    ports_closed = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Scan {self.ip_range} - {self.status}"


class NetworkEvent(models.Model):
    class EventType(models.TextChoices):
        NEW_DEVICE = "new_device", "New device"
        DEVICE_ONLINE = "device_online", "Device online"
        DEVICE_OFFLINE = "device_offline", "Device offline"
        PORT_OPENED = "port_opened", "Port opened"
        PORT_CLOSED = "port_closed", "Port closed"

    scan_run = models.ForeignKey(
        ScanRun,
        related_name="events",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    device = models.ForeignKey(
        Device,
        related_name="events",
        on_delete=models.CASCADE,
    )
    device_port = models.ForeignKey(
        DevicePort,
        related_name="events",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    notified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message


class NotificationDelivery(models.Model):
    class Channel(models.TextChoices):
        DISCORD = "discord", "Discord"
        TELEGRAM = "telegram", "Telegram"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    event = models.ForeignKey(
        NetworkEvent,
        related_name="notifications",
        on_delete=models.CASCADE,
    )
    channel = models.CharField(max_length=32, choices=Channel.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.channel} {self.status} - {self.event_id}"
