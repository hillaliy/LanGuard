from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes

from ..database_writes import DatabaseWriteBusy
from ..integrations.openwrt import OpenWrtError, inspect_openwrt, sync_openwrt
from ..models import AppSettings
from ..serializers.settings import AppSettingsSerializer
from ..user_messages import error_response, success_response


class OpenWrtConnectionSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=2048)
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(required=False, allow_blank=True, max_length=255,
                                     trim_whitespace=False, write_only=True)
    verify_ssl = serializers.BooleanField(default=True)

    validate_url = AppSettingsSerializer.validate_openwrt_url
    validate_username = AppSettingsSerializer.validate_openwrt_username

    def validate(self, attrs):
        if not attrs.get("password"):
            saved = AppSettings.load()
            if (attrs["url"], attrs["username"]) != (saved.openwrt_url, saved.openwrt_username) or not saved.openwrt_password:
                raise serializers.ValidationError({"password": "Enter the password for this router and username."})
            attrs["password"] = saved.openwrt_password
        return attrs


@extend_schema(request=OpenWrtConnectionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_openwrt_connection(request):
    serializer = OpenWrtConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        _, _, summary = inspect_openwrt(**serializer.validated_data)
    except OpenWrtError as exc:
        return error_response("OpenWrt connection failed", str(exc), response_status=status.HTTP_502_BAD_GATEWAY)
    unavailable = summary["unavailable"]
    details = f"Found {summary['leases']} IPv4 leases, {summary['host_hints']} host hints and {summary['wireless_clients']} Wi-Fi clients."
    if unavailable:
        details += f" Unavailable: {', '.join(unavailable)}."
    return success_response(summary, "OpenWrt connected", f"{details} No devices were changed.")


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def sync_openwrt_now(request):
    try:
        summary = sync_openwrt(manual=True)
    except OpenWrtError as exc:
        return error_response("OpenWrt sync failed", str(exc), response_status=status.HTTP_502_BAD_GATEWAY)
    except DatabaseWriteBusy:
        return error_response("OpenWrt sync delayed", "The database is busy. No changes were saved.",
                              response_status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if summary["status"] == "disabled":
        return success_response(summary, "OpenWrt disabled", "Enable OpenWrt before syncing.")
    return success_response(summary, "OpenWrt synced",
                            f"Created {summary['devices_discovered']} devices and enriched {summary['clients_enriched']} interfaces.")
