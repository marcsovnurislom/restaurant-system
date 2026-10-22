"""Демо-данные для разработки и показа проекта:

    python manage.py seed_data [--with-staff] [--with-orders 300]

Команду можно запускать повторно: записи ищутся по slug, номеру или username
и обновляются, дубликаты не появляются. Демо-заказы пересоздаются заново.
"""

import os
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.menu.models import Category, Dish, Tag
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.orders.rules import delivery_fee_for
from apps.tables.models import Table
from apps.users.models import User

# Только для локальной разработки; переопределяется через SEED_STAFF_PASSWORD
DEFAULT_STAFF_PASSWORD = "Demo-Passw0rd!"  # noqa: S105

TAGS = [
    ("Хит", "hit"),
    ("Острое", "ostroe"),
    ("Вегетарианское", "vegetarianskoe"),
    ("Новинка", "novinka"),
]

CATEGORIES = [
    ("Супы", "supy"),
    ("Горячие блюда", "goryachie"),
    ("Салаты", "salaty"),
    ("Выпечка", "vypechka"),
    ("Десерты", "deserty"),
    ("Напитки", "napitki"),
]

# (slug, название, категория, цена, вес г, теги, описание)
DISHES = [
    (
        "shurpa",
        "Шурпа",
        "supy",
        38000,
        400,
        ["hit"],
        "Наваристый бульон из баранины с крупно нарезанными овощами и зеленью.",
    ),
    (
        "lagman",
        "Лагман",
        "supy",
        42000,
        450,
        ["hit", "ostroe"],
        "Тянутая вручную лапша, говядина, болгарский перец и острый соус.",
    ),
    (
        "mastava",
        "Мастава",
        "supy",
        32000,
        400,
        [],
        "Рисовый суп с говядиной и овощами, подаётся с катыком.",
    ),
    (
        "plov-svadebnyy",
        "Плов свадебный",
        "goryachie",
        55000,
        350,
        ["hit"],
        "Девзира, баранина, жёлтая морковь, нут, изюм и перепелиное яйцо.",
    ),
    (
        "manty",
        "Манты",
        "goryachie",
        40000,
        300,
        [],
        "Пять мант на пару с рубленой бараниной и луком.",
    ),
    (
        "shashlyk-baranina",
        "Шашлык из баранины",
        "goryachie",
        35000,
        200,
        ["ostroe"],
        "Шампур бараньей корейки на углях, маринованный лук.",
    ),
    (
        "kazan-kabob",
        "Казан-кабоб",
        "goryachie",
        60000,
        400,
        ["novinka"],
        "Рёбрышки и картофель, обжаренные в казане до золотистой корочки.",
    ),
    (
        "dimlama",
        "Димлама",
        "goryachie",
        45000,
        450,
        [],
        "Мясо и овощи, томлённые в собственном соку.",
    ),
    (
        "achichuk",
        "Ачичук",
        "salaty",
        15000,
        200,
        ["vegetarianskoe"],
        "Томаты, лук и базилик. Лучшая пара к плову.",
    ),
    (
        "salat-tashkent",
        "Салат «Ташкент»",
        "salaty",
        30000,
        250,
        [],
        "Редька, отварная говядина, жареный лук и яйцо.",
    ),
    (
        "samsa-tandyr",
        "Самса из тандыра",
        "vypechka",
        12000,
        150,
        ["hit"],
        "Слоёное тесто, рубленая баранина с курдючным жиром.",
    ),
    (
        "non",
        "Лепёшка тандырная",
        "vypechka",
        6000,
        300,
        ["vegetarianskoe"],
        "Горячая лепёшка из тандыра с кунжутом.",
    ),
    (
        "chak-chak",
        "Чак-чак",
        "deserty",
        22000,
        150,
        ["vegetarianskoe"],
        "Обжаренное тесто в медовом сиропе.",
    ),
    (
        "halva",
        "Халва ассорти",
        "deserty",
        18000,
        120,
        ["vegetarianskoe", "novinka"],
        "Кунжутная, подсолнечная и ореховая халва.",
    ),
    (
        "choy-zelenyy",
        "Зелёный чай, чайник",
        "napitki",
        10000,
        700,
        ["vegetarianskoe"],
        "Китайский зелёный чай, как в настоящей чайхане.",
    ),
    (
        "ayran",
        "Айран",
        "napitki",
        9000,
        300,
        ["vegetarianskoe"],
        "Освежающий кисломолочный напиток.",
    ),
]

# (номер, мест, зона)
TABLES = [
    (1, 2, Table.Zone.HALL),
    (2, 2, Table.Zone.HALL),
    (3, 4, Table.Zone.HALL),
    (4, 4, Table.Zone.HALL),
    (5, 6, Table.Zone.HALL),
    (6, 6, Table.Zone.HALL),
    (7, 4, Table.Zone.TERRACE),
    (8, 4, Table.Zone.TERRACE),
    (9, 10, Table.Zone.VIP),
    (10, 8, Table.Zone.VIP),
]

STAFF = [
    ("demo_manager", User.Role.MANAGER),
    ("demo_cook", User.Role.COOK),
    ("demo_waiter", User.Role.WAITER),
    ("demo_courier", User.Role.COURIER),
]

# По этому имени демо-заказы находятся и пересоздаются при повторном запуске
DEMO_CUSTOMER = "Демо-гость"
DEMO_ORDER_DAYS = 60
# Час заказа и его вес: пики в обед и вечером, как в настоящей чайхане
ORDER_HOURS = {11: 2, 12: 6, 13: 8, 14: 5, 15: 2, 16: 2, 17: 3, 18: 6, 19: 9, 20: 8, 21: 4, 22: 2}


class Command(BaseCommand):
    help = "Заполняет базу демо-данными: меню, столы и (по флагу) сотрудники."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--with-staff",
            action="store_true",
            help="Создать демо-сотрудников (пароль из SEED_STAFF_PASSWORD)",
        )
        parser.add_argument(
            "--with-orders",
            type=int,
            default=0,
            metavar="N",
            help=f"Создать N заказов за последние {DEMO_ORDER_DAYS} дней (для дашборда)",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        tags = {
            slug: Tag.objects.update_or_create(slug=slug, defaults={"name": name})[0]
            for name, slug in TAGS
        }
        categories = {
            slug: Category.objects.update_or_create(
                slug=slug, defaults={"name": name, "position": position}
            )[0]
            for position, (name, slug) in enumerate(CATEGORIES, start=1)
        }

        for slug, name, category, price, weight, dish_tags, description in DISHES:
            dish, _ = Dish.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "category": categories[category],
                    "price": Decimal(price),
                    "weight_g": weight,
                    "description": description,
                },
            )
            dish.tags.set([tags[tag] for tag in dish_tags])

        for number, capacity, zone in TABLES:
            Table.objects.update_or_create(
                number=number, defaults={"capacity": capacity, "zone": zone}
            )

        summary = f"Меню: {len(DISHES)} блюд в {len(CATEGORIES)} категориях, столов: {len(TABLES)}"
        if options["with_staff"]:
            created = self._create_staff()
            summary += f", новых сотрудников: {created}"
        if options["with_orders"]:
            self._create_demo_orders(options["with_orders"])
            summary += f", демо-заказов: {options['with_orders']}"
        self.stdout.write(self.style.SUCCESS(summary))

    def _create_demo_orders(self, count: int) -> None:
        """История заказов напрямую в БД, мимо сервиса.

        Сервис разослал бы каждый заказ в Telegram и на экран кухни, а для
        прошлых заказов это не нужно (и не должно требовать запущенного Redis).
        Seed фиксирован, поэтому данные одинаковые при каждом запуске.
        """
        Order.objects.filter(customer_name=DEMO_CUSTOMER).delete()
        rng = random.Random(42)  # noqa: S311 — демо-данные, не криптография
        dishes = list(Dish.objects.all())
        tables = list(Table.objects.all())
        hours, weights = list(ORDER_HOURS), list(ORDER_HOURS.values())
        today = timezone.localdate()

        for _ in range(count):
            day = today - timedelta(days=rng.randrange(DEMO_ORDER_DAYS))
            created_at = timezone.make_aware(
                datetime.combine(day, time(rng.choices(hours, weights)[0], rng.randrange(60)))
            )
            lines = [(dish, rng.randint(1, 3)) for dish in rng.sample(dishes, rng.randint(1, 4))]
            items_total = sum(dish.price * quantity for dish, quantity in lines)
            order_type = rng.choice(list(Order.Type))
            delivery_fee = delivery_fee_for(order_type, items_total)
            status = rng.choices([Order.Status.COMPLETED, Order.Status.CANCELLED], [9, 1])[0]

            order = Order.objects.create(
                type=order_type,
                status=status,
                table=rng.choice(tables) if order_type == Order.Type.DINE_IN else None,
                address="ул. Навои, 1" if order_type == Order.Type.DELIVERY else "",
                payment_method=Order.PaymentMethod.CASH,
                payment_status=Order.PaymentStatus.PAID
                if status == Order.Status.COMPLETED
                else Order.PaymentStatus.UNPAID,
                customer_name=DEMO_CUSTOMER,
                phone="+998900000000",
                items_total=items_total,
                delivery_fee=delivery_fee,
                total=items_total + delivery_fee,
            )
            # auto_now_add не даёт задать дату при создании, поэтому отдельный UPDATE
            Order.objects.filter(pk=order.pk).update(created_at=created_at, updated_at=created_at)
            OrderItem.objects.bulk_create(
                OrderItem(
                    order=order,
                    dish=dish,
                    dish_name=dish.name,
                    unit_price=dish.price,
                    quantity=quantity,
                )
                for dish, quantity in lines
            )
            OrderStatusHistory.objects.create(order=order, to_status=status)

    def _create_staff(self) -> int:
        password = os.environ.get("SEED_STAFF_PASSWORD", DEFAULT_STAFF_PASSWORD)
        created_count = 0
        for username, role in STAFF:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@bahor.local", "role": role},
            )
            if created:
                # Пароль задаём только новым: повторный запуск не сбросит изменённый пароль
                user.set_password(password)
                user.save(update_fields=["password"])
                created_count += 1
        return created_count
