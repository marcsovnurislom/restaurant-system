from django.urls import path

from apps.orders import views

app_name = "orders"

urlpatterns = [
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<slug:slug>/", views.cart_add, name="cart-add"),
    path("cart/update/<slug:slug>/", views.cart_update, name="cart-update"),
    path("cart/checkout/", views.checkout, name="checkout"),
    path("orders/<uuid:token>/", views.order_detail, name="detail"),
    path("orders/<uuid:token>/cancel/", views.order_cancel, name="cancel"),
    path("orders/<uuid:token>/pay/", views.order_pay, name="pay"),
]
