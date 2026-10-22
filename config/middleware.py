from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from config.views import health

HEALTH_PATH = "/health/"


class HealthCheckMiddleware:
    """Отвечает на /health/ раньше остальных middleware.

    Health-check контейнера приходит изнутри Docker: по HTTP, с Host 127.0.0.1.
    Обычный путь запроса вернул бы 301 на HTTPS (SECURE_SSL_REDIRECT)
    или 400 из-за ALLOWED_HOSTS, и контейнер считался бы нездоровым.
    Поэтому middleware стоит первым и до этих проверок не доходит.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path == HEALTH_PATH and request.method == "GET":
            return health(request)
        return self.get_response(request)
