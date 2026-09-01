"""Server-side face verification for attendance clock actions."""
import logging
import os
import tempfile

from deepface import DeepFace

logger = logging.getLogger(__name__)

MODEL_NAME = "ArcFace"
DETECTOR = "opencv"


class FaceNotEnrolled(Exception):
    pass


def warm_up():
    """Load the ArcFace model once so first verification isn't slow."""
    try:
        DeepFace.build_model(MODEL_NAME)
    except Exception:
        logger.exception("DeepFace warm-up failed")


def verify_employee_face(employee, uploaded_file):
    """Compare an uploaded selfie against the employee's enrolled image.

    Returns (verified: bool, distance: float).
    Raises FaceNotEnrolled when no reference image exists.
    A selfie in which no face is detected counts as a mismatch.
    """
    enrolled = getattr(employee, "face_detection", None)
    if not enrolled or not getattr(enrolled, "image", None):
        raise FaceNotEnrolled()

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp.close()
        try:
            result = DeepFace.verify(
                img1_path=tmp.name,
                img2_path=enrolled.image.path,
                model_name=MODEL_NAME,
                detector_backend=DETECTOR,
                enforce_detection=True,
            )
        except ValueError:
            return False, 1.0
        return bool(result["verified"]), float(result["distance"])
    finally:
        os.unlink(tmp.name)
