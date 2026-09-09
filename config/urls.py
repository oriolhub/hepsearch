from django.urls import path

from apps.search.views import search

from .health import health

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/search/", search, name="search"),
]
