
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.test import TestCase
from rest_framework.test import APIClient


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_first_registered_user_becomes_admin(self):
        response = self.client.post(
            "/api/v1/register/",
            {
                "username": "admin",
                "password": "password",
                "password_confirm": "password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_staff"])
        self.assertTrue(response.data["is_superuser"])
        user = User.objects.get(username="admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_registration_is_closed_after_first_user_exists(self):
        User.objects.create_user(username="admin", password="password")

        response = self.client.post(
            "/api/v1/register/",
            {
                "username": "viewer",
                "password": "password",
                "password_confirm": "password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="viewer").exists())

    def test_setup_status_reports_registration_open(self):
        response = self.client.get("/api/v1/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["registration_open"])

    def test_setup_status_reports_registration_closed_after_user_exists(self):
        User.objects.create_user(username="admin", password="password")

        response = self.client.get("/api/v1/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["registration_open"])

    def test_login_returns_role_flags(self):
        User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
            is_superuser=True,
        )

        response = self.client.post(
            "/api/v1/login/",
            {"username": "admin", "password": "password"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_staff"])
        self.assertTrue(response.data["is_superuser"])

    def test_logout_requires_authentication(self):
        response = self.client.post("/api/v1/logout/")

        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_token(self):
        user = User.objects.create_user(username="admin", password="password")
        login_response = self.client.post(
            "/api/v1/login/",
            {"username": "admin", "password": "password"},
            format="json",
        )
        token = login_response.data["token"]
        token_client = APIClient()
        token_client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        response = token_client.post("/api/v1/logout/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["notification"]["title"], "Logged off")
        self.assertFalse(Token.objects.filter(user=user).exists())
        protected_response = token_client.get("/api/v1/scan/status/")
        self.assertEqual(protected_response.status_code, 401)
