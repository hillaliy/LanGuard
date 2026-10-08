from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..api import paginated_payload, parse_bool_param
from ..datetime_utils import utc_isoformat
from ..models import AdGuardUnmatchedClient, AppSettings, Device, DeviceDNSActivity
from ..serializers.dns import (
    AdGuardUnmatchedClientSerializer,
    DeviceDNSActivitySerializer,
    GlobalDNSActivitySerializer,
)


def active_dns_provider(config):
    if config.technitium_enabled:
        return "technitium"
    if config.pihole_enabled:
        return "pihole"
    return "adguard"


def dns_integration_payload(config, *, include_web_url=False):
    if config.technitium_enabled:
        payload = {
            "provider": "technitium",
            "provider_name": "Technitium DNS Server",
            "enabled": True,
            "configured": bool(
                config.technitium_url and config.technitium_api_token
            ),
            "last_sync_at": utc_isoformat(config.technitium_last_sync_at),
            "last_error": config.technitium_last_error,
        }
        if include_web_url:
            payload["web_url"] = config.technitium_url
        return payload
    if config.pihole_enabled:
        payload = {
            "provider": "pihole",
            "provider_name": "Pi-hole",
            "enabled": True,
            "configured": bool(config.pihole_url and config.pihole_password),
            "last_sync_at": utc_isoformat(config.pihole_last_sync_at),
            "last_error": config.pihole_last_error,
        }
        if include_web_url:
            payload["web_url"] = config.pihole_url
        return payload
    payload = {
        "provider": "adguard",
        "provider_name": "AdGuard Home",
        "enabled": config.adguard_enabled,
        "configured": bool(
            config.adguard_url
            and (not config.adguard_username or config.adguard_password)
        ),
        "last_sync_at": utc_isoformat(config.adguard_last_sync_at),
        "last_error": config.adguard_last_error,
    }
    if include_web_url:
        payload["web_url"] = config.adguard_url
    return payload


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def device_dns_activity(request):
    id_ = request.query_params.get("id")
    if not id_:
        raise ValidationError({"id": "Device id is required."})

    target = get_object_or_404(Device, pk=id_)
    config = AppSettings.load()
    provider = active_dns_provider(config)
    base_queryset = DeviceDNSActivity.objects.filter(device=target, provider=provider)
    queryset = base_queryset
    search = str(request.query_params.get("search") or "").strip()
    blocked = parse_bool_param(request.query_params, "blocked")
    ordering = request.query_params.get("ordering", "-last_seen")
    allowed_ordering = {
        "domain",
        "-domain",
        "query_count",
        "-query_count",
        "blocked_count",
        "-blocked_count",
        "last_seen",
        "-last_seen",
    }
    if ordering not in allowed_ordering:
        raise ValidationError({"ordering": "Invalid DNS activity ordering."})
    if search:
        queryset = queryset.filter(domain__icontains=search)
    if blocked is True:
        queryset = queryset.filter(blocked_count__gt=0)
    elif blocked is False:
        queryset = queryset.filter(blocked_count=0)
    queryset = queryset.order_by(ordering, "domain", "query_type")

    totals = base_queryset.aggregate(
        total_queries=Sum("query_count"),
        blocked_queries=Sum("blocked_count"),
    )
    payload = paginated_payload(
        request,
        queryset,
        DeviceDNSActivitySerializer,
        default_limit=100,
        max_limit=500,
    )
    return Response(
        {
            **payload,
            "summary": {
                "unique_domains": base_queryset.values("domain").distinct().count(),
                "total_queries": totals["total_queries"] or 0,
                "blocked_queries": totals["blocked_queries"] or 0,
                "last_activity_at": utc_isoformat(
                    base_queryset.order_by("-last_seen")
                    .values_list("last_seen", flat=True)
                    .first()
                ),
            },
            "integration": dns_integration_payload(config),
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dns_activity(request):
    config = AppSettings.load()
    provider = active_dns_provider(config)
    base_queryset = DeviceDNSActivity.objects.filter(provider=provider).select_related(
        "device"
    )
    queryset = base_queryset
    search = str(request.query_params.get("search") or "").strip()
    blocked = parse_bool_param(request.query_params, "blocked")
    ordering = request.query_params.get("ordering", "-last_seen")
    allowed_ordering = {
        "domain",
        "-domain",
        "query_count",
        "-query_count",
        "blocked_count",
        "-blocked_count",
        "last_seen",
        "-last_seen",
        "device__name",
        "-device__name",
    }
    if ordering not in allowed_ordering:
        raise ValidationError({"ordering": "Invalid DNS activity ordering."})
    if search:
        queryset = queryset.filter(
            Q(domain__icontains=search)
            | Q(device__name__icontains=search)
            | Q(device__ip__icontains=search)
            | Q(device__mac__icontains=search)
        )
    if blocked is True:
        queryset = queryset.filter(blocked_count__gt=0)
    elif blocked is False:
        queryset = queryset.filter(blocked_count=0)
    queryset = queryset.order_by(ordering, "domain", "query_type")

    totals = base_queryset.aggregate(
        total_queries=Sum("query_count"),
        blocked_queries=Sum("blocked_count"),
    )
    payload = paginated_payload(
        request,
        queryset,
        GlobalDNSActivitySerializer,
        default_limit=100,
        max_limit=500,
    )
    return Response(
        {
            **payload,
            "summary": {
                "unique_domains": base_queryset.values("domain").distinct().count(),
                "total_queries": totals["total_queries"] or 0,
                "blocked_queries": totals["blocked_queries"] or 0,
                "active_devices": base_queryset.values("device_id").distinct().count(),
                "last_activity_at": utc_isoformat(
                    base_queryset.order_by("-last_seen")
                    .values_list("last_seen", flat=True)
                    .first()
                ),
            },
            "integration": dns_integration_payload(config, include_web_url=True),
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dns_unmatched_clients(request):
    config = AppSettings.load()
    provider = active_dns_provider(config)
    base_queryset = AdGuardUnmatchedClient.objects.filter(provider=provider)
    queryset = base_queryset
    search = str(request.query_params.get("search") or "").strip()
    ordering = request.query_params.get("ordering", "-last_seen")
    allowed_ordering = {
        "client",
        "-client",
        "query_count",
        "-query_count",
        "blocked_count",
        "-blocked_count",
        "last_seen",
        "-last_seen",
    }
    if ordering not in allowed_ordering:
        raise ValidationError({"ordering": "Invalid unmatched client ordering."})
    if search:
        queryset = queryset.filter(
            Q(client__icontains=search) | Q(last_domain__icontains=search)
        )
    queryset = queryset.order_by(ordering, "client")
    totals = base_queryset.aggregate(
        total_queries=Sum("query_count"),
        blocked_queries=Sum("blocked_count"),
    )
    payload = paginated_payload(
        request,
        queryset,
        AdGuardUnmatchedClientSerializer,
        default_limit=100,
        max_limit=500,
    )
    return Response(
        {
            **payload,
            "summary": {
                "clients": base_queryset.count(),
                "total_queries": totals["total_queries"] or 0,
                "blocked_queries": totals["blocked_queries"] or 0,
                "last_activity_at": utc_isoformat(
                    base_queryset.order_by("-last_seen")
                    .values_list("last_seen", flat=True)
                    .first()
                ),
            },
        },
        status=status.HTTP_200_OK,
    )
