import ipaddress
import json
import urllib.error
import urllib.request

from drf_spectacular.utils import OpenApiTypes, extend_schema, inline_serializer
from rest_framework import status, generics, permissions
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404

import logging

from .serializers import (
    AppSettingsSerializer,
    DeviceSerializer,
    NetworkEventSerializer,
    NotificationDeliverySerializer,
    ScanRunSerializer,
    UserManagementSerializer,
    UserSerializer,
)
from .models import (
    AppSettings,
    Device,
    DevicePort,
    NetworkEvent,
    NotificationDelivery,
    ScanRun,
)
from .api import (
    paginated_response,
    paginated_payload,
    parse_bool_param,
    parse_datetime_param,
    parse_int_param,
)
from .scan import scan, validate_ip_range

LOGGER = logging.getLogger(__name__)


DEVICE_ORDERING_FIELDS = {
    "name": ("name", "ip", "id"),
    "-name": ("-name", "ip", "id"),
}


def ip_sort_key(device):
    try:
        address = ipaddress.ip_address(device.ip)
    except ValueError:
        return (1, device.ip, device.name.lower(), device.id)
    return (0, address.version, int(address), device.name.lower(), device.id)


def paginated_device_payload(request, devices):
    ordering = request.query_params.get("ordering")
    if ordering in DEVICE_ORDERING_FIELDS:
        devices = devices.order_by(*DEVICE_ORDERING_FIELDS[ordering])
        return paginated_payload(
            request,
            devices,
            DeviceSerializer,
            default_limit=10,
            max_limit=100,
        )
    if ordering in {"ip", "-ip"}:
        limit = parse_int_param(request.query_params, "limit", default=10, minimum=1, maximum=100)
        offset = parse_int_param(request.query_params, "offset", default=0, minimum=0)
        sorted_devices = sorted(devices, key=ip_sort_key, reverse=ordering == "-ip")
        total = len(sorted_devices)
        next_offset = offset + limit if offset + limit < total else None
        previous_offset = max(offset - limit, 0) if offset > 0 else None
        return {
            "data": DeviceSerializer(sorted_devices[offset : offset + limit], many=True).data,
            "pagination": {
                "count": total,
                "limit": limit,
                "offset": offset,
                "next_offset": next_offset,
                "previous_offset": previous_offset,
            },
        }
    if ordering:
        raise ValidationError({"ordering": "Must be one of: name, -name, ip, -ip."})
    return paginated_payload(
        request,
        devices,
        DeviceSerializer,
        default_limit=10,
        max_limit=100,
    )


def auth_payload(user, token):
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "token": token.key,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


def active_staff_count():
    return User.objects.filter(is_active=True, is_staff=True).count()


def staff_count():
    return User.objects.filter(is_staff=True).count()


def fetch_latest_version():
    if not settings.LATEST_VERSION_URL:
        return None

    request = urllib.request.Request(
        settings.LATEST_VERSION_URL,
        headers={"User-Agent": "LanGuard"},
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=settings.VERSION_CHECK_TIMEOUT,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        LOGGER.info("Latest version check failed: %s", exc)
        return None

    latest_version = payload.get("version")
    if isinstance(latest_version, str) and latest_version.strip():
        return latest_version.strip()
    return None


@extend_schema(
    responses=inline_serializer(
        name="VersionStatusResponse",
        fields={
            "data": inline_serializer(
                name="VersionStatus",
                fields={
                    "current_version": serializers.CharField(),
                    "latest_version": serializers.CharField(allow_null=True),
                    "check_interval_seconds": serializers.IntegerField(),
                },
            )
        },
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def version_status(request):
    latest_version = fetch_latest_version()
    config = AppSettings.load()
    return Response(
        {
            "data": {
                "current_version": settings.APP_VERSION,
                "latest_version": latest_version,
                "check_interval_seconds": config.version_check_interval,
            }
        }
    )


@extend_schema(
    request=AppSettingsSerializer,
    responses=AppSettingsSerializer,
)
@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAdminUser])
def app_settings(request):
    config = AppSettings.load()

    if request.method == "GET":
        return Response({"data": AppSettingsSerializer(config).data})

    serializer = AppSettingsSerializer(config, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({"data": AppSettingsSerializer(config).data})


@extend_schema(
    responses=inline_serializer(
        name="SetupStatusResponse",
        fields={"registration_open": serializers.BooleanField()},
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def setup_status(request):
    return Response(
        {"registration_open": not User.objects.exists()},
        status=status.HTTP_200_OK,
    )


@permission_classes([AllowAny])
class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        if User.objects.exists():
            return Response(
                {"error": "Registration is only available before the first user exists."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Call the serializer to validate and create the user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        LOGGER.info(f"New user created - {user.username}")
        # Generate a token for the newly created user
        token, created = Token.objects.get_or_create(user=user)

        # Return the username and token in the response
        return Response(auth_payload(user, token), status=status.HTTP_201_CREATED)


@permission_classes([AllowAny])
class UserLoginView(APIView):
    @extend_schema(
        request=inline_serializer(
            name="UserLoginRequest",
            fields={
                "username": serializers.CharField(),
                "password": serializers.CharField(write_only=True),
            },
        ),
        responses=inline_serializer(
            name="AuthTokenResponse",
            fields={
                "username": serializers.CharField(),
                "token": serializers.CharField(),
            },
        ),
    )
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            token, created = Token.objects.get_or_create(user=user)
            return Response(auth_payload(user, token), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )


@permission_classes([permissions.IsAuthenticated])
class UserEditView(generics.UpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        # Get the current authenticated user
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class UserLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=None,
        responses=inline_serializer(
            name="MessageResponse",
            fields={"message": serializers.CharField()},
        ),
    )
    def post(self, request, *args, **kwargs):
        logout(request)
        return Response({"message": "User logged out"}, status=status.HTTP_200_OK)


@extend_schema(
    methods=["GET"],
    responses=UserManagementSerializer(many=True),
)
@extend_schema(
    methods=["POST"],
    request=UserManagementSerializer,
    responses=UserManagementSerializer,
)
@extend_schema(
    methods=["PUT"],
    request=UserManagementSerializer,
    responses=UserManagementSerializer,
)
@extend_schema(
    methods=["DELETE"],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET", "POST", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def users(request):
    is_staff = request.user.is_staff

    if request.method == "GET":
        queryset = User.objects.order_by("username") if is_staff else User.objects.filter(pk=request.user.pk)
        serializer = UserManagementSerializer(
            queryset,
            many=True,
        )
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

    if request.method == "POST":
        if not is_staff:
            return Response(
                {"detail": "You do not have permission to create users."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = UserManagementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        LOGGER.info("User created - %s", user.username)
        return Response(
            {"data": UserManagementSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )

    id_ = parse_int_param(request.query_params, "id", default=0, minimum=1)
    user = get_object_or_404(User, pk=id_)
    if not is_staff and user.pk != request.user.pk:
        return Response(
            {"detail": "You do not have permission to edit this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "PUT":
        data = request.data.copy()
        if not is_staff:
            data.pop("is_staff", None)
            data.pop("is_superuser", None)
            data.pop("is_active", None)
        serializer = UserManagementSerializer(user, data=request.data, partial=True)
        if not is_staff:
            serializer = UserManagementSerializer(user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        next_is_staff = serializer.validated_data.get("is_staff", user.is_staff)
        next_is_active = serializer.validated_data.get("is_active", user.is_active)
        if user.is_staff and user.is_active and not (next_is_staff and next_is_active):
            if active_staff_count() <= 1:
                return Response(
                    {"error": "Cannot remove the last active admin user."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        user = serializer.save()
        LOGGER.info("User updated - %s", user.username)
        return Response(
            {"data": UserManagementSerializer(user).data},
            status=status.HTTP_200_OK,
        )

    if not is_staff:
        return Response(
            {"detail": "You do not have permission to delete users."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if User.objects.count() <= 1:
        return Response(
            {"error": "Cannot delete the last user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.is_staff and staff_count() <= 1:
        return Response(
            {"error": "Cannot delete the last admin user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.is_staff and user.is_active and active_staff_count() <= 1:
        return Response(
            {"error": "Cannot delete the last active admin user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    username = user.username
    user.delete()
    LOGGER.info("User deleted - %s", username)
    return Response({"status": "OK", "info": "User deleted."}, status=status.HTTP_200_OK)


# Endpoint for managing devices (GET, PUT, DELETE)
@extend_schema(
    methods=["GET"],
    responses=OpenApiTypes.OBJECT,
)
@extend_schema(
    methods=["PUT"],
    request=DeviceSerializer,
    responses=OpenApiTypes.OBJECT,
)
@extend_schema(
    methods=["DELETE"],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def device(request):
    all_devices = Device.objects.all().count()
    online_devices = Device.objects.exclude(status=Device.Status.OFFLINE).count()
    offline_devices = Device.objects.filter(status=Device.Status.OFFLINE).count()
    new_devices = Device.objects.filter(known=False).count()
    open_ports = DevicePort.objects.filter(open=True).count()
    counters = {
        "all_devices": all_devices,
        "online_devices": online_devices,
        "offline_devices": offline_devices,
        "new_devices": new_devices,
        "open_ports": open_ports,
    }

    # Handle GET request to retrieve devices
    if request.method == "GET":
        id_ = request.query_params.get("id", None)
        if not id_:
            devices = Device.objects.prefetch_related("ports").all()
            online = parse_bool_param(request.query_params, "online")
            device_status = request.query_params.get("status")
            known = parse_bool_param(request.query_params, "known")
            search = request.query_params.get("search")
            open_port = request.query_params.get("open_port")

            if device_status:
                if device_status not in Device.Status.values:
                    raise ValidationError({"status": "Invalid device status."})
                devices = devices.filter(status=device_status)
            elif online is not None:
                devices = devices.filter(online=online)
            if known is not None:
                devices = devices.filter(known=known)
            if search:
                devices = devices.filter(
                    Q(name__icontains=search)
                    | Q(ip__icontains=search)
                    | Q(mac__icontains=search)
                )
            if open_port:
                port = parse_int_param(
                    request.query_params,
                    "open_port",
                    default=open_port,
                    minimum=1,
                    maximum=65535,
                )
                devices = devices.filter(ports__port=port, ports__open=True).distinct()

            payload = paginated_device_payload(request, devices)
            return Response(
                {
                    "data": payload["data"],
                    "counters": counters,
                    "pagination": payload["pagination"],
                },
                status=status.HTTP_200_OK,
            )
        else:
            device = get_object_or_404(Device, pk=id_)
            serializer = DeviceSerializer(device)
            return Response(
                {
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

    # Handle PUT request to update device
    if request.method == "PUT":
        id_ = request.query_params.get("id", None)
        if not id_:
            return Response(
                {
                    "status": "Error",
                    "info": "Id is missing",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        device = get_object_or_404(Device, pk=id_)
        serializer = DeviceSerializer(device, data=request.data, partial=True)
        if serializer.is_valid():
            device = serializer.save()
            LOGGER.info(
                f"Device ({device.id}) updated - Name: {device.name} / Icon: {device.icon} / Known: {device.known}"
            )
            return Response(
                {"status": "OK", "info": f"Device ({device.id}) updated successfully"},
                status=status.HTTP_202_ACCEPTED,
            )
        else:
            return Response(
                {
                    "status": "Error",
                    "info": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Handle DELETE request to delete device
    if request.method == "DELETE":
        id_ = request.query_params.get("id", None)
        if not id_:
            return Response(
                {
                    "status": "Error",
                    "info": "Id is missing",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        device = get_object_or_404(Device, pk=id_)
        LOGGER.warning(
            f"Device ({device.id}) {device.name} - deleted successfully",
        )
        device.delete()
        return Response(
            {
                "status": "OK",
                "info": "Device deleted successfully",
            },
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(
    request=inline_serializer(
        name="ScanNowRequest",
        fields={
            "ip_range": serializers.CharField(required=False),
        },
    ),
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def scan_now(request):
    ip_range = request.data.get("ip_range") or AppSettings.load().ip_range
    try:
        ip_range = validate_ip_range(ip_range)
    except ValueError as exc:
        raise ValidationError({"ip_range": str(exc)}) from exc

    try:
        scan_run = scan(ip_range)
    except Exception as exc:
        LOGGER.exception("Scan failed for %s", ip_range)
        failed_scan = ScanRun.objects.filter(ip_range=ip_range).first()
        message = str(exc)
        if "Permission denied" in message and "/dev/bpf" in message:
            message = (
                "Network scan needs packet-capture permissions. Run the scanner "
                "with sudo locally or use the privileged Docker scanner service."
            )
        return Response(
            {
                "status": "Error",
                "info": message,
                "data": ScanRunSerializer(failed_scan).data if failed_scan else None,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {
            "status": "OK",
            "info": f"Scan completed for {ip_range}",
            "data": ScanRunSerializer(scan_run).data,
        },
        status=status.HTTP_202_ACCEPTED,
    )


@extend_schema(responses=ScanRunSerializer(many=True))
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def scan_runs(request):
    runs = ScanRun.objects.all()
    scan_status = request.query_params.get("status")
    ip_range = request.query_params.get("ip_range")
    started_after = parse_datetime_param(request.query_params, "started_after")
    started_before = parse_datetime_param(request.query_params, "started_before")

    if scan_status:
        if scan_status not in ScanRun.Status.values:
            raise ValidationError({"status": "Invalid scan status."})
        runs = runs.filter(status=scan_status)
    if ip_range:
        runs = runs.filter(ip_range=ip_range)
    if started_after:
        runs = runs.filter(started_at__gte=started_after)
    if started_before:
        runs = runs.filter(started_at__lte=started_before)

    return paginated_response(
        request,
        runs,
        ScanRunSerializer,
        default_limit=25,
        max_limit=100,
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def scan_status(request):
    latest_scan = ScanRun.objects.exclude(status=ScanRun.Status.RUNNING).first()
    active_scan = ScanRun.objects.filter(status=ScanRun.Status.RUNNING).first()
    return Response(
        {
            "data": ScanRunSerializer(latest_scan).data if latest_scan else None,
            "active_scan": ScanRunSerializer(active_scan).data if active_scan else None,
            "counters": {
                "all_devices": Device.objects.count(),
                "online_devices": Device.objects.exclude(status=Device.Status.OFFLINE).count(),
                "offline_devices": Device.objects.filter(status=Device.Status.OFFLINE).count(),
                "open_ports": DevicePort.objects.filter(open=True).count(),
                "unnotified_events": NetworkEvent.objects.filter(notified=False).count(),
            },
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(responses=NetworkEventSerializer(many=True))
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def events(request):
    event_type = request.query_params.get("event_type")
    notified = parse_bool_param(request.query_params, "notified")
    created_after = parse_datetime_param(request.query_params, "created_after")
    created_before = parse_datetime_param(request.query_params, "created_before")
    device_id = request.query_params.get("device")
    scan_run_id = request.query_params.get("scan_run")

    queryset = NetworkEvent.objects.select_related("device", "device_port", "scan_run")
    if event_type:
        if event_type not in NetworkEvent.EventType.values:
            raise ValidationError({"event_type": "Invalid event type."})
        queryset = queryset.filter(event_type=event_type)
    if notified is not None:
        queryset = queryset.filter(notified=notified)
    if created_after:
        queryset = queryset.filter(created_at__gte=created_after)
    if created_before:
        queryset = queryset.filter(created_at__lte=created_before)
    if device_id:
        queryset = queryset.filter(
            device_id=parse_int_param(request.query_params, "device", 0, 1)
        )
    if scan_run_id:
        queryset = queryset.filter(
            scan_run_id=parse_int_param(request.query_params, "scan_run", 0, 1)
        )

    return paginated_response(
        request,
        queryset,
        NetworkEventSerializer,
        default_limit=50,
        max_limit=200,
    )


@extend_schema(responses=NotificationDeliverySerializer(many=True))
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def notifications(request):
    channel = request.query_params.get("channel")
    delivery_status = request.query_params.get("status")
    event_id = request.query_params.get("event")
    created_after = parse_datetime_param(request.query_params, "created_after")
    created_before = parse_datetime_param(request.query_params, "created_before")

    queryset = NotificationDelivery.objects.select_related("event")
    if channel:
        if channel not in NotificationDelivery.Channel.values:
            raise ValidationError({"channel": "Invalid notification channel."})
        queryset = queryset.filter(channel=channel)
    if delivery_status:
        if delivery_status not in NotificationDelivery.Status.values:
            raise ValidationError({"status": "Invalid notification status."})
        queryset = queryset.filter(status=delivery_status)
    if event_id:
        queryset = queryset.filter(
            event_id=parse_int_param(request.query_params, "event", 0, 1)
        )
    if created_after:
        queryset = queryset.filter(created_at__gte=created_after)
    if created_before:
        queryset = queryset.filter(created_at__lte=created_before)

    return paginated_response(
        request,
        queryset,
        NotificationDeliverySerializer,
        default_limit=50,
        max_limit=200,
    )


@extend_schema(responses=DeviceSerializer(many=True))
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def export_db(request):
    data = DeviceSerializer(Device.objects.all(), many=True).data
    return JsonResponse(data, safe=False)


@extend_schema(
    request=DeviceSerializer(many=True),
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def import_db(request):
    data = request.data
    serializer = DeviceSerializer(data=data, many=True)

    if serializer.is_valid():
        serializer.save()
        return Response(
            {"status": "OK", "info": "Import successful"},
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
