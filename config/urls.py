from django.urls import path

from .health import health

urlpatterns = [
    path("api/health/", health, name="health"),
]
