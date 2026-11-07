from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..access_control import CanEditDevices, CanEditHomeMap
from ..database_writes import serialized_database_write
from ..models import NetworkLink, NetworkLinkDismissal, NetworkMapLayout
from ..network_map import endpoint_registry, lldp_evidence, network_map_data
from ..serializers.network_map import NetworkLayoutSerializer, NetworkLinkSerializer, NetworkRevisionSerializer
from ..user_messages import error_response, success_response


def conflict():
    return error_response("Map changed", "Another user changed this item. Refresh before saving again.", response_status=409)


def save_link(serializer, **kwargs):
    try:
        with transaction.atomic():
            return serializer.save(**kwargs)
    except IntegrityError as exc:
        raise serializers.ValidationError("This connection already exists or its endpoints have changed. Refresh the map.") from exc


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def network_map(request):
    return Response({"data": network_map_data()})


@extend_schema(request=NetworkLinkSerializer, responses=NetworkLinkSerializer)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
def network_links(request):
    with serialized_database_write(), transaction.atomic():
        serializer = NetworkLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_link(serializer)
    return success_response(serializer.data, "Connection saved", "The network connection was added.")


@extend_schema(methods=["PUT"], request=NetworkLinkSerializer, responses=NetworkLinkSerializer)
@extend_schema(methods=["DELETE"], request=NetworkRevisionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
def network_link(request, link_id):
    version = NetworkRevisionSerializer(data=request.data)
    version.is_valid(raise_exception=True)
    with serialized_database_write(), transaction.atomic():
        link = get_object_or_404(NetworkLink.objects.select_for_update(), pk=link_id)
        if version.validated_data["revision"] != link.revision:
            return conflict()
        if request.method == "DELETE":
            if link.evidence_key:
                NetworkLinkDismissal.objects.get_or_create(key=link.evidence_key)
            link.delete()
            return success_response({}, "Connection deleted", "The saved connection was removed.")
        serializer = NetworkLinkSerializer(link, data=request.data)
        serializer.is_valid(raise_exception=True)
        save_link(serializer, origin="manual", evidence_key="", observed_at=None, revision=link.revision + 1)
    return success_response(serializer.data, "Connection saved", "The network connection was updated.")


@extend_schema(request=NetworkLayoutSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated, CanEditHomeMap])
def network_layout(request):
    serializer = NetworkLayoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with serialized_database_write(), transaction.atomic():
        layout, _ = NetworkMapLayout.objects.select_for_update().get_or_create(pk=1)
        if layout.revision != serializer.validated_data["revision"]:
            return conflict()
        # Preserve positions for temporarily archived/merged devices so they can return unchanged.
        layout.positions = {**layout.positions, **serializer.validated_data["positions"]}
        if len(layout.positions) > 10000:
            return error_response("Layout full", "The map supports up to 10,000 saved positions.", response_status=400)
        layout.revision += 1
        layout.save(update_fields=["positions", "revision"])
    return success_response({"positions": layout.positions, "revision": layout.revision}, "Layout saved", "Network map positions were saved.")


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
def accept_network_suggestion(request, key):
    with serialized_database_write(), transaction.atomic():
        _, interfaces = endpoint_registry()
        evidence, _ = lldp_evidence(interfaces)
        item = evidence.get(key)
        if not item:
            return error_response("Observation unavailable", "This LLDP observation is no longer available. Refresh the map.", response_status=409)
        serializer = NetworkLinkSerializer(data={name: item[name] for name in ("source", "target", "source_port", "target_port", "kind")})
        serializer.is_valid(raise_exception=True)
        save_link(serializer, origin="lldp", evidence_key=key, observed_at=item["observed_at"])
        NetworkLinkDismissal.objects.filter(pk=key).delete()
    return success_response(serializer.data, "Connection confirmed", "The LLDP-reported connection was added to the map.")


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
def dismiss_network_suggestion(request, key):
    with serialized_database_write():
        _, interfaces = endpoint_registry()
        evidence, _ = lldp_evidence(interfaces)
        if key not in evidence:
            return error_response("Observation unavailable", "Refresh the map before dismissing this observation.", response_status=409)
        NetworkLinkDismissal.objects.get_or_create(key=key)
    return success_response({}, "Suggestion dismissed", "The observation will not be suggested again unless restored.")


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
def restore_network_suggestions(request):
    with serialized_database_write():
        NetworkLinkDismissal.objects.all().delete()
    return success_response({}, "Suggestions restored", "Dismissed LLDP observations can be suggested again.")
