import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..access_control import ACCESS_FIELDS, user_capabilities
from ..api import parse_int_param
from ..serializers import UserManagementSerializer, UserSerializer
from ..user_messages import success_response

LOGGER = logging.getLogger(__name__)

def auth_payload(user, token, *, account_created=False):
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "token": token.key,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        **user_capabilities(user),
        "notification": {
            "title": "Account created" if account_created else "Signed in",
            "message": "Your LanGuard session is ready.",
        },
    }


def active_staff_count():
    return User.objects.filter(is_active=True, is_staff=True).count()


def staff_count():
    return User.objects.filter(is_staff=True).count()

@extend_schema(
    responses=inline_serializer(
        name="SetupStatusResponse",
        fields={"registration_open": serializers.BooleanField()},
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def setup_status(request):
    return Response(
        {"registration_open": not User.objects.exists()},
        status=status.HTTP_200_OK,
    )


@permission_classes([AllowAny])
class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        if User.objects.exists():
            return Response(
                {"error": "Registration is only available before the first user exists."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Call the serializer to validate and create the user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        LOGGER.info(f"New user created - {user.username}")
        # Generate a token for the newly created user
        token, created = Token.objects.get_or_create(user=user)

        # Return the username and token in the response
        return Response(
            auth_payload(user, token, account_created=True),
            status=status.HTTP_201_CREATED,
        )


@permission_classes([AllowAny])
class UserLoginView(APIView):
    @extend_schema(
        request=inline_serializer(
            name="UserLoginRequest",
            fields={
                "username": serializers.CharField(),
                "password": serializers.CharField(write_only=True),
            },
        ),
        responses=inline_serializer(
            name="AuthTokenResponse",
            fields={
                "username": serializers.CharField(),
                "token": serializers.CharField(),
            },
        ),
    )
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            token, created = Token.objects.get_or_create(user=user)
            return Response(auth_payload(user, token), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )


class UserLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=None,
        responses=inline_serializer(
            name="MessageResponse",
            fields={"message": serializers.CharField()},
        ),
    )
    def post(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        logout(request)
        return success_response(
            None,
            "Logged off",
            "Your session has ended securely.",
        )


@extend_schema(
    methods=["GET"],
    responses=UserManagementSerializer(many=True),
)
@extend_schema(
    methods=["POST"],
    request=UserManagementSerializer,
    responses=UserManagementSerializer,
)
@extend_schema(
    methods=["PUT"],
    request=UserManagementSerializer,
    responses=UserManagementSerializer,
)
@extend_schema(
    methods=["DELETE"],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET", "POST", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def users(request):
    is_staff = request.user.is_staff

    if request.method == "GET":
        queryset = User.objects.order_by("username") if is_staff else User.objects.filter(pk=request.user.pk)
        serializer = UserManagementSerializer(
            queryset,
            many=True,
        )
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

    if request.method == "POST":
        if not is_staff:
            return Response(
                {"detail": "You do not have permission to create users."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = UserManagementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        LOGGER.info("User created - %s", user.username)
        return success_response(
            UserManagementSerializer(user).data,
            "User created",
            f"{user.username} can now sign in.",
            response_status=status.HTTP_201_CREATED,
        )

    id_ = parse_int_param(request.query_params, "id", default=0, minimum=1)
    user = get_object_or_404(User, pk=id_)
    if not is_staff and user.pk != request.user.pk:
        return Response(
            {"detail": "You do not have permission to edit this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "PUT":
        data = request.data.copy()
        if not is_staff:
            data.pop("is_staff", None)
            data.pop("is_superuser", None)
            data.pop("is_active", None)
            for field in ACCESS_FIELDS:
                data.pop(field, None)
        serializer = UserManagementSerializer(user, data=request.data, partial=True)
        if not is_staff:
            serializer = UserManagementSerializer(user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        next_is_staff = serializer.validated_data.get("is_staff", user.is_staff)
        next_is_active = serializer.validated_data.get("is_active", user.is_active)
        if user.is_staff and user.is_active and not (next_is_staff and next_is_active):
            if active_staff_count() <= 1:
                return Response(
                    {"error": "Cannot remove the last active admin user."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        user = serializer.save()
        LOGGER.info("User updated - %s", user.username)
        return success_response(
            UserManagementSerializer(user).data,
            "User saved",
            f"{user.username} was updated.",
        )

    if not is_staff:
        return Response(
            {"detail": "You do not have permission to delete users."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if User.objects.count() <= 1:
        return Response(
            {"error": "Cannot delete the last user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.is_staff and staff_count() <= 1:
        return Response(
            {"error": "Cannot delete the last admin user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.is_staff and user.is_active and active_staff_count() <= 1:
        return Response(
            {"error": "Cannot delete the last active admin user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    username = user.username
    user.delete()
    LOGGER.info("User deleted - %s", username)
    return success_response(
        {},
        "User deleted",
        f"{username} was removed.",
        status="OK",
    )
