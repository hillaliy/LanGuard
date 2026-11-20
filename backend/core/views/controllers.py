from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, PolymorphicProxySerializer, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from ..database_writes import DatabaseWriteBusy, serialized_database_write
from ..integrations.controllers import PROVIDERS, ControllerBusy, sync_connection
from ..integrations.unifi import ControllerError, normalize_url
from ..integrations.omada import identifier, normalize_url as normalize_omada_url
from ..integrations.routeros import normalize_url as normalize_routeros_url
from ..integrations.controllers import provider_client
from ..models import ControllerConnection
from ..user_messages import error_response, success_response
from ..datetime_utils import utc_isoformat


class ControllerCredentials(serializers.Serializer):
    url = serializers.CharField(max_length=2048)
    api_key = serializers.CharField(max_length=512, required=False, allow_blank=True, write_only=True)
    verify_ssl = serializers.BooleanField(default=True)
    site_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_url(self, value):
        try:
            return normalize_url(value) if value else ""
        except ControllerError as exc:
            raise serializers.ValidationError(str(exc)) from None

    def validate_api_key(self, value):
        if any(not 33 <= ord(c) <= 126 for c in value):
            raise serializers.ValidationError("Enter a valid local API key.")
        return value


class ControllerSettings(ControllerCredentials):
    url = serializers.CharField(max_length=2048, allow_blank=True)
    enabled = serializers.BooleanField()
    sync_interval = serializers.IntegerField(min_value=1, max_value=1440)


class OmadaCredentials(ControllerCredentials):
    api_key = None
    client_secret = serializers.CharField(max_length=512, required=False, allow_blank=True,
                                          write_only=True, trim_whitespace=False)
    controller_id = serializers.CharField(max_length=128, allow_blank=True)
    client_id = serializers.CharField(max_length=128, allow_blank=True)
    site_id = serializers.CharField(max_length=128, required=False, allow_null=True)

    def validate_url(self, value):
        try:
            return normalize_omada_url(value) if value else ""
        except ControllerError as exc:
            raise serializers.ValidationError(str(exc)) from None

    def validate_client_secret(self, value):
        return self.validate_api_key(value)

    def _identifier(self, value):
        if value and not identifier(value):
            raise serializers.ValidationError("Use only letters, numbers, hyphens and underscores.")
        return value

    validate_controller_id = _identifier
    validate_client_id = _identifier

    def validate_site_id(self, value):
        if value is None:
            return None
        if not identifier(value):
            raise serializers.ValidationError("Select a valid Omada site.")
        return value


class OmadaSettings(OmadaCredentials):
    url = serializers.CharField(max_length=2048, allow_blank=True)
    enabled = serializers.BooleanField()
    sync_interval = serializers.IntegerField(min_value=1, max_value=1440)


class RouterOSCredentials(serializers.Serializer):
    url = serializers.CharField(max_length=2048)
    username = serializers.CharField(max_length=128, allow_blank=True)
    password = serializers.CharField(max_length=512, required=False, allow_blank=True,
                                     write_only=True, trim_whitespace=False)
    verify_ssl = serializers.BooleanField(default=True)

    def validate_url(self, value):
        try:
            return normalize_routeros_url(value) if value else ""
        except ControllerError as exc:
            raise serializers.ValidationError(str(exc)) from None

    def validate_username(self, value):
        if ":" in value or any(not 32 <= ord(c) <= 126 for c in value):
            raise serializers.ValidationError("Enter a valid RouterOS username without colons or control characters.")
        return value

    def validate_password(self, value):
        if any(not 32 <= ord(c) <= 126 for c in value):
            raise serializers.ValidationError("Use printable ASCII credentials for RouterOS Basic authentication.")
        return value


class RouterOSSettings(RouterOSCredentials):
    url = serializers.CharField(max_length=2048, allow_blank=True)
    enabled = serializers.BooleanField()
    sync_interval = serializers.IntegerField(min_value=1, max_value=1440)


def _serializer(provider, *, settings=False):
    return ({"omada": OmadaSettings, "routeros": RouterOSSettings}.get(provider, ControllerSettings)
            if settings else {"omada": OmadaCredentials, "routeros": RouterOSCredentials}.get(provider, ControllerCredentials))


def _name(provider):
    return ControllerConnection.Provider(provider).label


def _connection(provider, *, for_update=False):
    if provider not in PROVIDERS:
        raise NotFound("Unknown network controller provider.")
    connections = ControllerConnection.objects
    if for_update:
        connections = connections.select_for_update()
    return connections.filter(provider=provider).first() or ControllerConnection(provider=provider)


def connection_status(connection):
    data = {
        "enabled": connection.enabled, "url": connection.url,
        "site_id": str(connection.site_id) if connection.site_id else None,
        "verify_ssl": connection.verify_ssl, "sync_interval": connection.sync_interval,
        "has_key": bool(connection.api_key),
        "configured": bool(connection.url and connection.api_key and connection.site_id),
        "last_attempt_at": utc_isoformat(connection.last_attempt_at) if connection.last_attempt_at else None,
        "last_sync_at": utc_isoformat(connection.last_sync_at) if connection.last_sync_at else None,
        "last_result": connection.last_result, "last_error": connection.last_error,
        "syncing": bool(connection.lock_until and connection.lock_until > timezone.now()),
    }
    if connection.provider == ControllerConnection.Provider.OMADA:
        data.update(controller_id=connection.controller_id, client_id=connection.client_id)
    if connection.provider == ControllerConnection.Provider.ROUTEROS:
        data.update(username=connection.username, configured=bool(connection.url and connection.api_key and connection.username))
    return data


def _credentials(connection, data, *, required=True):
    omada = connection.provider == ControllerConnection.Provider.OMADA
    routeros = connection.provider == ControllerConnection.Provider.ROUTEROS
    secret_field = "password" if routeros else "client_secret" if omada else "api_key"
    url, key = data["url"], data.get(secret_field) or ""
    if omada and required and not (data.get("controller_id") and data.get("client_id")):
        raise serializers.ValidationError({"controller_id": "Enter the controller ID and Client ID."})
    if routeros and required and not data.get("username"):
        raise serializers.ValidationError({"username": "Enter the RouterOS username."})
    if not key and connection.api_key:
        if url != connection.url or (omada and any(
            data.get(field) != getattr(connection, field) for field in ("controller_id", "client_id")
        )) or (routeros and data.get("username") != connection.username):
            raise serializers.ValidationError({secret_field: "Re-enter the secret when changing controller or client identity."})
        key = connection.api_key
    if key and any(key in str(data.get(field, "")) for field in ("url", "controller_id", "client_id", "site_id", "username")):
        raise serializers.ValidationError({"url": "The controller URL must not contain the API key."})
    if required and not (url and key):
        raise serializers.ValidationError({secret_field: "Enter the controller URL and credentials."})
    return url, key, data["verify_ssl"]


def _busy():
    return error_response("Controller busy", "A synchronization or database write is already in progress.",
                          response_status=status.HTTP_409_CONFLICT)


@extend_schema(request=PolymorphicProxySerializer(
    component_name="NetworkControllerSettings",
    serializers=[ControllerSettings, OmadaSettings, RouterOSSettings],
    resource_type_field_name=None,
), responses=OpenApiTypes.OBJECT)
@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAdminUser])
def controller_connection(request, provider):
    connection = _connection(provider)
    if request.method == "GET":
        return Response({"data": connection_status(connection)})
    serializer_class = _serializer(provider, settings=True)
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        with serialized_database_write(timeout=2), transaction.atomic():
            connection = _connection(provider, for_update=True)
            if connection_status(connection)["syncing"]:
                return _busy()
            url, key, verify_ssl = _credentials(connection, data, required=data["enabled"])
            site_id = data.get("site_id")
            site_id = str(site_id) if site_id else None
            if data["enabled"] and not site_id and provider != "routeros":
                raise serializers.ValidationError({"site_id": "Select a controller site."})
            controller_id, client_id = data.get("controller_id", ""), data.get("client_id", "")
            username = data.get("username", "")
            changed = (connection.url, connection.api_key, connection.verify_ssl, str(connection.site_id),
                       connection.controller_id, connection.client_id, connection.username) != (
                url, key, verify_ssl, str(site_id), controller_id, client_id, username,
            )
            if data["enabled"] and not connection.enabled:
                connection.last_attempt_at = None
            if changed:
                connection.last_sync_at = connection.last_attempt_at = None
                connection.last_error, connection.last_result = "", {}
            connection.enabled, connection.sync_interval = data["enabled"], data["sync_interval"]
            connection.url, connection.api_key, connection.verify_ssl, connection.site_id = url, key, verify_ssl, site_id
            connection.controller_id, connection.client_id = controller_id, client_id
            connection.username = username
            connection.save()
    except DatabaseWriteBusy:
        return _busy()
    return success_response(connection_status(connection), "Controller settings saved", "Controller settings were updated.")


def _probe(request, provider, *, sites_only):
    connection = _connection(provider)
    serializer_class = _serializer(provider)
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        connection.url, connection.api_key, connection.verify_ssl = _credentials(connection, data)
        connection.controller_id, connection.client_id = data.get("controller_id", ""), data.get("client_id", "")
        connection.username = data.get("username", "")
        with provider_client(connection) as client:
            result = {"sites": client.list_sites()} if sites_only else client.test_connection(data.get("site_id"))
    except ControllerError as exc:
        return error_response("Connection failed", str(exc), response_status=status.HTTP_502_BAD_GATEWAY)
    return success_response(result, f"{_name(provider)} connected",
                            "Connection verified without changing devices.")


@extend_schema(request=PolymorphicProxySerializer(
    component_name="NetworkControllerCredentials",
    serializers=[ControllerCredentials, OmadaCredentials, RouterOSCredentials],
    resource_type_field_name=None,
), responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def controller_sites(request, provider):
    return _probe(request, provider, sites_only=True)


@extend_schema(request=PolymorphicProxySerializer(
    component_name="NetworkControllerCredentials",
    serializers=[ControllerCredentials, OmadaCredentials, RouterOSCredentials],
    resource_type_field_name=None,
), responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def controller_test(request, provider):
    return _probe(request, provider, sites_only=False)


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def controller_sync(request, provider):
    _connection(provider)
    try:
        result = sync_connection(provider, manual=True)
    except (ControllerBusy, DatabaseWriteBusy):
        return _busy()
    except ControllerError as exc:
        return error_response("Sync failed", str(exc), response_status=status.HTTP_502_BAD_GATEWAY)
    if result["status"] != "ok":
        return error_response("Controller disabled", "Enable and save the controller before syncing.",
                              response_status=status.HTTP_409_CONFLICT)
    return success_response(result, f"{_name(provider)} synced",
                            f"{result['created']} created, {result['updated']} updated.")
