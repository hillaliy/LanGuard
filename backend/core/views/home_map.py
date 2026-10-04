from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..access_control import CanEditHomeMap
from ..models import AppSettings
from ..serializers.home_map import HomeMapLayoutSerializer
from ..user_messages import success_response


@extend_schema(methods=["GET"], responses=HomeMapLayoutSerializer)
@extend_schema(
    methods=["PUT"],
    request=HomeMapLayoutSerializer,
    responses=HomeMapLayoutSerializer,
)
@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAuthenticated, CanEditHomeMap])
def home_map_layout(request):
    config = AppSettings.load()

    if request.method == "GET":
        return Response({"data": {"layout": config.home_map_layout or {}}})

    serializer = HomeMapLayoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    config.home_map_layout = serializer.validated_data["layout"]
    config.save(update_fields=["home_map_layout", "updated_at"])
    return success_response(
        {"layout": config.home_map_layout or {}},
        "Layout saved",
        "Home map layout was updated.",
    )
