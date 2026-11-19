from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from organization.access import is_primary_admin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Uygulama yetkisi", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Uygulama yetkisi", {"fields": ("role",)}),)
    list_display = (*UserAdmin.list_display, "role")

    def has_module_permission(self, request):
        return is_primary_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_primary_admin(request.user)

    def has_add_permission(self, request):
        return is_primary_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_primary_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_primary_admin(request.user)

    def save_model(self, request, obj, form, change):
        # Role, rather than a manually toggled checkbox, controls admin entry.
        obj.is_staff = obj.is_superuser or obj.role in {
            User.Role.ADMIN,
            User.Role.IT_MANAGER,
        }
        super().save_model(request, obj, form, change)
