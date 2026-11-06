from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes

from ..database_writes import serialized_database_write
from ..integrations.asuswrt import AsuswrtError, inspect_asuswrt, normalize_asuswrt_url, sync_asuswrt
from ..models import AppSettings
from ..user_messages import error_response, success_response


class AsuswrtConnectionSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=2048)
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(required=False, allow_blank=True, max_length=255,
                                     trim_whitespace=False, write_only=True)
    verify_ssl = serializers.BooleanField(default=True)

    def validate_url(self, value):
        try:
            return normalize_asuswrt_url(value)
        except AsuswrtError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_username(self, value):
        if ":" in value or any(not char.isprintable() for char in value):
            raise serializers.ValidationError("Enter a valid router username.")
        return value

    def validate(self, attrs):
        if not attrs.get("password"):
            saved = AppSettings.load()
            if attrs["url"] != saved.asuswrt_url or attrs["username"] != saved.asuswrt_username or not saved.asuswrt_password:
                raise serializers.ValidationError({"password": "Enter the password for this router and username."})
            attrs["password"] = saved.asuswrt_password
        return attrs


@extend_schema(request=AsuswrtConnectionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_asuswrt_connection(request):
    serializer = AsuswrtConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        with serialized_database_write():
            _, summary = inspect_asuswrt(data["url"], data["username"], data["password"], data["verify_ssl"])
    except AsuswrtError as exc:
        return error_response("ASUSWRT connection failed", str(exc), response_status=status.HTTP_502_BAD_GATEWAY)
    return success_response(summary, "ASUSWRT connected",
                            f"Found {summary['clients_active']} active IPv4 clients. No devices were changed.")


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def sync_asuswrt_now(request):
    try:
        result = sync_asuswrt(manual=True)
    except AsuswrtError as exc:
        return error_response("ASUSWRT sync failed", str(exc), response_status=status.HTTP_502_BAD_GATEWAY)
    return success_response(result, "ASUSWRT synced" if result["status"] == "ok" else "ASUSWRT disabled",
                            f"Created {result.get('devices_discovered', 0)} devices and enriched {result.get('clients_enriched', 0)} interfaces.")
