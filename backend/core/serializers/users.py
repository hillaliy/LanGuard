from django.contrib.auth.models import User
from rest_framework import serializers

from ..access_control import (
    ACCESS_FIELDS,
    update_user_capabilities,
    user_capabilities,
)


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
    password_confirm = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )
    can_edit_devices = serializers.BooleanField(
        write_only=True,
        required=False,
        default=True,
    )
    can_edit_home_map = serializers.BooleanField(
        write_only=True,
        required=False,
        default=True,
    )
    can_run_scans = serializers.BooleanField(
        write_only=True,
        required=False,
        default=True,
    )

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
            "can_edit_devices",
            "can_edit_home_map",
            "can_run_scans",
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
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("password_confirm", None)
        capability_values = {
            field: validated_data.pop(field)
            for field in ACCESS_FIELDS
            if field in validated_data
        }
        user = User.objects.create_user(password=password, **validated_data)
        update_user_capabilities(user, capability_values)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        validated_data.pop("password_confirm", None)
        capability_values = {
            field: validated_data.pop(field)
            for field in ACCESS_FIELDS
            if field in validated_data
        }

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        update_user_capabilities(instance, capability_values)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(user_capabilities(instance))
        return data
