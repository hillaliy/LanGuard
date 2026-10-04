import logging

import requests
from drf_spectacular.utils import OpenApiTypes, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError

from ..api import paginated_response, parse_datetime_param, parse_int_param
from ..models import AppSettings, NotificationDelivery
from ..notifications import (
    send_discord_test,
    send_ntfy_test,
    send_telegram_test,
    send_webhook_test,
)
from ..serializers import NotificationDeliverySerializer, NotificationTestSerializer
from ..user_messages import error_response, success_response

LOGGER = logging.getLogger(__name__)


@extend_schema(
    request=NotificationTestSerializer,
    responses=inline_serializer(
        name="NotificationTestResponse",
        fields={
            "data": inline_serializer(
                name="NotificationTestResponseData",
                fields={
                    "channel": serializers.CharField(),
                    "message": serializers.CharField(),
                },
            )
        },
    ),
)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def test_notification_channel(request):
    serializer = NotificationTestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    channel = data["channel"]

    try:
        if channel == NotificationDelivery.Channel.DISCORD:
            saved_webhook = AppSettings.load().discord_webhook
            send_discord_test(
                data.get("discord_webhook", "").strip() or saved_webhook
            )
        elif channel == NotificationDelivery.Channel.TELEGRAM:
            telegram_config = AppSettings.load()
            send_telegram_test(
                data.get("telegram_token", "").strip() or telegram_config.telegram_token,
                data["telegram_user_id"].strip(),
                data.get("telegram_api_url", telegram_config.telegram_api_url),
            )
        elif channel == NotificationDelivery.Channel.NTFY:
            send_ntfy_test(
                data["ntfy_server_url"].strip(),
                data["ntfy_topic"].strip(),
                data["ntfy_priority"],
            )
        elif channel == NotificationDelivery.Channel.WEBHOOK:
            saved_secret = AppSettings.load().webhook_secret
            send_webhook_test(
                data["webhook_url"].strip(),
                data.get("webhook_secret", "").strip() or saved_secret,
            )
    except requests.Timeout:
        return error_response(
            "Test notification failed",
            f"{channel.title()} did not respond before the timeout.",
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
    except requests.RequestException as exc:
        response_status = getattr(getattr(exc, "response", None), "status_code", None)
        LOGGER.warning(
            "Notification channel test failed: channel=%s status=%s",
            channel,
            response_status or "unavailable",
        )
        if channel == NotificationDelivery.Channel.TELEGRAM:
            if response_status == 400:
                detail = (
                    "Telegram rejected the chat. Check the chat ID and send /start "
                    "to the bot before testing. HTTP 400."
                )
            elif response_status == 401:
                detail = "Telegram rejected the bot token. HTTP 401."
            elif response_status == 403:
                detail = (
                    "Telegram cannot send to this chat. Check whether the bot is "
                    "blocked or lacks permission. HTTP 403."
                )
            elif response_status == 429:
                detail = "Telegram rate-limited the test notification. Try again later."
            elif response_status:
                detail = f"Telegram rejected the test notification. HTTP {response_status}."
            else:
                detail = "LanGuard could not connect to Telegram."
        else:
            detail = f"{channel.title()} rejected the test notification."
            if response_status:
                detail = f"{detail} HTTP {response_status}."
            else:
                detail = f"LanGuard could not connect to {channel.title()}."
        return error_response(
            "Test notification failed",
            detail,
            response_status=status.HTTP_502_BAD_GATEWAY,
        )

    message = f"Test notification sent to {channel.title()}."
    return success_response(
        {"channel": channel, "message": message},
        "Test notification sent",
        message,
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
        max_limit=500,
    )
