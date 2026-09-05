"""Tests for approval_condition_matches — which MultipleApprovalCondition applies to a request."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from leave.models import approval_condition_matches


def _condition(field, op, value=None, start=None, end=None):
    cond = MagicMock()
    cond.condition_field = field
    cond.condition_operator = op
    cond.condition_value = value
    cond.condition_start_value = start
    cond.condition_end_value = end
    return cond


def _request(requested_days=1.0, leave_type_id=None):
    req = MagicMock()
    req.requested_days = requested_days
    req.leave_type_id_id = leave_type_id
    return req


class RequestedDaysConditionTest(SimpleTestCase):
    """The original behaviour, now behind a field dispatch — must be unchanged."""

    def test_equal(self):
        self.assertTrue(
            approval_condition_matches(
                _condition("requested_days", "equal", "7"), _request(7.0)
            )
        )
        self.assertFalse(
            approval_condition_matches(
                _condition("requested_days", "equal", "7"), _request(8.0)
            )
        )

    def test_ge(self):
        cond = _condition("requested_days", "ge", "7")
        self.assertTrue(approval_condition_matches(cond, _request(7.0)))
        self.assertTrue(approval_condition_matches(cond, _request(40.0)))
        self.assertFalse(approval_condition_matches(cond, _request(6.5)))

    def test_range_inclusive(self):
        cond = _condition("requested_days", "range", start="3", end="7")
        self.assertTrue(approval_condition_matches(cond, _request(3.0)))
        self.assertTrue(approval_condition_matches(cond, _request(7.0)))
        self.assertFalse(approval_condition_matches(cond, _request(7.5)))

    def test_blank_field_defaults_to_requested_days(self):
        # Rows saved before the field existed have condition_field="" — keep them working.
        self.assertTrue(
            approval_condition_matches(_condition("", "equal", "7"), _request(7.0))
        )
        self.assertTrue(
            approval_condition_matches(_condition(None, "equal", "7"), _request(7.0))
        )

    def test_bad_values_never_match(self):
        self.assertFalse(
            approval_condition_matches(
                _condition("requested_days", "equal", "seven"), _request(7.0)
            )
        )
        self.assertFalse(
            approval_condition_matches(
                _condition("requested_days", "range", start="a", end="b"), _request(7.0)
            )
        )
        self.assertFalse(
            approval_condition_matches(
                _condition("requested_days", "bogus", "7"), _request(7.0)
            )
        )


class LeaveTypeConditionTest(SimpleTestCase):
    def test_equal_matches_only_that_leave_type(self):
        hajj = _condition("leave_type", "equal", "13")
        self.assertTrue(
            approval_condition_matches(hajj, _request(40.0, leave_type_id=13))
        )
        self.assertFalse(
            approval_condition_matches(hajj, _request(40.0, leave_type_id=4))
        )

    def test_requested_days_are_ignored_for_leave_type(self):
        hajj = _condition("leave_type", "equal", "13")
        self.assertTrue(
            approval_condition_matches(hajj, _request(1.0, leave_type_id=13))
        )

    def test_notequal(self):
        cond = _condition("leave_type", "notequal", "13")
        self.assertTrue(approval_condition_matches(cond, _request(leave_type_id=4)))
        self.assertFalse(approval_condition_matches(cond, _request(leave_type_id=13)))

    def test_numeric_operators_do_not_apply_to_a_foreign_key(self):
        for op in ("lt", "gt", "le", "ge", "range", "icontains"):
            self.assertFalse(
                approval_condition_matches(
                    _condition("leave_type", op, "13", "1", "20"),
                    _request(leave_type_id=13),
                ),
                op,
            )

    def test_non_integer_value_never_matches(self):
        self.assertFalse(
            approval_condition_matches(
                _condition("leave_type", "equal", "Hajj"), _request(leave_type_id=13)
            )
        )
        self.assertFalse(
            approval_condition_matches(
                _condition("leave_type", "equal", None), _request(leave_type_id=13)
            )
        )
