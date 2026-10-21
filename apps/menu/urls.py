from django.urls import path

from apps.menu import views

app_name = "menu"

urlpatterns = [
    path("", views.home, name="home"),
    path("menu/", views.menu_list, name="menu-list"),
    path("menu/<slug:slug>/", views.dish_detail, name="dish-detail"),
    path("t/<uuid:token>/", views.table_menu, name="table-menu"),
]
