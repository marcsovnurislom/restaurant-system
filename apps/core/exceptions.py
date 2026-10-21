from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    """409: запрос корректный, но конфликтует с текущим состоянием данных."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Объект используется и не может быть удалён."
    default_code = "conflict"
