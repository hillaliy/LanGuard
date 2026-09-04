from django.contrib import admin
from .models import (
    AdGuardUnmatchedClient,
    AppSettings,
    Device,
    DeviceDNSActivity,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
    UserAccess,
)


class DevicePortInline(admin.TabularInline):
    model = DevicePort
    extra = 0
    readonly_fields = ("firstseen", "lastseen")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "name", "ip", "mac", "vendor", "status", "status_source",
        "online_notification_preference", "offline_notification_preference",
        "online", "known", "is_gateway", "lastseen",
    )
    list_filter = (
        "status", "status_source", "online_notification_preference",
        "offline_notification_preference", "online", "known", "is_gateway", "vendor",
    )
    search_fields = ("name", "ip", "mac", "vendor")
    inlines = [DevicePortInline]


@admin.register(DevicePort)
class DevicePortAdmin(admin.ModelAdmin):
    list_display = ("device", "protocol", "port", "service", "open", "lastseen")
    list_filter = ("open", "protocol", "service")
    search_fields = ("device__name", "device__ip", "port", "service")


@admin.register(UserAccess)
class UserAccessAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "can_edit_devices",
        "can_edit_home_map",
        "can_run_scans",
    )
    list_filter = ("can_edit_devices", "can_edit_home_map", "can_run_scans")
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(DeviceDNSActivity)
class DeviceDNSActivityAdmin(admin.ModelAdmin):
    list_display = (
        "device",
        "domain",
        "query_type",
        "query_count",
        "blocked_count",
        "last_seen",
    )
    list_filter = ("query_type", "last_reason")
    search_fields = ("device__name", "device__ip", "domain")
    readonly_fields = ("first_seen", "last_seen")


@admin.register(AdGuardUnmatchedClient)
class AdGuardUnmatchedClientAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "query_count",
        "blocked_count",
        "last_domain",
        "last_seen",
    )
    search_fields = ("client", "last_domain")
    readonly_fields = ("first_seen", "last_seen")


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
        "adguard_enabled",
        "adguard_sync_interval",
        "adguard_retention_days",
        "time_zone",
        "notifications_enabled",
        "webhook_enabled",
        "updated_at",
    )
    readonly_fields = ("singleton_key", "updated_at")
