from django.urls import path
from .views.homebox import test_homebox, search_homebox
from .views.docker import (
    docker_device_context,
    docker_host_detail,
    docker_hosts,
    docker_inventory_overview,
    sync_docker_host_view,
)
from .views.users import (
    UserLoginView,
    UserLogoutView,
    UserRegistrationView,
    setup_status,
    users,
)
from .views.app_settings import app_settings, version_status
from .views.integrations import (
    speedtest_tracker_latest,
    sync_adguard,
    sync_pihole_now,
    sync_technitium_now,
    test_adguard,
    test_pihole,
    test_technitium,
    test_speedtest_tracker,
)
from .views.dns_activity import (
    device_dns_activity,
    dns_activity,
    dns_unmatched_clients,
)
from .views.notifications import notifications, test_notification_channel
from .views.activity import events, scan_runs
from .views.scans import scan_now, scan_status
from .views.port_scans import cancel_detailed_port_scan, detailed_port_scan
from .views.health import health_status
from .views.home_map import home_map_layout
from .views.maintenance import maintenance_cleanup
from .views.diagnostics import export_diagnostics
from .views.devices import (
    bulk_update_devices,
    device,
    device_availability,
    device_merge_candidates,
    device_web_interface,
    merge_devices,
    unmerge_device,
    wake_device,
)

from .views.inventory import (
    export_devices,
    import_devices,
    import_netalertx_devices,
    import_watchyourlan_devices,
)

urlpatterns = [
    path(
        "integrations/docker/inventory/",
        docker_inventory_overview,
        name="docker-inventory-overview",
    ),
    path("integrations/docker/hosts/", docker_hosts, name="docker-hosts"),
    path(
        "integrations/docker/hosts/<int:host_id>/",
        docker_host_detail,
        name="docker-host-detail",
    ),
    path(
        "integrations/docker/hosts/<int:host_id>/sync/",
        sync_docker_host_view,
        name="sync-docker-host",
    ),
    path(
        "integrations/docker/device/",
        docker_device_context,
        name="docker-device-context",
    ),
    path("integrations/homebox/test/", test_homebox, name="test-homebox"),
    path("integrations/homebox/items/", search_homebox, name="homebox-items"),
    path("health/", health_status, name="health-status"),
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("setup/", setup_status, name="setup-status"),
    path("version/", version_status, name="version-status"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("users/", users, name="users"),
    path("settings/", app_settings, name="app-settings"),
    path("integrations/adguard/test/", test_adguard, name="test-adguard"),
    path("integrations/adguard/sync/", sync_adguard, name="sync-adguard"),
    path("integrations/pihole/test/", test_pihole, name="test-pihole"),
    path("integrations/pihole/sync/", sync_pihole_now, name="sync-pihole"),
    path(
        "integrations/technitium/test/",
        test_technitium,
        name="test-technitium",
    ),
    path(
        "integrations/technitium/sync/",
        sync_technitium_now,
        name="sync-technitium",
    ),
    path(
        "integrations/speedtest-tracker/test/",
        test_speedtest_tracker,
        name="test-speedtest-tracker",
    ),
    path(
        "integrations/speedtest-tracker/latest/",
        speedtest_tracker_latest,
        name="speedtest-tracker-latest",
    ),
    path(
        "notifications/test/",
        test_notification_channel,
        name="test-notification-channel",
    ),
    path("home-map-layout/", home_map_layout, name="home-map-layout"),
    path("maintenance/cleanup/", maintenance_cleanup, name="maintenance-cleanup"),
    path("device/", device, name="device"),
    path("device/availability/", device_availability, name="device-availability"),
    path(
        "device/merge-candidates/",
        device_merge_candidates,
        name="device-merge-candidates",
    ),
    path("device/merge/", merge_devices, name="merge-devices"),
    path("device/unmerge/", unmerge_device, name="unmerge-device"),
    path("devices/bulk-update/", bulk_update_devices, name="bulk-update-devices"),
    path("device/web-interface/", device_web_interface, name="device-web-interface"),
    path("device/wake/", wake_device, name="wake-device"),
    path("device/port-scan/", detailed_port_scan, name="detailed-port-scan"),
    path(
        "device/port-scan/cancel/",
        cancel_detailed_port_scan,
        name="cancel-detailed-port-scan",
    ),
    path("device/dns-activity/", device_dns_activity, name="device-dns-activity"),
    path("dns-activity/", dns_activity, name="dns-activity"),
    path(
        "dns-activity/unmatched/",
        dns_unmatched_clients,
        name="dns-unmatched-clients",
    ),
    path("scan/", scan_now, name="scan_now"),
    path("scan/status/", scan_status, name="scan_status"),
    path("scan/runs/", scan_runs, name="scan_runs"),
    path("events/", events, name="events"),
    path("notifications/", notifications, name="notifications"),
    path("devices/export/", export_devices, name="export_devices"),
    path("diagnostics/export/", export_diagnostics, name="export_diagnostics"),
    path("devices/import/", import_devices, name="import_devices"),
    path(
        "devices/import/netalertx/",
        import_netalertx_devices,
        name="import_netalertx_devices",
    ),
    path(
        "devices/import/watchyourlan/",
        import_watchyourlan_devices,
        name="import_watchyourlan_devices",
    ),
]
