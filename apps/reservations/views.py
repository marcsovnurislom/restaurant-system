from datetime import timedelta
from uuid import UUID

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.reservations.forms import ReservationForm
from apps.reservations.models import Reservation
from apps.reservations.rules import MAX_DAYS_AHEAD, ReservationError
from apps.reservations.services import reservation_cancel, reservation_create


@require_http_methods(["GET", "POST"])
def reservation_create_view(request: HttpRequest) -> HttpResponse:
    form = ReservationForm(request.POST or None, initial=_initial_for(request))

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            reservation = reservation_create(
                start_at=data["start_at"],
                guests_count=data["guests_count"],
                guest_name=data["guest_name"],
                phone=data["phone"],
                email=data["email"],
                comment=data["comment"],
                user=request.user if request.user.is_authenticated else None,
            )
        except ReservationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, "Стол забронирован! Сохраните эту страницу.")
            return redirect("reservations:detail", token=reservation.token)

    today = timezone.localdate()
    context = {
        "form": form,
        "min_date": today,
        "max_date": today + timedelta(days=MAX_DAYS_AHEAD),
    }
    return render(request, "reservations/form.html", context)


@require_GET
def reservation_detail_view(request: HttpRequest, token: UUID) -> HttpResponse:
    reservation = get_object_or_404(Reservation.objects.select_related("table"), token=token)
    return render(request, "reservations/detail.html", {"reservation": reservation})


@require_POST
def reservation_cancel_view(request: HttpRequest, token: UUID) -> HttpResponse:
    reservation = get_object_or_404(Reservation, token=token)
    try:
        reservation_cancel(reservation=reservation)
    except ReservationError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, "Бронь отменена.")
    return redirect("reservations:detail", token=token)


def _initial_for(request: HttpRequest) -> dict:
    initial = {"date": timezone.localdate() + timedelta(days=1)}
    user = request.user
    if user.is_authenticated:
        initial |= {
            "guest_name": user.get_full_name() or user.username,
            "phone": user.phone,
            "email": user.email,
        }
    return initial
