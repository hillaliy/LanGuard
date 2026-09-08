from rest_framework import permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiTypes

from .access_control import user_capabilities
from .homebox import HomeBoxClient, HomeBoxError, normalize_url
from .models import AppSettings


class HomeBoxConnectionSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=2048)
    api_token = serializers.CharField(max_length=512, required=False, allow_blank=True, write_only=True)


@extend_schema(request=HomeBoxConnectionSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_homebox(request):
    serializer = HomeBoxConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    config = AppSettings.load()
    data = serializer.validated_data
    try:
        if not data.get("api_token") and normalize_url(data["url"]) != config.homebox_url:
            return Response({"detail": "Enter an API key when testing a different HomeBox URL."}, status=400)
        HomeBoxClient(data["url"], data.get("api_token") or config.homebox_api_token).search()
    except HomeBoxError as exc:
        return Response({"detail": str(exc)}, status=502)
    return Response({"data": {"connected": True}})


class HomeBoxSearchSerializer(serializers.Serializer):
    q = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    page = serializers.IntegerField(min_value=1, max_value=10000, default=1)


@extend_schema(parameters=[HomeBoxSearchSerializer], responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def search_homebox(request):
    if not user_capabilities(request.user)["can_edit_devices"]:
        return Response({"detail": "You do not have permission to link devices."}, status=403)
    config = AppSettings.load()
    if not config.homebox_enabled:
        return Response({"detail": "HomeBox is disabled."}, status=400)
    serializer = HomeBoxSearchSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    try:
        result = HomeBoxClient(config.homebox_url, config.homebox_api_token).search(
            serializer.validated_data["q"], serializer.validated_data["page"]
        )
    except HomeBoxError as exc:
        return Response({"detail": str(exc)}, status=502)
    return Response({"data": result})
