from django.urls import path

from apps.payments.api.views import CheckoutView, WebhookView

app_name = "payments-api"

urlpatterns = [
    path("checkout/<uuid:token>/", CheckoutView.as_view(), name="checkout"),
    path("webhook/<slug:provider>/", WebhookView.as_view(), name="webhook"),
]
