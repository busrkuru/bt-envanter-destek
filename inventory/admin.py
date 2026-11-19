from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone

from organization.access import is_it_manager, scoped_devices
from organization.admin_access import (
    RoleScopedAdmin,
    manager_departments,
    manager_units,
)

from .models import AssignmentHistory, ComponentType, Device, DeviceComponent, DeviceType, InvoiceInfo
from .forms import AssignmentTransferForm

User = get_user_model()


class ScopedDeviceRelatedAdmin(RoleScopedAdmin):
    it_manager_access = True

    def manager_queryset(self, request, queryset):
        return queryset.filter(device__in=scoped_devices(request.user))


@admin.register(Device)
class DeviceAdmin(RoleScopedAdmin):
    it_manager_access = True
    list_display = ("asset_tag", "device_type", "brand", "model_name", "department", "unit", "status", "is_active")
    list_filter = ("device_type", "department", "unit", "status", "is_active")
    search_fields = ("asset_tag", "serial_number", "ip_address", "mac_address", "brand", "model_name")

    def manager_queryset(self, request, queryset):
        return queryset.filter(pk__in=scoped_devices(request.user).values("pk"))

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/transfer/",
                self.admin_site.admin_view(self.transfer_view),
                name="inventory_device_transfer",
            ),
        ]
        return custom_urls + urls

    def transfer_view(self, request, object_id):
        device = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not self.has_change_permission(request, device):
            raise PermissionDenied

        current_assignment = device.assignments.filter(ended_at__isnull=True).select_related("user").first()
        if request.method == "POST":
            form = AssignmentTransferForm(
                request.POST, device=device, actor=request.user,
                current_assignment=current_assignment,
            )
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Serialize transfers for this device and re-check the holder under the lock.
                        locked_device = Device.objects.select_for_update().get(pk=device.pk)
                        active = AssignmentHistory.objects.select_for_update().filter(
                            device=locked_device, ended_at__isnull=True
                        ).first()
                        if active and active.user_id == form.cleaned_data["user"].pk:
                            form.add_error("user", "Bu kullanıcı cihazın mevcut kullanıcısı.")
                        else:
                            if active:
                                active.ended_at = timezone.now()
                                active.save(update_fields=["ended_at"])
                            AssignmentHistory.objects.create(
                                device=locked_device,
                                user=form.cleaned_data["user"],
                                assigned_by=request.user,
                                notes=form.cleaned_data["notes"],
                            )
                except IntegrityError:
                    form.add_error(None, "Cihazın ataması eşzamanlı olarak değişti. Sayfayı yenileyip tekrar deneyin.")
                else:
                    if not form.errors:
                        self.message_user(request, "Cihaz yeni kullanıcıya devredildi; önceki atama geçmişte kapatıldı.", messages.SUCCESS)
                        return redirect(reverse("admin:inventory_device_change", args=[device.pk]))
        else:
            form = AssignmentTransferForm(
                device=device, actor=request.user, current_assignment=current_assignment
            )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Cihaz ata / devret",
            "device": device,
            "current_assignment": current_assignment,
            "form": form,
            "change_url": reverse("admin:inventory_device_change", args=[device.pk]),
        }
        return render(request, "admin/inventory/device/transfer.html", context)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context["transfer_url"] = (
            reverse("admin:inventory_device_transfer", args=[obj.pk])
            if obj and self.has_change_permission(request, obj)
            else None
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        if not is_it_manager(request.user):
            return form_class

        scopes = list(request.user.scopes.values_list("department_id", "unit_id"))

        class ScopedDeviceForm(form_class):
            def clean(self):
                cleaned_data = super().clean()
                department = cleaned_data.get("department")
                unit = cleaned_data.get("unit")
                department_wide = department and any(
                    department_id == department.pk and unit_id is None
                    for department_id, unit_id in scopes
                )
                unit_allowed = department and unit and any(
                    department_id == department.pk and unit_id == unit.pk
                    for department_id, unit_id in scopes
                    if unit_id is not None
                )
                if department and not (department_wide or unit_allowed):
                    self.add_error(
                        "unit",
                        "Cihazı yalnızca yetki kapsamınızdaki departman ve birime kaydedebilirsiniz.",
                    )
                return cleaned_data

        return ScopedDeviceForm

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if is_it_manager(request.user):
            if db_field.name == "department":
                kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                    pk__in=manager_departments(request.user)
                )
            elif db_field.name == "unit":
                kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                    manager_units(request.user)
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeviceComponent)
class DeviceComponentAdmin(ScopedDeviceRelatedAdmin):
    list_display = ("device", "component_type", "brand", "model_name", "serial_number", "installed_at", "removed_at")
    list_filter = ("component_type", "device__department", "removed_at")
    search_fields = ("device__asset_tag", "component_type__name", "brand", "model_name", "serial_number")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "device" and is_it_manager(request.user):
            kwargs["queryset"] = scoped_devices(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AssignmentHistory)
class AssignmentHistoryAdmin(ScopedDeviceRelatedAdmin):
    list_display = ("device", "user", "assigned_by", "started_at", "ended_at")
    list_filter = ("device__department", "started_at", "ended_at")
    search_fields = ("device__asset_tag", "user__username", "user__first_name", "user__last_name")
    readonly_fields = ("device", "user", "assigned_by", "started_at", "ended_at")

    def has_add_permission(self, request):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if is_it_manager(request.user):
            if db_field.name == "device":
                kwargs["queryset"] = scoped_devices(request.user)
            elif db_field.name == "user":
                user_scope = Q(pk__in=[])
                for department_id, unit_id in request.user.scopes.values_list(
                    "department_id", "unit_id"
                ):
                    if unit_id:
                        user_scope |= Q(scopes__department_id=department_id, scopes__unit_id=unit_id)
                        user_scope |= Q(scopes__department_id=department_id, scopes__unit__isnull=True)
                    else:
                        user_scope |= Q(scopes__department_id=department_id)
                kwargs["queryset"] = User.objects.filter(user_scope, is_active=True).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InvoiceInfo)
class InvoiceInfoAdmin(ScopedDeviceRelatedAdmin):
    list_display = ("invoice_number", "device", "vendor", "invoice_date", "amount", "currency", "warranty_until")
    list_filter = ("vendor", "currency", "invoice_date", "warranty_until", "device__department")
    search_fields = ("invoice_number", "vendor", "device__asset_tag")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "device" and is_it_manager(request.user):
            kwargs["queryset"] = scoped_devices(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False


class ConfigurationAdmin(RoleScopedAdmin):
    pass


admin.site.register(DeviceType, ConfigurationAdmin)
admin.site.register(ComponentType, ConfigurationAdmin)
