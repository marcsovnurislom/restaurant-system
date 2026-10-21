import logging
import uuid
from io import BytesIO

import qrcode
from django.conf import settings
from qrcode.constants import ERROR_CORRECT_M

from apps.tables.models import Table

logger = logging.getLogger(__name__)


def table_menu_url(table: Table) -> str:
    """Полная ссылка, которая зашивается в QR-код на столе."""
    return f"{settings.SITE_URL.rstrip('/')}{table.get_absolute_url()}"


def table_qr_png(table: Table) -> bytes:
    """PNG с QR-кодом для печати. Уровень коррекции M переживает потёртости наклейки."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(table_menu_url(table))
    qr.make(fit=True)

    buffer = BytesIO()
    qr.make_image().save(buffer, format="PNG")
    return buffer.getvalue()


def table_regenerate_qr(table: Table) -> Table:
    """Выпускает новый токен: старые QR-наклейки перестают работать.

    Нужно, если ссылку на стол утащили и делают заказы удалённо.
    """
    table.qr_token = uuid.uuid4()
    table.save(update_fields=["qr_token"])
    logger.info("QR-код стола %s перевыпущен", table.number)
    return table
