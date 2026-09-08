from unittest.mock import patch

import pytest
from django.test import Client


def test_health_returns_200_when_database_is_ok() -> None:
    with patch("config.health.database_ok", return_value=True):
        response = Client().get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"database": "ok"}


def test_health_returns_503_when_database_is_unavailable() -> None:
    with patch("config.health.database_ok", return_value=False):
        response = Client().get("/api/health/")

    assert response.status_code == 503
    assert response.json() == {"database": "unavailable"}


@pytest.mark.django_db
def test_health_checks_the_real_database() -> None:
    response = Client().get("/api/health/")

    assert response.status_code == 200
