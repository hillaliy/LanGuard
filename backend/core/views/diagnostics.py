from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes

from ..diagnostics import build_diagnostics_report
from ..user_messages import success_response


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def export_diagnostics(request):
    generated_at = timezone.now()
    filename = f"languard-diagnostics-{generated_at.strftime('%Y%m%d-%H%M%S')}.json"
    return success_response(
        {
            "filename": filename,
            "report": build_diagnostics_report(),
        },
        "Diagnostics ready",
        "A sanitized diagnostics report was generated.",
    )
