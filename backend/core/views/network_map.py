from contextlib import contextmanager
from datetime import timedelta
import time

from django.db import IntegrityError, OperationalError, connection, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import APIException

from ..access_control import CanEditDevices, CanEditHomeMap
from ..database_writes import DatabaseWriteBusy, serialized_database_write, sqlite_busy, sqlite_busy_timeout
from ..models import NetworkLink, NetworkLinkDismissal, NetworkMapLayout, NetworkMapPreference, NetworkMapCommand, NetworkInternetConnection
from ..network_map_commands import command_handler, executing_command, resolve_command, command_allowed, command_data
from django.utils import timezone
from ..network_map import endpoint_registry, lldp_evidence, network_map_data
from ..network_map_preferences import save_network_map_preference
from ..serializers.network_map import (
    NetworkLayoutSerializer, NetworkLinkSerializer, NetworkRevisionSerializer, NetworkMapPreferenceSerializer,
    NetworkBulkLinksSerializer,
    NetworkInternetSerializer,
)
from ..user_messages import error_response, success_response

NETWORK_MAP_WRITE_WAIT_SECONDS = 2


class NetworkMapBusy(APIException):
    status_code = 503
    default_detail = "A scan or another update is using the database. No map changes were saved. Wait a moment and try again."
    default_code = "network_map_busy"
    wait = 1


@contextmanager
def network_map_write():
    if executing_command.get():
        yield
        return
    try:
        with serialized_database_write(timeout=NETWORK_MAP_WRITE_WAIT_SECONDS), sqlite_busy_timeout(500):
            yield
    except DatabaseWriteBusy:
        raise NetworkMapBusy from None
    except OperationalError as exc:
        if connection.vendor == "sqlite" and sqlite_busy(exc):
            raise NetworkMapBusy from exc
        raise


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
    data = network_map_data()
    value = NetworkMapPreference.objects.filter(user=request.user).values_list("show_lldp_suggestions", flat=True).first()
    data["preferences"] = {"show_lldp_suggestions": bool(value)}
    return Response({"data": data})


@extend_schema(methods=["PUT"], request=NetworkMapPreferenceSerializer, responses=NetworkMapPreferenceSerializer)
@extend_schema(methods=["GET"], responses=NetworkMapPreferenceSerializer)
@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAuthenticated])
def network_map_preferences(request):
    if request.method == "GET":
        value = NetworkMapPreference.objects.filter(user=request.user).values_list("show_lldp_suggestions", flat=True).first()
        return Response({"data": {"show_lldp_suggestions": bool(value)}})
    serializer = NetworkMapPreferenceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if not save_network_map_preference(request.user.pk, serializer.validated_data["show_lldp_suggestions"]):
        response = error_response("Database busy", "Your display preference could not be saved because the database is busy. Try again.", response_status=503)
        response["Retry-After"] = "1"
        return response
    return success_response(serializer.validated_data, "Preference saved", "Your Network Map display preference was saved.")


@extend_schema(request=NetworkLinkSerializer, responses=NetworkLinkSerializer)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
@command_handler
def network_links(request):
    with network_map_write(), transaction.atomic():
        serializer = NetworkLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_link(serializer)
    return success_response(serializer.data, "Connection saved", "The network connection was added.")


@extend_schema(request=NetworkBulkLinksSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
@command_handler
def network_links_bulk(request):
    batch = NetworkBulkLinksSerializer(data=request.data)
    batch.is_valid(raise_exception=True)
    with network_map_write(), transaction.atomic():
        pending, signatures = [], set()
        for index, body in enumerate(batch.validated_data["connections"]):
            serializer = NetworkLinkSerializer(data=body)
            if not serializer.is_valid():
                raise serializers.ValidationError({"connections": {index: serializer.errors}})
            signature = serializer.validated_data["signature"]
            if signature in signatures:
                raise serializers.ValidationError({"connections": {index: "Duplicate connection in this selection."}})
            signatures.add(signature)
            pending.append(serializer)
        for serializer in pending:
            save_link(serializer)
    return success_response({"connections": [serializer.data for serializer in pending]},
                            "Connections saved", f"{len(pending)} manual connections were added.")


@extend_schema(methods=["PUT"], request=NetworkLinkSerializer, responses=NetworkLinkSerializer)
@extend_schema(methods=["DELETE"], request=NetworkRevisionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
@command_handler
def network_link(request, link_id):
    version = NetworkRevisionSerializer(data=request.data)
    version.is_valid(raise_exception=True)
    with network_map_write(), transaction.atomic():
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
@command_handler
def network_layout(request):
    serializer = NetworkLayoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with network_map_write(), transaction.atomic():
        layout, _ = NetworkMapLayout.objects.select_for_update().get_or_create(pk=1)
        if layout.revision != serializer.validated_data["revision"]:
            return conflict()
        # Preserve positions for temporarily archived/merged devices so they can return unchanged.
        positions = {**layout.positions, **serializer.validated_data["positions"]}
        if len(positions) > 10000:
            return error_response("Layout full", "The map supports up to 10,000 saved positions.", response_status=400)
        layout.positions = positions
        layout.revision += 1
        layout.save(update_fields=["positions", "revision"])
    return success_response({"positions": layout.positions, "revision": layout.revision}, "Layout saved", "Network map positions were saved.")


@extend_schema(methods=['PUT'], request=NetworkInternetSerializer, responses=OpenApiTypes.OBJECT)
@extend_schema(methods=['DELETE'], request=NetworkRevisionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(['PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
@command_handler
def network_internet(request):
    serializer = NetworkInternetSerializer(data=request.data) if request.method == 'PUT' else NetworkRevisionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with network_map_write(), transaction.atomic():
        uplink = NetworkInternetConnection.objects.select_for_update().filter(pk=1).first()
        if uplink is None:
            if request.method == 'DELETE' or serializer.validated_data['revision'] != 0:
                return conflict()
            uplink = NetworkInternetConnection.objects.create(pk=1)
        if uplink.revision != serializer.validated_data['revision']:
            return conflict()
        if request.method == 'DELETE':
            uplink.enabled, uplink.target = False, None
        else:
            # Validate inventory again under the writer lock before assigning the interface.
            serializer = NetworkInternetSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            uplink.enabled = True
            uplink.target = serializer.validated_data['target']
            uplink.kind = serializer.validated_data['kind']
        uplink.revision += 1
        uplink.save(update_fields=['enabled', 'target', 'kind', 'revision'])
    return success_response({'revision': uplink.revision}, 'Internet connection saved', 'The Internet uplink was updated.')


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
@command_handler
def accept_network_suggestion(request, key):
    with network_map_write(), transaction.atomic():
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
@command_handler
def dismiss_network_suggestion(request, key):
    with network_map_write(), transaction.atomic():
        _, interfaces = endpoint_registry()
        evidence, _ = lldp_evidence(interfaces)
        if key not in evidence:
            return error_response("Observation unavailable", "Refresh the map before dismissing this observation.", response_status=409)
        NetworkLinkDismissal.objects.get_or_create(key=key)
    return success_response({}, "Suggestion dismissed", "The observation will not be suggested again unless restored.")


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated, CanEditDevices])
@command_handler
def restore_network_suggestions(request):
    with network_map_write(), transaction.atomic():
        NetworkLinkDismissal.objects.all().delete()
    return success_response({}, "Suggestions restored", "Dismissed LLDP observations can be suggested again.")


class MapCommandSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    path = serializers.CharField(max_length=160)
    method = serializers.ChoiceField(choices=["POST", "PUT", "DELETE"])
    body = serializers.JSONField(default=dict)

    def validate(self, attrs):
        if not resolve_command(attrs["path"], attrs["method"])[0]:
            raise serializers.ValidationError("Unsupported map operation.")
        body = attrs["body"]
        import json
        if not isinstance(body, dict) or len(json.dumps(body)) > 1_000_000:
            raise serializers.ValidationError("Invalid map operation body.")
        if attrs["path"] == "layout/":
            layout = NetworkLayoutSerializer(data=body)
            layout.is_valid(raise_exception=True)
            attrs["body"] = dict(layout.validated_data)
        elif attrs["path"] == "links/bulk/":
            batch = NetworkBulkLinksSerializer(data=body)
            batch.is_valid(raise_exception=True)
        return attrs


@extend_schema(methods=["POST"], request=MapCommandSerializer, responses={202: OpenApiTypes.OBJECT})
@extend_schema(methods=["GET"], responses=OpenApiTypes.OBJECT)
@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def network_map_commands(request):
    if request.method == "GET":
        owned = NetworkMapCommand.objects.filter(requested_by=request.user)
        pending = list(owned.filter(status="queued").order_by("-id")[:100])
        recent = list(owned.exclude(status="queued").filter(
            finished_at__gte=timezone.now() - timedelta(days=1)).order_by("-id")[:100])
        jobs = sorted(pending + recent, key=lambda job: job.pk, reverse=True)
        latest_layout = next((job.pk for job in jobs if job.path == "layout/"), None)
        return Response({"data": {"commands": [command_data(job, include_body=job.pk == latest_layout) for job in jobs]}})
    serializer = MapCommandSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    if not command_allowed(request.user, values["path"]):
        return error_response("Permission denied", "You cannot edit this part of the map.", response_status=403)
    # Intake deliberately bypasses the cooperative scan lock, not SQLite's transaction safety.
    for attempt in range(3):
        try:
            with sqlite_busy_timeout(250), transaction.atomic():
                job, created = NetworkMapCommand.objects.get_or_create(
                    requested_by=request.user, request_id=values["request_id"],
                    defaults={key: values[key] for key in ("path", "method", "body")})
                if created and NetworkMapCommand.objects.filter(requested_by=request.user, status="queued").count() > 100:
                    from rest_framework.exceptions import Throttled
                    raise Throttled(detail="You already have 100 changes waiting to save. Wait for them to finish before adding more.")
                if any(getattr(job, key) != values[key] for key in ("path", "method", "body")):
                    return error_response("Request conflict", "This request ID belongs to another change.", response_status=409)
            return Response({"data": {"command": command_data(job)}}, status=202)
        except OperationalError as exc:
            if not sqlite_busy(exc):
                raise
            if attempt < 2:
                time.sleep(0.05 * (attempt + 1))
    return error_response("Queue unavailable", "Your change could not reach the save queue. It has not been accepted.", response_status=503)
