from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Device, DevicePort, DockerContainer, DockerHost
from .serializers import (
    DockerContainerSerializer,
    DockerHostSerializer,
    DockerHostSummarySerializer,
)


def _observed_ports(device):
    return set(
        DevicePort.objects.filter(device=device, open=True).values_list("port", "protocol")
    )


@extend_schema(request=DockerHostSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["GET", "POST"])
@permission_classes([permissions.IsAdminUser])
def docker_hosts(request):
    if request.method == "GET":
        queryset = DockerHost.objects.select_related("device").prefetch_related("containers")
        return Response({"data": DockerHostSerializer(queryset, many=True).data})

    if DockerHost.objects.exists():
        return Response(
            {"error": "Docker inventory is already configured for this LanGuard instance."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = DockerHostSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    host = serializer.save()
    return Response({"data": DockerHostSerializer(host).data}, status=status.HTTP_201_CREATED)


@extend_schema(request=DockerHostSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["PUT", "DELETE"])
@permission_classes([permissions.IsAdminUser])
def docker_host_detail(request, host_id):
    host = get_object_or_404(DockerHost.objects.select_related("device"), pk=host_id)
    if request.method == "DELETE":
        host.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = DockerHostSerializer(host, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    host = serializer.save()
    return Response({"data": DockerHostSerializer(host).data})


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def sync_docker_host_view(request, host_id):
    host = get_object_or_404(DockerHost, pk=host_id)
    host.sync_requested = True
    host.save(update_fields=["sync_requested", "updated_at"])
    return Response(
        {
            "data": {"host": DockerHostSerializer(host).data},
            "notification": "Docker inventory sync queued. The scheduler will run it shortly.",
        }
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def docker_device_context(request):
    device = get_object_or_404(Device, pk=request.query_params.get("device"))
    host = DockerHost.objects.select_related("device").filter(device=device).first()
    host_containers = DockerContainer.objects.none()
    if host:
        host_containers = host.containers.filter(active=True).select_related("linked_device")
    linked_containers = DockerContainer.objects.filter(
        linked_device=device,
        active=True,
    ).select_related("host", "host__device", "linked_device")

    observed = _observed_ports(device)
    context = {"observed_ports": observed}
    linked_hosts = {
        container.host_id: container.host for container in linked_containers
    }
    return Response(
        {
            "data": {
                "host": DockerHostSummarySerializer(host).data if host else None,
                "containers": DockerContainerSerializer(
                    host_containers,
                    many=True,
                    context=context,
                ).data,
                "linked_containers": DockerContainerSerializer(
                    linked_containers,
                    many=True,
                    context=context,
                ).data,
                "linked_hosts": DockerHostSummarySerializer(
                    linked_hosts.values(),
                    many=True,
                ).data,
            }
        }
    )
