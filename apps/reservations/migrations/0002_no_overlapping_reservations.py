"""Запрет двойного бронирования на уровне PostgreSQL.

Сервис уже проверяет пересечения под select_for_update, но constraint в БД —
последняя линия обороны: даже код, который пишет в обход сервиса
(админка, скрипт, будущая ошибка), не сможет создать две активные брони
одного стола на пересекающееся время.

EXCLUDE USING gist запрещает две строки, у которых совпадает table_id (=)
и пересекаются интервалы времени (&&). '[)' — полуоткрытый интервал,
поэтому брони «впритык» (18:00–20:00 и 20:00–22:00) разрешены.
Отменённые брони и завершённые визиты не учитываются (WHERE status = 'confirmed').

Это возможность только PostgreSQL, поэтому на других БД (SQLite для
локальных экспериментов) миграция ничего не делает.
"""

from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations

CONSTRAINT_NAME = "reservation_no_overlap"

CREATE_SQL = f"""
ALTER TABLE reservations_reservation
ADD CONSTRAINT {CONSTRAINT_NAME}
EXCLUDE USING gist (
    table_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
)
WHERE (status = 'confirmed')
"""

DROP_SQL = f"ALTER TABLE reservations_reservation DROP CONSTRAINT {CONSTRAINT_NAME}"


def add_constraint(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE_SQL)


def drop_constraint(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("reservations", "0001_initial"),
    ]

    operations = [
        # btree_gist нужен, чтобы в GiST-индексе сравнивать обычное число table_id через =
        BtreeGistExtension(),
        migrations.RunPython(add_constraint, drop_constraint),
    ]
