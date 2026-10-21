from django.urls import path

from apps.payments import views

app_name = "payments"

urlpatterns = [
    path("fake/<str:external_id>/", views.fake_checkout, name="fake-checkout"),
]
