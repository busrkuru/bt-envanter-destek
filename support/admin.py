from django.contrib import admin
from django.utils import timezone

from organization.access import is_it_manager, it_assignees_for, scoped_devices
from organization.admin_access import RoleScopedAdmin

from .models import Issue, IssueUpdate


@admin.register(IssueUpdate)
class IssueUpdateAdmin(RoleScopedAdmin):
    it_manager_access = True
    list_display = ("issue", "author", "old_status", "new_status", "created_at")
    list_filter = ("created_at", "old_status", "new_status")
    search_fields = ("issue__title", "issue__device__asset_tag", "author__username", "message")
    readonly_fields = ("issue", "author", "message", "old_status", "new_status", "created_at")

    def manager_queryset(self, request, queryset):
        return queryset.filter(issue__device__in=scoped_devices(request.user))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class IssueUpdateInline(admin.TabularInline):
    model = IssueUpdate
    extra = 0
    can_delete = False
    fields = ("message", "old_status", "new_status", "author", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Issue)
class IssueAdmin(RoleScopedAdmin):
    it_manager_access = True
    list_display = ("title", "device", "reported_by", "assigned_to", "status", "priority", "created_at")
    list_filter = ("status", "priority", "created_at")
    search_fields = ("title", "description", "device__asset_tag", "reported_by__username")
    inlines = (IssueUpdateInline,)

    def manager_queryset(self, request, queryset):
        return queryset.filter(device__in=scoped_devices(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "device" and is_it_manager(request.user):
            kwargs["queryset"] = scoped_devices(request.user)
        elif db_field.name == "assigned_to":
            device = None
            device_id = request.POST.get("device")
            if device_id:
                from inventory.models import Device

                device = Device.objects.filter(pk=device_id).first()
            else:
                object_id = request.resolver_match.kwargs.get("object_id")
                if object_id:
                    issue = self.get_object(request, object_id)
                    device = issue.device if issue else None
            kwargs["queryset"] = it_assignees_for(request.user, device)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = Issue.objects.get(pk=obj.pk)

        if obj.status in {Issue.Status.RESOLVED, Issue.Status.CLOSED}:
            obj.resolved_at = obj.resolved_at or timezone.now()
        else:
            obj.resolved_at = None

        super().save_model(request, obj, form, change)

        if not change:
            IssueUpdate.objects.create(
                issue=obj,
                author=request.user,
                message=f"Durum: {dict(Issue.Status.choices)[obj.status]}",
                new_status=obj.status,
            )
            return

        if previous.status != obj.status:
            labels = dict(Issue.Status.choices)
            IssueUpdate.objects.create(
                issue=obj,
                author=request.user,
                message=f"Durum: {labels[previous.status]} → {labels[obj.status]}",
                old_status=previous.status,
                new_status=obj.status,
            )

    def has_delete_permission(self, request, obj=None):
        return False
