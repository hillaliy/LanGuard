import logging

from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..adguard import AdGuardError, sync_adguard_query_log, test_adguard_connection
from ..api import parse_bool_param
from ..models import AppSettings
from ..pihole import PiHoleError, sync_pihole, test_pihole_connection
from ..serializers import (
    AdGuardConnectionSerializer,
    PiHoleConnectionSerializer,
    SpeedtestTrackerConnectionSerializer,
)
from ..speedtest_tracker import SpeedtestTrackerError, latest_speedtest_result
from ..user_messages import error_response, success_response

LOGGER = logging.getLogger(__name__)


@extend_schema(request=AdGuardConnectionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_adguard(request):
    serializer = AdGuardConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    config = AppSettings.load()
    password = data.get("password") or config.adguard_password
    try:
        result = test_adguard_connection(
            data["url"],
            data.get("username", "").strip(),
            password,
        )
    except AdGuardError as exc:
        return error_response(
            "AdGuard Home connection failed",
            str(exc),
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    query_log = "enabled" if result.get("query_log_enabled") else "disabled"
    return success_response(
        result,
        "AdGuard Home connected",
        f"Connection succeeded. Query log is {query_log}.",
    )


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def sync_adguard(request):
    try:
        result = sync_adguard_query_log()
    except AdGuardError as exc:
        return error_response(
            "AdGuard Home sync failed",
            str(exc),
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    return success_response(
        result,
        "AdGuard Home synced",
        (
            f"Matched {result.get('matched', 0)} queries across "
            f"{result.get('domains_updated', 0)} device domains."
        ),
    )


@extend_schema(request=PiHoleConnectionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_pihole(request):
    serializer = PiHoleConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    config = AppSettings.load()
    password = data.get("password") or config.pihole_password
    try:
        result = test_pihole_connection(data["url"], password)
    except PiHoleError as exc:
        return error_response(
            "Pi-hole connection failed",
            str(exc),
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    return success_response(
        result,
        "Pi-hole connected",
        "Connection succeeded. Query and DHCP APIs are available.",
    )


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def sync_pihole_now(request):
    try:
        result = sync_pihole()
    except PiHoleError as exc:
        return error_response(
            "Pi-hole sync failed",
            str(exc),
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    return success_response(
        result,
        "Pi-hole synced",
        (
            f"Matched {result.get('matched', 0)} queries and processed "
            f"{result.get('leases', 0)} DHCP leases."
        ),
    )


@extend_schema(request=SpeedtestTrackerConnectionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_speedtest_tracker(request):
    serializer = SpeedtestTrackerConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    config = AppSettings.load()
    api_token = data.get("api_token") or config.speedtest_tracker_api_token
    try:
        result, _ = latest_speedtest_result(
            data["url"],
            api_token,
            force_refresh=True,
        )
    except SpeedtestTrackerError as exc:
        return error_response(
            "Speedtest Tracker connection failed",
            str(exc),
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    return success_response(
        result,
        "Speedtest Tracker connected",
        "Connection succeeded and the latest result is available.",
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def speedtest_tracker_latest(request):
    config = AppSettings.load()
    configured = bool(
        config.speedtest_tracker_url and config.speedtest_tracker_api_token
    )
    integration = {
        "enabled": config.speedtest_tracker_enabled,
        "configured": configured,
        "available": False,
        "service_url": config.speedtest_tracker_url if configured else "",
    }
    if not config.speedtest_tracker_enabled or not configured:
        return Response({"data": None, "integration": integration})

    try:
        result, cached = latest_speedtest_result(
            config.speedtest_tracker_url,
            config.speedtest_tracker_api_token,
            force_refresh=parse_bool_param(request.query_params, "refresh") is True,
        )
    except SpeedtestTrackerError as exc:
        LOGGER.warning("Speedtest Tracker latest-result request failed: %s", exc)
        return Response({"data": None, "integration": integration})

    integration.update({"available": True, "cached": cached})
    return Response({"data": result, "integration": integration})
