"""Страница имитации оплаты для провайдера fake (только для разработки)."""

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.payments.models import Payment
from apps.payments.providers.fake import FakeProvider
from apps.payments.services import payment_process_webhook


@require_http_methods(["GET", "POST"])
def fake_checkout(request: HttpRequest, external_id: str) -> HttpResponse:
    if FakeProvider.name != settings.PAYMENT_PROVIDER:
        raise Http404
    payment = get_object_or_404(
        Payment.objects.select_related("order"), provider=FakeProvider.name, external_id=external_id
    )

    if request.method == "POST":
        succeeded = request.POST.get("action") == "pay"
        # Тот же путь, что у настоящего провайдера: подписанный webhook через сервис
        body, headers = FakeProvider.build_webhook(
            external_id=external_id, succeeded=succeeded, amount=payment.amount
        )
        payment_process_webhook(provider_name=FakeProvider.name, body=body, headers=headers)
        if succeeded:
            messages.success(request, "Оплата прошла. Заказ подтверждён!")
        else:
            messages.error(request, "Оплата отменена. Можно попробовать ещё раз.")
        return redirect("orders:detail", token=payment.order.token)

    return render(request, "payments/fake_checkout.html", {"payment": payment})
