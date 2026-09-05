from django.db import models
from django.conf import settings
from django.utils import timezone


QUIET_HOURS_DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def default_quiet_hours_days():
    return list(QUIET_HOURS_DAY_KEYS)


def default_scan_ranges():
    return ["192.168.1.0/24"]


def default_scan_range_labels():
    return {"192.168.1.0/24": "Primary network"}


def default_scan_range_label(index):
    return "Primary network" if index == 0 else f"Network {index + 1}"


class Device(models.Model):
    class NotificationPreference(models.TextChoices):
        INHERIT = "inherit", "Use global setting"
        ALWAYS = "always", "Always notify"
        NEVER = "never", "Never notify"

    class IdentitySource(models.TextChoices):
        REVERSE_DNS = "reverse_dns", "Reverse DNS"
        MDNS = "mdns", "mDNS"
        LLMNR = "llmnr", "LLMNR"
        NETBIOS = "netbios", "NetBIOS"
        SSDP = "ssdp", "SSDP / UPnP"
        SNMP = "snmp", "SNMP"
        HTTP = "http", "Device web interface"
        ARP = "arp", "ARP"
        MANUF = "manuf", "Wireshark manuf"
        INFERRED = "inferred", "Inferred"
        IMPORTED = "imported", "Imported inventory"

    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        RECENTLY_SEEN = "recently_seen", "Recently seen"
        SLEEPING = "sleeping", "Sleeping"
        OFFLINE = "offline", "Offline"

    class StatusSource(models.TextChoices):
        ARP = "arp", "ARP"
        LOCAL = "local", "Local scanner"
        PORT = "port", "Port"
        ICMP = "icmp", "ICMP"
        RECENT = "recent", "Recent"
        NONE = "none", "None"

    icon = models.CharField(max_length=255, default="plus")
    secondary_icon = models.CharField(max_length=255, blank=True, default="")
    name = models.CharField(max_length=100, default="Device")
    hostname = models.CharField(max_length=255, blank=True, default="")
    hostname_source = models.CharField(
        max_length=32,
        choices=IdentitySource.choices,
        blank=True,
        default="",
    )
    ip = models.GenericIPAddressField()
    mac = models.CharField(max_length=17, unique=True)
    vendor = models.CharField(max_length=255, blank=True, default="")
    vendor_source = models.CharField(
        max_length=32,
        choices=IdentitySource.choices,
        blank=True,
        default="",
    )
    comments = models.TextField(blank=True, default="")
    external_url = models.URLField(max_length=2048, blank=True, default="")
    online_notification_preference = models.CharField(
        max_length=16,
        choices=NotificationPreference.choices,
        default=NotificationPreference.INHERIT,
    )
    offline_notification_preference = models.CharField(
        max_length=16,
        choices=NotificationPreference.choices,
        default=NotificationPreference.INHERIT,
    )
    attention_acknowledged_signature = models.CharField(max_length=64, blank=True, default="")
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


class DeviceDNSActivity(models.Model):
    device = models.ForeignKey(
        Device,
        related_name="dns_activity",
        on_delete=models.CASCADE,
    )
    domain = models.CharField(max_length=253)
    query_type = models.CharField(max_length=16, blank=True, default="")
    query_count = models.PositiveBigIntegerField(default=0)
    blocked_count = models.PositiveBigIntegerField(default=0)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    last_status = models.CharField(max_length=32, blank=True, default="")
    last_reason = models.CharField(max_length=64, blank=True, default="")
    last_service_name = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        ordering = ["-last_seen", "domain", "query_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "domain", "query_type"],
                name="unique_device_dns_domain_type",
            )
        ]
        indexes = [
            models.Index(
                fields=["device", "-last_seen"],
                name="core_dns_device_seen_idx",
            ),
            models.Index(
                fields=["device", "-blocked_count"],
                name="core_dns_device_blocked_idx",
            ),
        ]

    def __str__(self):
        return f"{self.device.name} - {self.domain} ({self.query_type or 'DNS'})"


class AdGuardUnmatchedClient(models.Model):
    client = models.CharField(max_length=255, unique=True)
    query_count = models.PositiveBigIntegerField(default=0)
    blocked_count = models.PositiveBigIntegerField(default=0)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    last_domain = models.CharField(max_length=253, blank=True, default="")
    last_status = models.CharField(max_length=32, blank=True, default="")
    last_reason = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-last_seen", "client"]
        indexes = [
            models.Index(fields=["-last_seen"], name="core_ag_unmatched_seen_idx"),
            models.Index(fields=["-query_count"], name="core_ag_unmatched_query_idx"),
        ]

    def __str__(self):
        return self.client


class ScanRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    ip_range = models.CharField(max_length=64)
    scan_ranges = models.JSONField(default=list, blank=True)
    scan_range_labels = models.JSONField(default=dict, blank=True)
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
        WEBHOOK = "webhook", "Webhook"

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


class UserAccess(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="languard_access",
        on_delete=models.CASCADE,
    )
    can_edit_devices = models.BooleanField(default=True)
    can_edit_home_map = models.BooleanField(default=True)
    can_run_scans = models.BooleanField(default=True)

    class Meta:
        verbose_name = "User access"
        verbose_name_plural = "User access"

    def __str__(self):
        return f"LanGuard access for {self.user}"


class AppSettings(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    ip_range = models.CharField(max_length=64, default="192.168.1.0/24")
    scan_ranges = models.JSONField(default=default_scan_ranges, blank=True)
    scan_range_labels = models.JSONField(default=default_scan_range_labels, blank=True)
    scan_interval = models.PositiveIntegerField(default=10)
    time_zone = models.CharField(max_length=64, default="UTC")
    version_check_interval = models.PositiveIntegerField(default=21600)
    notifications_enabled = models.BooleanField(default=True)
    discord_enabled = models.BooleanField(default=True)
    discord_webhook = models.URLField(blank=True, default="")
    telegram_enabled = models.BooleanField(default=True)
    telegram_token = models.CharField(max_length=255, blank=True, default="")
    telegram_user_id = models.CharField(max_length=64, blank=True, default="")
    webhook_enabled = models.BooleanField(default=False)
    webhook_url = models.URLField(max_length=2048, blank=True, default="")
    webhook_secret = models.CharField(max_length=255, blank=True, default="")
    notify_new_devices = models.BooleanField(default=True)
    notify_device_online = models.BooleanField(default=False)
    notify_device_offline = models.BooleanField(default=False)
    notify_port_changes = models.BooleanField(default=False)
    notification_quiet_hours_enabled = models.BooleanField(default=False)
    notification_quiet_hours_start = models.CharField(max_length=5, default="22:00")
    notification_quiet_hours_end = models.CharField(max_length=5, default="07:00")
    notification_quiet_hours_days = models.JSONField(
        default=default_quiet_hours_days,
        blank=True,
    )
    activity_cleanup_retention_days = models.PositiveIntegerField(default=90)
    adguard_enabled = models.BooleanField(default=False)
    adguard_url = models.URLField(max_length=2048, blank=True, default="")
    adguard_username = models.CharField(max_length=255, blank=True, default="")
    adguard_password = models.CharField(max_length=255, blank=True, default="")
    adguard_sync_interval = models.PositiveIntegerField(default=5)
    adguard_retention_days = models.PositiveIntegerField(default=90)
    adguard_last_sync_at = models.DateTimeField(blank=True, null=True)
    adguard_last_error = models.TextField(blank=True, default="")
    speedtest_tracker_enabled = models.BooleanField(default=False)
    speedtest_tracker_url = models.URLField(max_length=2048, blank=True, default="")
    speedtest_tracker_api_token = models.CharField(max_length=512, blank=True, default="")
    home_map_layout = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "App settings"
        verbose_name_plural = "App settings"

    def __str__(self):
        return "LanGuard settings"

    @property
    def effective_scan_ranges(self):
        if isinstance(self.scan_ranges, list):
            ranges = [str(value).strip() for value in self.scan_ranges if str(value).strip()]
            if ranges:
                return ranges
        return [self.ip_range]

    @property
    def effective_scan_range_labels(self):
        stored_labels = self.scan_range_labels if isinstance(self.scan_range_labels, dict) else {}
        return {
            network_range: (
                str(stored_labels.get(network_range) or "").strip()
                or default_scan_range_label(index)
            )
            for index, network_range in enumerate(self.effective_scan_ranges)
        }

    @classmethod
    def load(cls):
        defaults = {
            "ip_range": settings.IP_RANGE,
            "scan_ranges": [settings.IP_RANGE],
            "scan_range_labels": {settings.IP_RANGE: "Primary network"},
            "scan_interval": settings.INTERVAL,
            "time_zone": settings.TIME_ZONE,
            "version_check_interval": settings.VERSION_CHECK_INTERVAL,
            "notifications_enabled": settings.NOTIFICATIONS_ENABLED,
            "discord_enabled": settings.NOTIFICATIONS_ENABLED,
            "discord_webhook": settings.DISCORD_WEBHOOK or "",
            "telegram_enabled": settings.NOTIFICATIONS_ENABLED,
            "telegram_token": settings.TELEGRAM_TOKEN or "",
            "telegram_user_id": settings.TELEGRAM_USERID or "",
            "webhook_enabled": False,
            "webhook_url": "",
            "webhook_secret": "",
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
            "notification_quiet_hours_days": default_quiet_hours_days(),
            "activity_cleanup_retention_days": 90,
            "adguard_enabled": False,
            "adguard_url": "",
            "adguard_username": "",
            "adguard_password": "",
            "adguard_sync_interval": 5,
            "adguard_retention_days": 90,
            "adguard_last_sync_at": None,
            "adguard_last_error": "",
            "speedtest_tracker_enabled": False,
            "speedtest_tracker_url": "",
            "speedtest_tracker_api_token": "",
            "home_map_layout": {},
        }
        config, _ = cls.objects.get_or_create(singleton_key=1, defaults=defaults)
        return config
