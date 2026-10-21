from decimal import Decimal

import factory

from apps.menu.models import Category, Dish, Tag


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Категория {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")
    position = factory.Sequence(lambda n: n)


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"Тег {n}")
    slug = factory.Sequence(lambda n: f"tag-{n}")


class DishFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Dish
        skip_postgeneration_save = True

    category = factory.SubFactory(CategoryFactory)
    name = factory.Sequence(lambda n: f"Блюдо {n}")
    slug = factory.Sequence(lambda n: f"dish-{n}")
    description = "Готовим по семейному рецепту"
    price = Decimal("25000.00")
    weight_g = 300

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if create and extracted:
            self.tags.set(extracted)
