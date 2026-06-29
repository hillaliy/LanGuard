from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Device, DevicePort, NetworkEvent, NotificationDelivery, ScanRun


def capitalize_name(value):
    def capitalize_part(part):
        return part[:1].upper() + part[1:].lower() if part else part

    return " ".join(
        "-".join(capitalize_part(part) for part in word.split("-"))
        for word in (value or "").strip().split()
    )


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "password", "password_confirm")

    def create(self, validated_data):
        password = validated_data.pop("password")
        password_confirm = validated_data.pop("password_confirm")

        if password != password_confirm:
            raise serializers.ValidationError("Passwords do not match.")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user


class UserManagementSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password_confirm = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("id", "date_joined", "last_login")

    def validate(self, attrs):
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")
        if "first_name" in attrs:
            attrs["first_name"] = capitalize_name(attrs["first_name"])
        if "last_name" in attrs:
            attrs["last_name"] = capitalize_name(attrs["last_name"])

        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Password is required."})
        if password and password != password_confirm:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("password_confirm", None)
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        validated_data.pop("password_confirm", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class DevicePortSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevicePort
        fields = "__all__"
        read_only_fields = ("device", "firstseen", "lastseen")


class DeviceSerializer(serializers.ModelSerializer):
    open_ports = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = "__all__"

    @extend_schema_field(DevicePortSerializer(many=True))
    def get_open_ports(self, obj):
        return DevicePortSerializer(obj.ports.filter(open=True), many=True).data


class ScanRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanRun
        fields = "__all__"


class NetworkEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )

    class Meta:
        model = NetworkEvent
        fields = "__all__"


class NotificationDeliverySerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(
        source="get_channel_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = NotificationDelivery
        fields = "__all__"
