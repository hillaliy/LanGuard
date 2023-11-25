from django.urls import path

from .views import (
    UserRegistrationView,
    UserLoginView,
    UserLogoutView,
    device,
    export_db,
    import_db,
)

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("device/", device, name="device"),
    path("export-db/", export_db, name="export_db"),
    path("import-db/", import_db, name="import_db"),
]
