import logging

from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


LOGGER = logging.getLogger(__name__)


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_status(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        LOGGER.exception("Database health check failed")
        return Response(
            {"status": "unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response({"status": "ok"}, status=status.HTTP_200_OK)
