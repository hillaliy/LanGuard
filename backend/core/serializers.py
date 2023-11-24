from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Device


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


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = "__all__"
