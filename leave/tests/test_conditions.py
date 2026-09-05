"""Tests for LeaveTypeCondition model and evaluate_leave_type_conditions."""

from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from leave.models import LeaveTypeCondition
from leave.services import evaluate_leave_type_conditions
from leave.tests.helpers import _make_employee, _make_leave_type


class LeaveTypeConditionModelTest(TestCase):
    def test_str_with_value(self):
        cond = LeaveTypeCondition.__new__(LeaveTypeCondition)
        cond.condition_type = "gender"
        cond.value = "female"
        self.assertIn("female", str(cond))
        self.assertIn("Gender", str(cond))

    def test_str_without_value(self):
        cond = LeaveTypeCondition.__new__(LeaveTypeCondition)
        cond.condition_type = "once_per_employment"
        cond.value = None
        self.assertIn("Once Per Employment", str(cond))

    def test_clean_raises_when_value_missing_for_gender(self):
        cond = LeaveTypeCondition.__new__(LeaveTypeCondition)
        cond.pk = None
        cond.condition_type = "gender"
        cond.value = ""
        with self.assertRaises(ValidationError):
            cond.clean()

    def test_clean_passes_for_once_per_employment_without_value(self):
        cond = LeaveTypeCondition.__new__(LeaveTypeCondition)
        cond.pk = None
        cond.condition_type = "once_per_employment"
        cond.value = None
        # Should not raise
        cond.clean()


# ---------------------------------------------------------------------------
# evaluate_leave_type_conditions service tests
# ---------------------------------------------------------------------------


class GenderConditionTest(TestCase):
    def _gender_condition(self, value):
        cond = MagicMock()
        cond.condition_type = "gender"
        cond.value = value
        return cond

    def test_matching_gender_passes(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._gender_condition("female")]
        employee = _make_employee(gender="female")
        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertTrue(is_eligible)
        self.assertIsNone(msg)

    def test_wrong_gender_fails(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._gender_condition("female")]
        employee = _make_employee(gender="male")
        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertFalse(is_eligible)
        self.assertIn("female", str(msg))

    def test_case_insensitive_gender_match(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._gender_condition("Female")]
        employee = _make_employee(gender="female")
        is_eligible, _ = evaluate_leave_type_conditions(lt, employee)
        self.assertTrue(is_eligible)

    def test_maternity_female_only(self):
        lt = _make_leave_type(name="Maternity Leave")
        lt.conditions.all.return_value = [self._gender_condition("female")]
        male = _make_employee(gender="male")
        is_eligible, msg = evaluate_leave_type_conditions(lt, male)
        self.assertFalse(is_eligible)

    def test_paternity_male_only(self):
        lt = _make_leave_type(name="Paternity Leave")
        lt.conditions.all.return_value = [self._gender_condition("male")]
        female = _make_employee(gender="female")
        is_eligible, msg = evaluate_leave_type_conditions(lt, female)
        self.assertFalse(is_eligible)


class OncePerEmploymentConditionTest(TestCase):
    def _once_condition(self):
        cond = MagicMock()
        cond.condition_type = "once_per_employment"
        cond.value = None
        return cond

    @patch("leave.models.AvailableLeave")
    def test_not_yet_assigned_passes(self, MockAL):
        MockAL.objects.filter.return_value.exists.return_value = False
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._once_condition()]
        employee = _make_employee()
        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertTrue(is_eligible)

    @patch("leave.models.AvailableLeave")
    def test_already_assigned_blocks(self, MockAL):
        MockAL.objects.filter.return_value.exists.return_value = True
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._once_condition()]
        employee = _make_employee()
        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertFalse(is_eligible)
        self.assertIn("once", str(msg).lower())


class MaritalStatusConditionTest(TestCase):
    def _marital_condition(self, value):
        cond = MagicMock()
        cond.condition_type = "marital_status"
        cond.value = value
        return cond

    def test_matching_marital_passes(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._marital_condition("married")]
        employee = _make_employee(marital_status="married")
        is_eligible, _ = evaluate_leave_type_conditions(lt, employee)
        self.assertTrue(is_eligible)

    def test_wrong_marital_fails(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._marital_condition("married")]
        employee = _make_employee(marital_status="single")
        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertFalse(is_eligible)


class NoConditionsTest(TestCase):
    def test_no_conditions_always_eligible(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = []
        employee = _make_employee()
        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertTrue(is_eligible)
        self.assertIsNone(msg)


class MultipleConditionsTest(TestCase):
    """When multiple conditions are set, all must pass."""

    @patch("leave.models.AvailableLeave")
    def test_all_pass(self, MockAL):
        MockAL.objects.filter.return_value.exists.return_value = False

        gender_cond = MagicMock()
        gender_cond.condition_type = "gender"
        gender_cond.value = "female"

        once_cond = MagicMock()
        once_cond.condition_type = "once_per_employment"
        once_cond.value = None

        lt = _make_leave_type()
        lt.conditions.all.return_value = [gender_cond, once_cond]
        employee = _make_employee(gender="female")

        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertTrue(is_eligible)

    @patch("leave.models.AvailableLeave")
    def test_first_fails_short_circuits(self, MockAL):
        MockAL.objects.filter.return_value.exists.return_value = False

        gender_cond = MagicMock()
        gender_cond.condition_type = "gender"
        gender_cond.value = "female"

        once_cond = MagicMock()
        once_cond.condition_type = "once_per_employment"
        once_cond.value = None

        lt = _make_leave_type()
        lt.conditions.all.return_value = [gender_cond, once_cond]
        employee = _make_employee(gender="male")  # fails gender check

        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertFalse(is_eligible)
        # once_per_employment filter should NOT have been called
        MockAL.objects.filter.assert_not_called()


# ---------------------------------------------------------------------------
# service_duration — tenure measured from work-info date_joining
# ---------------------------------------------------------------------------


class ServiceDurationConditionTest(TestCase):
    def _condition(self, years):
        cond = MagicMock()
        cond.condition_type = "service_duration"
        cond.value = years
        return cond

    def _employee_joined_years_ago(self, years):
        from datetime import date, timedelta

        emp = _make_employee()
        emp.employee_work_info = MagicMock()
        emp.employee_work_info.date_joining = date.today() - timedelta(
            days=int(years * 365.25)
        )
        return emp

    def test_long_enough_tenure_passes(self):
        lt = _make_leave_type(name="Cuti Besar")
        lt.conditions.all.return_value = [self._condition("5")]
        is_eligible, msg = evaluate_leave_type_conditions(
            lt, self._employee_joined_years_ago(6)
        )
        self.assertTrue(is_eligible)
        self.assertIsNone(msg)

    def test_exactly_at_threshold_passes(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._condition("5")]
        is_eligible, _ = evaluate_leave_type_conditions(
            lt, self._employee_joined_years_ago(5.01)
        )
        self.assertTrue(is_eligible)

    def test_short_tenure_fails_with_actual_years(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._condition("5")]
        is_eligible, msg = evaluate_leave_type_conditions(
            lt, self._employee_joined_years_ago(2)
        )
        self.assertFalse(is_eligible)
        self.assertIn("5", str(msg))
        self.assertIn("2.0", str(msg))

    def test_no_joining_date_is_ineligible_not_silent(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._condition("5")]
        emp = _make_employee()
        emp.employee_work_info = MagicMock()
        emp.employee_work_info.date_joining = None
        is_eligible, msg = evaluate_leave_type_conditions(lt, emp)
        self.assertFalse(is_eligible)
        self.assertIn("joining date", str(msg))

    def test_no_work_info_is_ineligible(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._condition("5")]
        emp = _make_employee()
        emp.employee_work_info = None
        is_eligible, _ = evaluate_leave_type_conditions(lt, emp)
        self.assertFalse(is_eligible)

    def test_fractional_years_allowed(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._condition("0.5")]
        is_eligible, _ = evaluate_leave_type_conditions(
            lt, self._employee_joined_years_ago(1)
        )
        self.assertTrue(is_eligible)

    def test_non_numeric_value_fails_closed(self):
        lt = _make_leave_type()
        lt.conditions.all.return_value = [self._condition("five")]
        is_eligible, msg = evaluate_leave_type_conditions(
            lt, self._employee_joined_years_ago(10)
        )
        self.assertFalse(is_eligible)
        self.assertIn("invalid", str(msg).lower())
