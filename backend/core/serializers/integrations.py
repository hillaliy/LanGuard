
from rest_framework import serializers

from ..models import (
    AppSettings,
)



class AdGuardConnectionSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)
    username = serializers.CharField(required=False, allow_blank=True, max_length=255)
    password = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        username = attrs.get("username", "").strip()
        password = attrs.get("password", "")
        if username and not password:
            saved = AppSettings.load()
            if not saved.adguard_password:
                raise serializers.ValidationError(
                    {"password": "Enter the AdGuard Home password."}
                )
        return attrs


class PiHoleConnectionSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)
    password = serializers.CharField(required=False, allow_blank=True, max_length=255)
    dhcp_enabled = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        saved = AppSettings.load()
        if not attrs.get("password") and not saved.pihole_password:
            raise serializers.ValidationError(
                {"password": "Enter a Pi-hole application password."}
            )
        return attrs


class TechnitiumConnectionSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)
    api_token = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=512,
        trim_whitespace=True,
    )
    dhcp_enabled = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        saved = AppSettings.load()
        if not attrs.get("api_token") and not saved.technitium_api_token:
            raise serializers.ValidationError(
                {"api_token": "Enter a Technitium API token."}
            )
        return attrs


class SpeedtestTrackerConnectionSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)
    api_token = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=512,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        saved = AppSettings.load()
        if not attrs.get("api_token") and not saved.speedtest_tracker_api_token:
            raise serializers.ValidationError(
                {"api_token": "Enter a Speedtest Tracker API token."}
            )
        return attrs
