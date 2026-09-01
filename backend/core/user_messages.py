from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


GENERIC_SERVER_ERROR = (
    "LanGuard could not complete this request. Try again, and export a diagnostics "
    "report from Settings if the problem continues."
)


def notification(title, message):
    return {"title": title, "message": message}


def success_response(data, title, message, *, response_status=status.HTTP_200_OK, **extra):
    return Response(
        {
            "data": data,
            "notification": notification(title, message),
            **extra,
        },
        status=response_status,
    )


def error_response(title, message, *, response_status, **extra):
    return Response(
        {
            "detail": message,
            "notification": notification(title, message),
            **extra,
        },
        status=response_status,
    )


def external_service_error(service, exc=None):
    response_status = getattr(getattr(exc, "response", None), "status_code", None)
    if response_status in {401, 403}:
        return f"{service} rejected the configured credentials or access permissions."
    if response_status == 404:
        return f"{service} could not find the requested API endpoint. Check the service URL."
    if response_status == 429:
        return f"{service} is rate limiting requests. Try again later."
    if response_status:
        return f"{service} rejected the request (HTTP {response_status})."
    return f"LanGuard could not connect to {service}. Check that the service is reachable."


def scan_error_message(exc=None):
    message = str(exc or "")
    if "Permission denied" in message and "/dev/bpf" in message:
        return (
            "Network scan needs packet-capture permissions. Run the scanner with sudo "
            "locally or use the privileged Docker scanner service."
        )
    return (
        "The network scan could not be completed. Check the scanner container and export "
        "a diagnostics report if the problem continues."
    )


def stored_error_message(kind, value):
    if not value:
        return ""
    messages = {
        "adguard": "The last AdGuard Home synchronization failed. Test the connection and try again.",
        "notification": "The notification could not be delivered. Check the channel configuration.",
        "scan": "The network scan could not be completed. Check the scanner container.",
    }
    return messages.get(kind, GENERIC_SERVER_ERROR)


def _message_from_data(data):
    if not isinstance(data, dict):
        return "The request could not be completed."
    value = data.get("detail") or data.get("error") or data.get("info")
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for field_value in value.values():
            if isinstance(field_value, (list, tuple)) and field_value:
                field_value = field_value[0]
            if isinstance(field_value, str) and field_value.strip():
                return field_value.strip()
    for value in data.values():
        if isinstance(value, (list, tuple)) and value:
            value = value[0]
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "The request could not be completed."


def _error_title(status_code):
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "Check the entered information"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "Sign in required"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "Permission denied"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "Not found"
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return "Too many requests"
    if status_code >= 500:
        return "Server error"
    return "Request failed"


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    message = _message_from_data(response.data)
    if response.status_code >= 500:
        message = GENERIC_SERVER_ERROR
    response.data["notification"] = notification(
        _error_title(response.status_code),
        message,
    )
    return response


class ApiMessageMiddleware:
    """Add a safe notification envelope to explicit DRF error responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.rstrip("/").endswith("/health"):
            return response
        data = getattr(response, "data", None)
        if response.status_code < 400 or not isinstance(data, dict):
            return response
        if "notification" in data:
            return response

        message = _message_from_data(data)
        if response.status_code >= 500:
            message = GENERIC_SERVER_ERROR
            response.data = {"detail": message}
        response.data["notification"] = notification(
            _error_title(response.status_code),
            message,
        )
        return response
