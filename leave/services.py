"""
leave/services.py

Centralised business-logic helpers for the leave app.
Condition evaluation follows the same pattern as payroll allowance eligibility checks.
"""

from datetime import date

from django.utils.translation import gettext_lazy as _


# Conditions that only make sense when a leave type is first assigned. At
# request time an AvailableLeave row necessarily exists, so re-checking these
# would hide every leave type that carries them.
ASSIGN_TIME_ONLY_CONDITIONS = frozenset({"once_per_employment"})


def evaluate_leave_type_conditions(leave_type, employee, ignore_types=()):
    """
    Evaluate all conditions configured on a LeaveType against an employee.

    Returns a (is_eligible, error_message) tuple.  When all conditions pass,
    returns (True, None).  On the first failing condition it returns
    (False, <translated error string>).

    ``ignore_types`` skips condition types that do not apply in the caller's
    context (see ``requestable_leave_types`` / ``ASSIGN_TIME_ONLY_CONDITIONS``).

    Usage::

        is_eligible, msg = evaluate_leave_type_conditions(leave_type, employee)
        if not is_eligible:
            raise ValidationError(msg)
    """
    from leave.models import AvailableLeave

    for condition in leave_type.conditions.all():
        ctype = condition.condition_type
        if ctype in ignore_types:
            continue

        if ctype == "gender":
            emp_gender = (getattr(employee, "gender", None) or "").lower()
            required_gender = (condition.value or "").lower()
            if emp_gender and required_gender and emp_gender != required_gender:
                return False, _(
                    "This leave type is restricted to {gender} employees only."
                ).format(gender=condition.value)

        elif ctype == "once_per_employment":
            already_assigned = AvailableLeave.objects.filter(
                employee_id=employee,
                leave_type_id=leave_type,
            ).exists()
            if already_assigned:
                return False, _(
                    "'{leave_type}' can only be assigned once per employment and has already been assigned to this employee."
                ).format(leave_type=leave_type.name)

        elif ctype == "marital_status":
            emp_status = (getattr(employee, "marital_status", None) or "").lower()
            required_status = (condition.value or "").lower()
            if emp_status and required_status and emp_status != required_status:
                return False, _(
                    "This leave type is restricted to employees with marital status: {status}."
                ).format(status=condition.value)

        elif ctype == "nationality":
            emp_country = (getattr(employee, "country", None) or "").lower()
            required_country = (condition.value or "").lower()
            if emp_country and required_country and emp_country != required_country:
                return False, _(
                    "This leave type is restricted to employees with nationality: {nationality}."
                ).format(nationality=condition.value)

        elif ctype == "department":
            dept = None
            work_info = getattr(employee, "employee_work_info", None)
            if work_info:
                dept_obj = getattr(work_info, "department_id", None)
                if dept_obj:
                    dept = str(dept_obj).lower()
            required_dept = (condition.value or "").lower()
            if dept and required_dept and dept != required_dept:
                return False, _(
                    "This leave type is restricted to employees in the {department} department."
                ).format(department=condition.value)

        elif ctype == "employment_type":
            emp_type = None
            work_info = getattr(employee, "employee_work_info", None)
            if work_info:
                emp_type_obj = getattr(work_info, "employee_type_id", None)
                if emp_type_obj:
                    emp_type = str(emp_type_obj).lower()
            required_type = (condition.value or "").lower()
            if emp_type and required_type and emp_type != required_type:
                return False, _(
                    "This leave type is restricted to employees with employment type: {emp_type}."
                ).format(emp_type=condition.value)

        elif ctype == "grade":
            grade = None
            work_info = getattr(employee, "employee_work_info", None)
            if work_info:
                grade_obj = getattr(work_info, "job_position_id", None)
                if grade_obj:
                    grade = str(grade_obj).lower()
            required_grade = (condition.value or "").lower()
            if grade and required_grade and grade != required_grade:
                return False, _(
                    "This leave type is restricted to employees with grade: {grade}."
                ).format(grade=condition.value)

        elif ctype == "service_duration":
            # Value is the minimum tenure in years (fractions allowed), measured
            # from work-info date_joining. An employee with no joining date on
            # record cannot prove tenure, so they are treated as ineligible
            # rather than silently passing.
            try:
                required_years = float(condition.value)
            except (TypeError, ValueError):
                return False, _(
                    "Service duration condition has an invalid value: {value}."
                ).format(value=condition.value)
            work_info = getattr(employee, "employee_work_info", None)
            joined = getattr(work_info, "date_joining", None) if work_info else None
            if not joined:
                return False, _(
                    "This leave type requires {years} years of service, but the "
                    "employee has no joining date on record."
                ).format(years=condition.value)
            tenure_years = (date.today() - joined).days / 365.25
            if tenure_years < required_years:
                return False, _(
                    "This leave type requires {years} years of service; the "
                    "employee has {actual:.1f}."
                ).format(years=condition.value, actual=tenure_years)

    return True, None


def is_currently_eligible(leave_type, employee):
    """
    Live eligibility: does the employee satisfy the leave type's conditions
    right now? Assign-time-only conditions are skipped.
    """
    ok, _msg = evaluate_leave_type_conditions(
        leave_type, employee, ignore_types=ASSIGN_TIME_ONLY_CONDITIONS
    )
    return ok


def requestable_leave_types(employee, keep=None):
    """
    Leave types the employee can request today: assigned (AvailableLeave
    exists) AND currently eligible under the type's conditions. A type stops
    appearing the moment a condition no longer holds and reappears when it
    does, without touching the underlying assignment.

    ``keep`` is a LeaveType (or id) to include regardless — used when editing
    an existing request so HR can still open it if the employee has since
    become ineligible.
    """
    from leave.models import AvailableLeave, LeaveType

    if not employee:
        return LeaveType.objects.none()
    assigned = LeaveType.objects.filter(
        id__in=AvailableLeave.objects.filter(employee_id=employee).values_list(
            "leave_type_id", flat=True
        )
    ).prefetch_related("conditions")
    eligible_ids = [lt.id for lt in assigned if is_currently_eligible(lt, employee)]
    keep_id = getattr(keep, "id", keep)
    if keep_id:
        eligible_ids.append(keep_id)
    return LeaveType.objects.filter(id__in=eligible_ids)


def has_sufficient_leave_balance(available_leave, requested_days) -> bool:
    """
    Gate used by leave_request_approve before deducting balance.

    Returns True when available_days + carryforward_days covers requested_days.
    """
    total = (available_leave.available_days or 0) + (
        available_leave.carryforward_days or 0
    )
    return total >= float(requested_days or 0)


def get_condition_display_choices():
    """
    Returns a dict of {condition_type: suggested value choices} for UI hints.
    """
    return {
        "gender": [("male", _("Male")), ("female", _("Female")), ("other", _("Other"))],
        "marital_status": [
            ("single", _("Single")),
            ("married", _("Married")),
            ("divorced", _("Divorced")),
        ],
        "once_per_employment": [],
        "nationality": [],
        "department": [],
        "employment_type": [],
        "grade": [],
        "service_duration": [],
    }
