from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes

from ..integrations.dhcp import DhcpError, inspect_lease_source, lease_path, sync_dhcp
from ..datetime_utils import utc_isoformat
from ..user_messages import error_response, success_response


class DhcpSourceSerializer(serializers.Serializer):
    lease_file = serializers.CharField(max_length=512)
    format = serializers.ChoiceField(choices=["dnsmasq", "kea", "isc"])

    def validate_lease_file(self, value):
        try:
            lease_path(value)
        except DhcpError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


@extend_schema(request=DhcpSourceSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_dhcp_source(request):
    serializer = DhcpSourceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        _, summary, observed_at = inspect_lease_source(
            serializer.validated_data["lease_file"], serializer.validated_data["format"],
        )
    except DhcpError as exc:
        return error_response("DHCP source test failed", str(exc), response_status=status.HTTP_502_BAD_GATEWAY)
    return success_response(
        {**summary, "observed_at": utc_isoformat(observed_at)}, "DHCP source available",
        f"Found {summary['active_leases']} active IPv4 leases. No devices were changed.",
    )


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def sync_dhcp_now(request):
    try:
        result = sync_dhcp()
    except DhcpError as exc:
        return error_response("DHCP sync failed", str(exc), response_status=status.HTTP_502_BAD_GATEWAY)
    return success_response(
        result, "DHCP source synced" if result["status"] == "ok" else "DHCP source disabled",
        f"Processed {result.get('active_leases', 0)} active leases; "
        f"created {result.get('devices_discovered', 0)} and updated {result.get('devices_updated', 0)} devices.",
    )
