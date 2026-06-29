from django.urls import path

from .views import (
    UserRegistrationView,
    UserLoginView,
    UserEditView,
    UserLogoutView,
    setup_status,
    device,
    events,
    scan_now,
    scan_runs,
    scan_status,
    notifications,
    export_db,
    import_db,
    users,
)

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("setup/", setup_status, name="setup-status"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("edit/", UserEditView.as_view(), name="user-edit"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("users/", users, name="users"),
    path("device/", device, name="device"),
    path("scan/", scan_now, name="scan_now"),
    path("scan/status/", scan_status, name="scan_status"),
    path("scan/runs/", scan_runs, name="scan_runs"),
    path("events/", events, name="events"),
    path("notifications/", notifications, name="notifications"),
    path("export-db/", export_db, name="export_db"),
    path("import-db/", import_db, name="import_db"),
]
