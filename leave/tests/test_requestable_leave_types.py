"""Tests for live leave-type eligibility at request time (requestable_leave_types + LeaveRequest.clean)."""

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase


class RequestableLeaveTypesTests(TestCase):
    def setUp(self):
        from horilla.testkit import make_company, make_employee
        from leave.models import AvailableLeave, LeaveType, LeaveTypeCondition

        company = make_company("Eligibility Co")
        self.employee = make_employee(company=company, email="elig@test.horilla")
        wi = self.employee.employee_work_info
        wi.date_joining = date.today() - timedelta(days=3 * 365)  # ~3 years
        wi.save(update_fields=["date_joining"])

        self.annual = LeaveType.objects.create(name="Annual", total_days=12)
        self.long_service = LeaveType.objects.create(name="Long Service", total_days=30)
        cond = LeaveTypeCondition.objects.create(
            condition_type="service_duration", value="5"
        )
        self.long_service.conditions.add(cond)
        for lt in (self.annual, self.long_service):
            AvailableLeave.objects.create(
                employee_id=self.employee,
                leave_type_id=lt,
                available_days=lt.total_days,
                total_leave_days=lt.total_days,
            )

    def _set_tenure_years(self, years):
        wi = self.employee.employee_work_info
        wi.date_joining = date.today() - timedelta(days=int(years * 365.25))
        wi.save(update_fields=["date_joining"])
        self.employee.refresh_from_db()

    def test_assigned_but_ineligible_type_is_hidden(self):
        from leave.services import requestable_leave_types

        names = set(
            requestable_leave_types(self.employee).values_list("name", flat=True)
        )
        self.assertEqual(names, {"Annual"})

    def test_type_reappears_once_condition_holds(self):
        from leave.services import requestable_leave_types

        self._set_tenure_years(6)
        names = set(
            requestable_leave_types(self.employee).values_list("name", flat=True)
        )
        self.assertEqual(names, {"Annual", "Long Service"})

    def test_unassigned_type_never_appears_even_if_eligible(self):
        from leave.models import LeaveType
        from leave.services import requestable_leave_types

        LeaveType.objects.create(name="Not Assigned", total_days=1)
        self.assertNotIn(
            "Not Assigned",
            set(requestable_leave_types(self.employee).values_list("name", flat=True)),
        )

    def test_keep_forces_inclusion_for_editing(self):
        from leave.services import requestable_leave_types

        names = set(
            requestable_leave_types(self.employee, keep=self.long_service).values_list(
                "name", flat=True
            )
        )
        self.assertIn("Long Service", names)

    def test_once_per_employment_is_not_evaluated_at_request_time(self):
        from leave.models import LeaveTypeCondition
        from leave.services import requestable_leave_types

        # At request time an AvailableLeave always exists, so this condition
        # would hide the type if it were re-checked here.
        self.annual.conditions.add(
            LeaveTypeCondition.objects.create(condition_type="once_per_employment")
        )
        self.assertIn(
            "Annual",
            set(requestable_leave_types(self.employee).values_list("name", flat=True)),
        )

    def test_no_employee_gives_empty_queryset(self):
        from leave.services import requestable_leave_types

        self.assertEqual(requestable_leave_types(None).count(), 0)


class LeaveRequestCleanEligibilityGateTests(TestCase):
    def setUp(self):
        from horilla.testkit import make_company, make_employee
        from leave.models import AvailableLeave, LeaveType, LeaveTypeCondition

        company = make_company("Gate Co")
        self.employee = make_employee(company=company, email="gate@test.horilla")
        wi = self.employee.employee_work_info
        wi.date_joining = date.today() - timedelta(days=2 * 365)
        wi.save(update_fields=["date_joining"])
        self.long_service = LeaveType.objects.create(name="Long Service", total_days=30)
        self.long_service.conditions.add(
            LeaveTypeCondition.objects.create(
                condition_type="service_duration", value="5"
            )
        )
        AvailableLeave.objects.create(
            employee_id=self.employee,
            leave_type_id=self.long_service,
            available_days=30,
            total_leave_days=30,
        )

    def _request(self, **overrides):
        from leave.models import LeaveRequest

        today = date.today()
        fields = dict(
            employee_id=self.employee,
            leave_type_id=self.long_service,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=1),
            start_date_breakdown="full_day",
            end_date_breakdown="full_day",
            description="x",
        )
        fields.update(overrides)
        return LeaveRequest(**fields)

    def test_new_request_for_ineligible_assigned_type_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self._request().clean()
        self.assertIn("years of service", str(ctx.exception))

    def test_existing_request_is_not_re_gated(self):
        # An already-saved request (pk set) must remain editable/decidable even
        # though the employee is ineligible now: the eligibility evaluator must
        # not even be consulted. Later gates in clean() read the thread-local
        # request, so install a real superuser there for the duration and put
        # the previous value back afterwards (HorillaModel.save() stamps
        # created_by from the same thread-local, so a leaked mock breaks every
        # later test).
        from unittest.mock import patch

        from django.contrib.auth import get_user_model

        from horilla import horilla_middlewares

        superuser = get_user_model().objects.create_superuser(
            username="gate-super@test.horilla",
            email="gate-super@test.horilla",
            password="x",
        )
        tl = horilla_middlewares._thread_locals
        had = hasattr(tl, "request")
        previous = getattr(tl, "request", None)

        class _Req:
            user = superuser

        tl.request = _Req()
        try:
            req = self._request()
            req.pk = 999
            with patch("leave.services.evaluate_leave_type_conditions") as evaluator:
                try:
                    req.clean()
                except ValidationError as e:
                    self.assertNotIn("years of service", str(e))
                evaluator.assert_not_called()
        finally:
            if had:
                tl.request = previous
            else:
                del tl.request
