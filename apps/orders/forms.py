from django import forms

from apps.orders.models import Order
from apps.users.validators import phone_validator


class CheckoutForm(forms.Form):
    type = forms.ChoiceField(label="Как получить", widget=forms.RadioSelect)
    customer_name = forms.CharField(label="Имя", max_length=100)
    phone = forms.CharField(
        label="Телефон",
        max_length=20,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={"type": "tel", "placeholder": "+998901234567"}),
    )
    address = forms.CharField(
        label="Адрес доставки",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Улица, дом, квартира, ориентир"}),
    )
    comment = forms.CharField(
        label="Комментарий",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    payment_method = forms.ChoiceField(
        label="Оплата",
        choices=Order.PaymentMethod.choices,
        initial=Order.PaymentMethod.CASH,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, has_table: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Заказ «в зале» доступен, только если гость открыл меню по QR-коду со стола
        types = [(t.value, t.label) for t in Order.Type if has_table or t != Order.Type.DINE_IN]
        self.fields["type"].choices = types
        self.fields["type"].initial = Order.Type.DINE_IN if has_table else Order.Type.DELIVERY

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("type") == Order.Type.DELIVERY and not cleaned.get("address", "").strip():
            self.add_error("address", "Укажите адрес доставки.")
        return cleaned
