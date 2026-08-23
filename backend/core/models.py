from django.db import models
from django.conf import settings
from django.utils import timezone


class Device(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        RECENTLY_SEEN = "recently_seen", "Recently seen"
        SLEEPING = "sleeping", "Sleeping"
        OFFLINE = "offline", "Offline"

    class StatusSource(models.TextChoices):
        ARP = "arp", "ARP"
        PORT = "port", "Port"
        ICMP = "icmp", "ICMP"
        RECENT = "recent", "Recent"
        NONE = "none", "None"

    icon = models.CharField(max_length=255, default="plus")
    secondary_icon = models.CharField(max_length=255, blank=True, default="")
    name = models.CharField(max_length=100, default="Device")
    hostname = models.CharField(max_length=255, blank=True, default="")
    ip = models.GenericIPAddressField()
    mac = models.CharField(max_length=17, unique=True)
    vendor = models.CharField(max_length=255, blank=True, default="")
    role = models.CharField(max_length=32, blank=True, default="device")
    room = models.CharField(max_length=100, blank=True, default="")
    online = models.BooleanField(default=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ONLINE,
    )
    status_source = models.CharField(
        max_length=32,
        choices=StatusSource.choices,
        default=StatusSource.ARP,
    )
    status_reason = models.CharField(max_length=255, blank=True, default="")
    firstseen = models.DateTimeField(default=timezone.now)
    lastseen = models.DateTimeField(default=timezone.now)
    last_status_check = models.DateTimeField(blank=True, null=True)
    last_port_scan = models.DateTimeField(blank=True, null=True)
    missed_scans = models.PositiveIntegerField(default=0)
    known = models.BooleanField(default=False)
    is_gateway = models.BooleanField(default=False)

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
        indexes = [
            models.Index(fields=["-started_at"], name="core_scanrun_started_desc_idx"),
            models.Index(fields=["status", "-started_at"], name="core_scanrun_status_idx"),
        ]

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
        indexes = [
            models.Index(fields=["-created_at"], name="core_event_created_desc_idx"),
            models.Index(fields=["event_type", "-created_at"], name="core_event_type_created_idx"),
            models.Index(fields=["notified", "-created_at"], name="core_event_notified_idx"),
        ]

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
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
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
        indexes = [
            models.Index(fields=["-created_at"], name="core_notify_created_desc_idx"),
            models.Index(fields=["channel", "-created_at"], name="core_notify_channel_idx"),
            models.Index(fields=["status", "-created_at"], name="core_notify_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.channel} {self.status} - {self.event_id}"


class AppSettings(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    ip_range = models.CharField(max_length=64, default="192.168.1.0/24")
    scan_interval = models.PositiveIntegerField(default=10)
    time_zone = models.CharField(max_length=64, default="UTC")
    version_check_interval = models.PositiveIntegerField(default=21600)
    notifications_enabled = models.BooleanField(default=True)
    discord_enabled = models.BooleanField(default=True)
    discord_webhook = models.URLField(blank=True, default="")
    telegram_enabled = models.BooleanField(default=True)
    telegram_token = models.CharField(max_length=255, blank=True, default="")
    telegram_user_id = models.CharField(max_length=64, blank=True, default="")
    notify_new_devices = models.BooleanField(default=True)
    notify_device_online = models.BooleanField(default=False)
    notify_device_offline = models.BooleanField(default=False)
    notify_port_changes = models.BooleanField(default=False)
    notification_quiet_hours_enabled = models.BooleanField(default=False)
    notification_quiet_hours_start = models.CharField(max_length=5, default="22:00")
    notification_quiet_hours_end = models.CharField(max_length=5, default="07:00")
    activity_cleanup_retention_days = models.PositiveIntegerField(default=90)
    home_map_layout = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "App settings"
        verbose_name_plural = "App settings"

    def __str__(self):
        return "LanGuard settings"

    @classmethod
    def load(cls):
        defaults = {
            "ip_range": settings.IP_RANGE,
            "scan_interval": settings.INTERVAL,
            "time_zone": settings.TIME_ZONE,
            "version_check_interval": settings.VERSION_CHECK_INTERVAL,
            "notifications_enabled": settings.NOTIFICATIONS_ENABLED,
            "discord_enabled": settings.NOTIFICATIONS_ENABLED,
            "discord_webhook": settings.DISCORD_WEBHOOK or "",
            "telegram_enabled": settings.NOTIFICATIONS_ENABLED,
            "telegram_token": settings.TELEGRAM_TOKEN or "",
            "telegram_user_id": settings.TELEGRAM_USERID or "",
            "notify_new_devices": "new_device" in settings.NOTIFICATION_EVENT_TYPES,
            "notify_device_online": "device_online" in settings.NOTIFICATION_EVENT_TYPES,
            "notify_device_offline": "device_offline" in settings.NOTIFICATION_EVENT_TYPES,
            "notify_port_changes": any(
                event_type in settings.NOTIFICATION_EVENT_TYPES
                for event_type in ("port_opened", "port_closed")
            ),
            "notification_quiet_hours_enabled": False,
            "notification_quiet_hours_start": "22:00",
            "notification_quiet_hours_end": "07:00",
            "activity_cleanup_retention_days": 90,
            "home_map_layout": {},
        }
        config, _ = cls.objects.get_or_create(singleton_key=1, defaults=defaults)
        return config
