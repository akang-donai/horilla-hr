from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from horilla_api.api_views.attendance.guards import face_guard, geofence_guard


def _req(lat=None, lng=None):
    r = MagicMock()
    r.data = {}
    if lat is not None:
        r.data = {"latitude": lat, "longitude": lng}
    return r


class GeofenceGuardTests(SimpleTestCase):
    def _fence(self, exempt=False, start=True):
        fence = MagicMock()
        fence.start = start
        fence.latitude, fence.longitude, fence.radius_in_meters = 10.0, 76.0, 200
        fence.is_department_exempt.return_value = exempt
        return fence

    def _wire(self, req, fence, dept="Engineering"):
        req.user.employee_get.get_company.return_value.geo_fencing = fence
        req.user.employee_get.employee_work_info.department_id = dept

    def test_disabled_fence_allows(self):
        req = _req()
        self._wire(req, self._fence(start=False))
        self.assertIsNone(geofence_guard(req))

    def test_exempt_department_allows_without_coords(self):
        req = _req()
        self._wire(req, self._fence(exempt=True))
        self.assertIsNone(geofence_guard(req))

    def test_missing_coords_rejected(self):
        req = _req()
        self._wire(req, self._fence())
        res = geofence_guard(req)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["error_code"], "outside_geofence")

    def test_inside_radius_allows(self):
        req = _req(lat=10.0001, lng=76.0001)  # ~15 m away
        self._wire(req, self._fence())
        self.assertIsNone(geofence_guard(req))

    def test_outside_radius_rejected(self):
        req = _req(lat=10.01, lng=76.01)  # ~1.5 km away
        self._wire(req, self._fence())
        self.assertEqual(geofence_guard(req).status_code, 403)

    def test_error_fails_closed(self):
        req = _req(lat="garbage", lng=None)
        self._wire(req, self._fence())
        self.assertEqual(geofence_guard(req).status_code, 403)


class FaceGuardTests(SimpleTestCase):
    def _req(self, with_image=True):
        r = MagicMock()
        r.FILES = {"image": MagicMock()} if with_image else {}
        return r

    @override_settings(STRICT_FACE_ATTENDANCE=False)
    def test_flag_off_allows(self):
        self.assertIsNone(face_guard(self._req(with_image=False)))

    @override_settings(STRICT_FACE_ATTENDANCE=True)
    def test_missing_image_rejected(self):
        res = face_guard(self._req(with_image=False))
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["error_code"], "face_mismatch")

    @override_settings(STRICT_FACE_ATTENDANCE=True)
    @patch("facedetection.services.verify_employee_face")
    def test_match_allows(self, verify):
        verify.return_value = (True, 0.3)
        self.assertIsNone(face_guard(self._req()))

    @override_settings(STRICT_FACE_ATTENDANCE=True)
    @patch("facedetection.services.verify_employee_face")
    def test_mismatch_rejected(self, verify):
        verify.return_value = (False, 0.9)
        self.assertEqual(face_guard(self._req()).status_code, 403)

    @override_settings(STRICT_FACE_ATTENDANCE=True)
    @patch("facedetection.services.verify_employee_face")
    def test_not_enrolled_400(self, verify):
        from facedetection.services import FaceNotEnrolled
        verify.side_effect = FaceNotEnrolled()
        res = face_guard(self._req())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error_code"], "not_enrolled")
