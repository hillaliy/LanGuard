from django.conf import settings
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework.decorators import api_view

import logging
import threading

from .serializers import UserSerializer, DeviceSerializer
from .scan import scan
from .models import Device

LOGGER = logging.getLogger(__name__)

scan(settings.IP_RANGE)


def set_interval(func, sec, *args, **kwargs):
    def func_wrapper():
        func(*args, **kwargs)
        set_interval(func, sec, *args, **kwargs)

    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t


set_interval(scan, int(settings.INTERVAL) * 60, settings.IP_RANGE)


class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        # Call the serializer to validate and create the user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        LOGGER.info(f"New user created - {user.username}")
        # Generate a token for the newly created user
        token, created = Token.objects.get_or_create(user=user)

        # Return the username and token in the response
        return Response(
            {"username": user.username, "token": token.key},
            status=status.HTTP_201_CREATED,
        )


class UserLoginView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {"username": username, "token": token.key}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )


class UserLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logout(request)
        return Response({"message": "User logged out"}, status=status.HTTP_200_OK)


# Endpoint for managing devices (GET, PUT, DELETE)
@api_view(["GET", "PUT", "DELETE"])
def device(request):
    all_devices = Device.objects.all().count()
    online_devices = Device.objects.filter(online=True).count()
    offline_devices = Device.objects.filter(online=False).count()
    new_devices = Device.objects.filter(known=False).count()
    counters = {
        "all_devices": all_devices,
        "online_devices": online_devices,
        "offline_devices": offline_devices,
        "new_devices": new_devices,
    }

    # Handle GET request to retrieve devices
    if request.method == "GET":
        id_ = request.query_params.get("id", None)
        if not id_:
            devices = Device.objects.all()
            serializer = DeviceSerializer(devices, many=True)
            return Response(
                {
                    "data": serializer.data,
                    "counters": counters,
                },
                status=200,
            )
        else:
            device = Device.objects.get(pk=id_)
            serializer = DeviceSerializer(device)
            return Response(
                {
                    "data": serializer.data,
                },
                status=200,
            )

    # Handle PUT request to update device
    if request.method == "PUT":
        id_ = request.query_params.get("id", None)
        if not id_:
            return Response(
                {
                    "status": "Error",
                    "info": "Id is missing",
                },
                status=400,
            )
        device = Device.objects.get(pk=id_)
        serializer = DeviceSerializer(device, data=request.data, partial=True)
        if serializer.is_valid():
            device = serializer.save()
            LOGGER.info(
                f"Device ({device.id}) updated - Name: {device.name} / Icon: {device.icon} / Known: {device.known}"
            )
            return Response(
                {"status": "OK", "info": f"Device ({device.id}) updated seccessfully"},
                status=200,
            )
        else:
            return Response(
                {
                    "status": "Error",
                    "info": serializer.errors,
                },
                status=400,
            )

    # Handle DELETE request to delete device
    if request.method == "DELETE":
        id_ = request.query_params.get("id", None)
        if not id_:
            return Response(
                {
                    "status": "Error",
                    "info": "Id is missing",
                },
                status=400,
            )
        device = Device.objects.get(pk=id_)
        LOGGER.warning(
            f"Device ({device.id}) {device.name} - deleted successfully",
        )
        device.delete()
        return Response(
            {
                "status": "OK",
                "info": f"Device deleted successfully",
            },
            status=200,
        )
