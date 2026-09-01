"""Pre-conditions applied to clock-in / clock-out API calls."""
import logging

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from geopy.distance import geodesic
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _outside():
    return Response(
        {
            "error_code": "outside_geofence",
            "error": _("You are outside the allowed clock-in area."),
        },
        status=403,
    )


def geofence_guard(request):
    """Return a 403 Response when the geofence blocks this request, else None.

    Fail closed: any error while checking a non-exempt employee rejects.
    """
    try:
        company = request.user.employee_get.get_company()
        fence = getattr(company, "geo_fencing", None)
        if fence is None or not fence.start:
            return None
    except Exception:
        return None  # no company/fence configured -> feature off

    try:
        department = request.user.employee_get.employee_work_info.department_id
    except Exception:
        department = None
    try:
        if fence.is_department_exempt(department):
            return None
        lat = float(request.data.get("latitude"))
        lng = float(request.data.get("longitude"))
        meters = geodesic((fence.latitude, fence.longitude), (lat, lng)).meters
        if meters <= fence.radius_in_meters:
            return None
        return _outside()
    except Exception:
        logger.exception("Geofence check failed; rejecting (fail closed)")
        return _outside()


def face_guard(request):
    """Verify the uploaded selfie when STRICT_FACE_ATTENDANCE is on."""
    if not getattr(settings, "STRICT_FACE_ATTENDANCE", False):
        return None
    from facedetection.services import FaceNotEnrolled, verify_employee_face

    image = request.FILES.get("image")
    if image is None:
        return Response(
            {"error_code": "face_mismatch",
             "error": _("A selfie image is required to clock in or out.")},
            status=403,
        )
    try:
        verified, _distance = verify_employee_face(request.user.employee_get, image)
    except FaceNotEnrolled:
        return Response(
            {"error_code": "not_enrolled",
             "error": _("No enrolled face image. Please enroll first.")},
            status=400,
        )
    except Exception:
        logger.exception("Face verification error; rejecting (fail closed)")
        verified = False
    if verified:
        return None
    return Response(
        {"error_code": "face_mismatch", "error": _("Face verification failed.")},
        status=403,
    )
