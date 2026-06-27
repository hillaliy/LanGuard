from django.contrib import admin
from .models import Device, DevicePort


class DevicePortInline(admin.TabularInline):
    model = DevicePort
    extra = 0
    readonly_fields = ("firstseen", "lastseen")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "ip", "mac", "vendor", "online", "known", "lastseen")
    list_filter = ("online", "known", "vendor")
    search_fields = ("name", "ip", "mac", "vendor")
    inlines = [DevicePortInline]


@admin.register(DevicePort)
class DevicePortAdmin(admin.ModelAdmin):
    list_display = ("device", "protocol", "port", "service", "open", "lastseen")
    list_filter = ("open", "protocol", "service")
    search_fields = ("device__name", "device__ip", "port", "service")
