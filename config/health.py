from django.db import connection
from django.db.utils import OperationalError
from django.http import JsonResponse


def database_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except OperationalError:
        return False
    return True


def health(request):
    if database_ok():
        return JsonResponse({"database": "ok"})
    return JsonResponse({"database": "unavailable"}, status=503)
