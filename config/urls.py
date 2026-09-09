from django.urls import path

from apps.search.views import search, search_page

from .health import health

urlpatterns = [
    path("", search_page, name="search-page"),
    path("api/health/", health, name="health"),
    path("api/search/", search, name="search"),
]
