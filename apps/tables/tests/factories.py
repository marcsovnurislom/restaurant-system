import factory

from apps.tables.models import Table


class TableFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Table

    number = factory.Sequence(lambda n: n + 1)
    capacity = 4
    zone = Table.Zone.HALL
