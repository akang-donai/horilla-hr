"""JWT authentication that also establishes tenant scope.

``CompanyMiddleware`` sets the selected-company context that
``HorillaCompanyManager`` filters on, but it reads ``request.user``, which for
a token-authenticated API call is still ``AnonymousUser``: DRF authenticates
inside the view, and API clients send no session cookie. The middleware
therefore set the company to ``None``, and ``HorillaCompanyManager`` skips
filtering entirely when no company is selected -- so every company-scoped model
returned rows from every tenant over the API.

Authentication is the first point where the user is known, so the scope is
established here.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication

from horilla.horilla_middlewares import set_selected_company


def company_id_for(user):
    """Company a token-authenticated ``user`` may read, or ``None``.

    ``None`` leaves the queryset unfiltered, so it is returned only when there
    is genuinely no company to scope to -- an employee whose work information
    names no company, which upstream treats as visible everywhere.
    """
    employee = getattr(user, "employee_get", None)
    work_info = getattr(employee, "employee_work_info", None)
    company = getattr(work_info, "company_id", None)
    return str(company.id) if company is not None else None


class CompanyScopedJWTAuthentication(JWTAuthentication):
    """Authenticate, then pin the request to the user's own company."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            set_selected_company(company_id_for(user))
        return result
