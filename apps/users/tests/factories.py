import factory

from apps.users.models import User

DEFAULT_PASSWORD = "Str0ng-Passw0rd!"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    phone = "+998901234567"
    role = User.Role.CUSTOMER
    password = factory.django.Password(DEFAULT_PASSWORD)
