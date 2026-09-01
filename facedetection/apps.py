from django.apps import AppConfig


class FacedetectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "facedetection"

    def ready(self):
        from django.urls import include, path

        from horilla.urls import urlpatterns

        urlpatterns.append(
            path("api/facedetection/", include("facedetection.urls")),
        )
        super().ready()

        from django.conf import settings
        if getattr(settings, "STRICT_FACE_ATTENDANCE", False):
            from threading import Thread
            from .services import warm_up
            Thread(target=warm_up, daemon=True).start()
