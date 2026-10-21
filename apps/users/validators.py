from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r"^\+?\d{9,15}$",
    message="Введите телефон в формате +998901234567",
)
