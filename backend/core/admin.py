from django.contrib import admin
from .models import (
    AppSettings,
    Device,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)


class DevicePortInline(admin.TabularInline):
    model = DevicePort
    extra = 0
    readonly_fields = ("firstseen", "lastseen")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "ip", "mac", "vendor", "status", "status_source", "online", "known", "is_gateway", "lastseen")
    list_filter = ("status", "status_source", "online", "known", "is_gateway", "vendor")
    search_fields = ("name", "ip", "mac", "vendor")
    inlines = [DevicePortInline]


@admin.register(DevicePort)
class DevicePortAdmin(admin.ModelAdmin):
    list_display = ("device", "protocol", "port", "service", "open", "lastseen")
    list_filter = ("open", "protocol", "service")
    search_fields = ("device__name", "device__ip", "port", "service")


@admin.register(ScanRun)
class ScanRunAdmin(admin.ModelAdmin):
    list_display = (
        "ip_range",
        "status",
        "started_at",
        "finished_at",
        "devices_seen",
        "new_devices",
        "ports_opened",
        "ports_closed",
    )
    list_filter = ("status",)
    readonly_fields = ("started_at", "finished_at")


@admin.register(NetworkEvent)
class NetworkEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "device", "message", "notified", "created_at")
    list_filter = ("event_type", "notified")
    search_fields = ("message", "device__name", "device__ip", "device__mac")
    readonly_fields = ("created_at",)


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("channel", "status", "event", "attempts", "created_at", "sent_at")
    list_filter = ("channel", "status")
    search_fields = ("event__message", "error")
    readonly_fields = ("created_at", "sent_at")


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "ip_range",
        "scan_interval",
        "version_check_interval",
        "activity_cleanup_retention_days",
        "time_zone",
        "notifications_enabled",
        "updated_at",
    )
    readonly_fields = ("singleton_key", "updated_at")
