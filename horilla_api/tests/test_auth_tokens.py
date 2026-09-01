"""Tests for JWT refresh and logout endpoints."""

from django.test import TestCase
from rest_framework.test import APIClient

from horilla.testkit import make_company, make_employee, make_user


class AuthTokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = make_company("Token Test Co")
        self.user = make_user("apitest", password="pass12345")
        self.employee = make_employee(
            company=self.company,
            email="apitest@test.horilla",
            user=self.user,
        )

    def login(self):
        return self.client.post(
            "/api/auth/login/",
            {"username": "apitest", "password": "pass12345"},
        )

    def test_login_returns_refresh(self):
        data = self.login().json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)

    def test_refresh_returns_new_access(self):
        refresh = self.login().json()["refresh"]
        res = self.client.post("/api/auth/refresh/", {"refresh": refresh})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.json())

    def test_logout_blacklists_refresh(self):
        refresh = self.login().json()["refresh"]
        res = self.client.post("/api/auth/logout/", {"refresh": refresh})
        self.assertEqual(res.status_code, 200)
        res2 = self.client.post("/api/auth/refresh/", {"refresh": refresh})
        self.assertEqual(res2.status_code, 401)
