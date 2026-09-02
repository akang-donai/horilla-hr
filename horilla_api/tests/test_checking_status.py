"""Regression tests for GET /api/attendance/checking-in (CheckingStatus).

The clock-in/clock-out endpoints decide "already clocked in" from
Employee.check_online(), which looks back to yesterday. CheckingStatus must
agree with that decision, or the mobile app shows "Swipe to Check-In" while
the server rejects every clock-in with "Already clocked-in".
"""

from datetime import date, datetime, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from attendance.models import AttendanceActivity
from horilla.testkit import make_company, make_employee, make_user

URL = "/api/attendance/checking-in"


class CheckingStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = make_company("Status Test Co")
        self.user = make_user("statususer", password="pass12345")
        self.employee = make_employee(
            company=self.company,
            email="statususer@test.horilla",
            user=self.user,
        )
        self.client.force_authenticate(user=self.user)

    def _open_activity(self, day: date) -> AttendanceActivity:
        started = datetime.combine(day, datetime.min.time()).replace(hour=14, minute=0)
        return AttendanceActivity.objects.create(
            employee_id=self.employee,
            attendance_date=day,
            clock_in_date=day,
            clock_in=started.time(),
            in_datetime=started,
        )

    def test_no_activity_reports_not_clocked_in(self):
        data = self.client.get(URL).json()
        self.assertFalse(data["status"])
        self.assertIn("clock_in", data)

    def test_open_session_today_reports_clocked_in(self):
        self._open_activity(date.today())
        data = self.client.get(URL).json()
        self.assertTrue(data["status"])
        self.assertEqual(data["clock_in"], "02:00 PM")

    def test_open_session_from_yesterday_reports_clocked_in(self):
        # The bug: a session opened yesterday and never closed. check_online()
        # says clocked in, so clock-in is rejected -- but the status endpoint
        # looked at today only, crashed on None, and reported not clocked in.
        self._open_activity(date.today() - timedelta(days=1))
        data = self.client.get(URL).json()
        self.assertTrue(data["status"])
        self.assertEqual(data["clock_in"], "02:00 PM")

    def test_closed_session_reports_not_clocked_in(self):
        activity = self._open_activity(date.today())
        activity.clock_out = datetime.now().time()
        activity.clock_out_date = date.today()
        activity.save()
        data = self.client.get(URL).json()
        self.assertFalse(data["status"])
        self.assertEqual(data["clock_in"], "02:00 PM")
