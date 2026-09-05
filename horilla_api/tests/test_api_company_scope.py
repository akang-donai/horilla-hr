"""API requests must not return other tenants' rows.

CompanyMiddleware reads request.user, which is anonymous for a token
authenticated call, so it selected no company and HorillaCompanyManager
skipped filtering -- every company-scoped model was tenant-wide over the API.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from base.models import Company
from horilla.testkit import make_company, make_employee, make_user
from horilla.testkit.company import CompanyFilterTestMixin
from leave.models import LeaveType


class ApiCompanyScopeTests(CompanyFilterTestMixin, TestCase):
    def setUp(self):
        self.own = make_company("Own Co")
        self.other = make_company("Other Co")

        self.user = make_user("scopeduser", password="pass12345")
        self.employee = make_employee(
            company=self.own,
            email="scopeduser@test.horilla",
            user=self.user,
        )

        self.clear_company_context()
        self.own_type = LeaveType.objects.create(name="Own Leave")
        self.own_type.company_id = self.own
        self.own_type.save()
        self.other_type = LeaveType.objects.create(name="Other Leave")
        self.other_type.company_id = self.other
        self.other_type.save()

        self.client = APIClient()

    def _login(self):
        res = self.client.post(
            "/api/auth/login/",
            {"username": "scopeduser", "password": "pass12345"},
        )
        self.assertEqual(res.status_code, 200, res.content)
        token = res.json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_leave_types_exclude_other_companies(self):
        self._login()
        res = self.client.get("/api/leave/leave-type/")
        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        rows = body["results"] if isinstance(body, dict) and "results" in body else body
        names = {row["name"] for row in rows}
        self.assertIn("Own Leave", names)
        self.assertNotIn(
            "Other Leave", names, "another company's leave type leaked over the API"
        )
