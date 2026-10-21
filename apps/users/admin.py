from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.users.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "role", "phone", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "phone", "first_name", "last_name")
    fieldsets = (
        *DjangoUserAdmin.fieldsets,
        ("Ресторан", {"fields": ("role", "phone")}),
    )
    add_fieldsets = (
        *DjangoUserAdmin.add_fieldsets,
        ("Ресторан", {"fields": ("email", "role", "phone")}),
    )
