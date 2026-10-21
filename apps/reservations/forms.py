from datetime import datetime

from django import forms
from django.utils import timezone

from apps.reservations.rules import slot_times
from apps.users.validators import phone_validator

TIME_CHOICES = [(f"{t:%H:%M}", f"{t:%H:%M}") for t in slot_times()]


class ReservationForm(forms.Form):
    date = forms.DateField(label="Дата", widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.ChoiceField(label="Время", choices=TIME_CHOICES, initial="19:00")
    guests_count = forms.IntegerField(label="Гостей", min_value=1, max_value=20, initial=2)
    guest_name = forms.CharField(label="Имя", max_length=100)
    phone = forms.CharField(
        label="Телефон",
        max_length=20,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={"type": "tel", "placeholder": "+998901234567"}),
    )
    email = forms.EmailField(label="Email", required=False, help_text="Пришлём напоминание")
    comment = forms.CharField(
        label="Пожелания",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Например: детский стул"}),
    )

    def clean(self) -> dict:
        cleaned = super().clean()
        day, time_value = cleaned.get("date"), cleaned.get("time")
        if day and time_value:
            naive = datetime.combine(day, datetime.strptime(time_value, "%H:%M").time())
            cleaned["start_at"] = timezone.make_aware(naive)
        return cleaned
