"""DeepFace verification service tests."""
from unittest.mock import MagicMock, patch
from django.test import TestCase
from facedetection.services import FaceNotEnrolled, verify_employee_face


class VerifyFaceTests(TestCase):
    def _employee(self, enrolled=True):
        emp = MagicMock()
        if enrolled:
            emp.face_detection.image.path = "/media/faces/ref.jpg"
        else:
            emp.face_detection = None
        return emp

    def _upload(self):
        f = MagicMock()
        f.chunks.return_value = [b"jpegbytes"]
        return f

    @patch("facedetection.services.DeepFace")
    def test_match(self, deepface):
        deepface.verify.return_value = {"verified": True, "distance": 0.31}
        ok, dist = verify_employee_face(self._employee(), self._upload())
        self.assertTrue(ok)
        self.assertAlmostEqual(dist, 0.31)
        kwargs = deepface.verify.call_args.kwargs
        self.assertEqual(kwargs["model_name"], "ArcFace")

    @patch("facedetection.services.DeepFace")
    def test_mismatch(self, deepface):
        deepface.verify.return_value = {"verified": False, "distance": 0.92}
        ok, _ = verify_employee_face(self._employee(), self._upload())
        self.assertFalse(ok)

    def test_not_enrolled_raises(self):
        emp = MagicMock()
        emp.face_detection = None
        with self.assertRaises(FaceNotEnrolled):
            verify_employee_face(emp, self._upload())

    @patch("facedetection.services.DeepFace")
    def test_no_face_in_selfie_is_mismatch(self, deepface):
        deepface.verify.side_effect = ValueError("Face could not be detected")
        ok, _ = verify_employee_face(self._employee(), self._upload())
        self.assertFalse(ok)
