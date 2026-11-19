from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .admin_access import RoleScopedAdmin
from .models import Department, Unit, UserScope


@admin.register(Department)
class DepartmentAdmin(RoleScopedAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(Unit)
class UnitAdmin(RoleScopedAdmin):
    list_display = ("name", "code", "department", "is_active")
    search_fields = ("name", "code", "department__name")
    list_filter = ("department", "is_active")


@admin.register(UserScope)
class UserScopeAdmin(RoleScopedAdmin):
    list_display = ("user", "department", "unit")
    search_fields = ("user__username", "department__name", "unit__name")
