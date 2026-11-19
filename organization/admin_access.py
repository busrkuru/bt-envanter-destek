from django.contrib import admin
from django.db.models import Q

from .access import is_it_manager, is_primary_admin, scope_query
from .models import UserScope


class RoleScopedAdmin(admin.ModelAdmin):
    """Role checks for admin pages; subclasses opt into scoped IT access."""

    it_manager_access = False

    def manager_queryset(self, request, queryset):
        return queryset.none()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_primary_admin(request.user):
            return queryset
        if self.it_manager_access and is_it_manager(request.user):
            return self.manager_queryset(request, queryset)
        return queryset.none()

    def has_module_permission(self, request):
        return is_primary_admin(request.user) or (
            self.it_manager_access and is_it_manager(request.user)
        )

    def _role_permission(self, request, obj=None):
        if is_primary_admin(request.user):
            return True
        if not (self.it_manager_access and is_it_manager(request.user)):
            return False
        if obj is None:
            return True
        return self.get_queryset(request).filter(pk=obj.pk).exists()

    def has_view_permission(self, request, obj=None):
        return self._role_permission(request, obj)

    def has_add_permission(self, request):
        return self._role_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._role_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._role_permission(request, obj)


def manager_departments(user):
    return UserScope.objects.filter(user=user).values("department_id")


def manager_units(user):
    query = Q(pk__in=[])
    for department_id, unit_id in UserScope.objects.filter(user=user).values_list(
        "department_id", "unit_id"
    ):
        if unit_id:
            query |= Q(pk=unit_id)
        else:
            query |= Q(department_id=department_id)
    return query


def scoped_related_queryset(user, model, prefix=""):
    return model.objects.filter(scope_query(user, prefix=prefix)).distinct()
