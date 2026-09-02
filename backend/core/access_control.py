from rest_framework import permissions

from .models import UserAccess


ACCESS_FIELDS = (
    "can_edit_devices",
    "can_edit_home_map",
    "can_run_scans",
)


def user_capabilities(user):
    if not user or not user.is_authenticated:
        return {field: False for field in ACCESS_FIELDS}
    if user.is_staff or user.is_superuser:
        return {field: True for field in ACCESS_FIELDS}

    access = UserAccess.objects.filter(user=user).first()
    if access is None:
        return {field: True for field in ACCESS_FIELDS}
    return {field: bool(getattr(access, field)) for field in ACCESS_FIELDS}


def update_user_capabilities(user, values):
    updates = {field: values[field] for field in ACCESS_FIELDS if field in values}
    access, _ = UserAccess.objects.get_or_create(user=user)
    if updates:
        for field, value in updates.items():
            setattr(access, field, bool(value))
        access.save(update_fields=list(updates))
    return access


class CanEditDevices(permissions.BasePermission):
    message = "You do not have permission to edit devices."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return user_capabilities(request.user)["can_edit_devices"]


class CanEditHomeMap(permissions.BasePermission):
    message = "You do not have permission to edit the Home Map."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return user_capabilities(request.user)["can_edit_home_map"]


class CanRunScans(permissions.BasePermission):
    message = "You do not have permission to run network scans."

    def has_permission(self, request, view):
        return user_capabilities(request.user)["can_run_scans"]
