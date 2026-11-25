import base64
import csv
from io import BytesIO
from datetime import timedelta
from pathlib import Path

import qrcode
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import CharField, Count, Prefetch, Q
from django.db.models.functions import Cast
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from organization.access import (
    is_it_manager,
    is_primary_admin,
    it_units_for,
    scoped_devices,
    visible_issues_for as issues_visible_to,
)
from organization.models import Unit
from support.models import Issue, IssueAttachment, IssueUpdate
from support.models import Notification
from support.services import (
    notify_attachment_added,
    notify_assignment_changed,
    notify_new_issue,
    notify_public_activity,
    notify_shared_users,
)

from .models import AssignmentHistory, Device, DeviceComponent, InvoiceInfo


def scoped_devices_for(user):
    """Return all devices visible to this user based on their role and scopes."""
    return scoped_devices(user)


def visible_issues_for(user):
    return issues_visible_to(user)


def user_is_it(user):
    return is_primary_admin(user) or is_it_manager(user)


def require_it_access(request):
    """Keep IT-only screens protected even when their URLs are entered directly."""
    if not user_is_it(request.user):
        raise PermissionDenied


@login_required
def dashboard(request):
    devices = scoped_devices_for(request.user)
    visible_issues = visible_issues_for(request.user)
    open_issues = visible_issues.exclude(status__in=[Issue.Status.RESOLVED, Issue.Status.CLOSED])
    context = {
        "device_count": devices.count(),
        "active_device_count": devices.filter(is_active=True).count(),
        "open_issue_count": open_issues.count(),
        "repair_count": devices.filter(status=Device.Status.REPAIR).count(),
        "recent_issues": visible_issues.select_related(
            "device", "reported_by", "assigned_unit", "assigned_to"
        ).order_by("-created_at")[:5],
    }
    if user_is_it(request.user):
        context.update(
            my_assigned_issue_count=open_issues.filter(assigned_to=request.user).count(),
            team_queue_issue_count=open_issues.filter(assigned_to__isnull=True).count(),
        )
    return render(request, "inventory/dashboard.html", context)


@login_required
def device_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    active_assignments = AssignmentHistory.objects.filter(
        ended_at__isnull=True
    ).select_related("user")
    devices = scoped_devices_for(request.user).prefetch_related(
        Prefetch("assignments", queryset=active_assignments, to_attr="active_assignments")
    )
    if status in dict(Device.Status.choices):
        devices = devices.filter(status=status)
    else:
        status = ""
    if query:
        devices = devices.annotate(
            component_specs_text=Cast("components__specifications", output_field=CharField())
        )
        component_match = Q(components__removed_at__isnull=True) & (
            Q(components__component_type__name__icontains=query)
            | Q(components__brand__icontains=query)
            | Q(components__model_name__icontains=query)
            | Q(components__serial_number__icontains=query)
            | Q(component_specs_text__icontains=query)
        )
        devices = devices.filter(
            Q(asset_tag__icontains=query)
            | Q(serial_number__icontains=query)
            | Q(ip_address__icontains=query)
            | Q(mac_address__icontains=query)
            | Q(brand__icontains=query)
            | Q(model_name__icontains=query)
            | Q(device_type__name__icontains=query)
            | Q(department__name__icontains=query)
            | Q(unit__name__icontains=query)
            | Q(assignments__ended_at__isnull=True, assignments__user__username__icontains=query)
            | Q(assignments__ended_at__isnull=True, assignments__user__first_name__icontains=query)
            | Q(assignments__ended_at__isnull=True, assignments__user__last_name__icontains=query)
            | component_match
        ).distinct()
    devices = devices.order_by("asset_tag")
    for device in devices:
        assignment = device.active_assignments[0] if device.active_assignments else None
        device.current_holder = assignment.user if assignment else None
    return render(
        request,
        "inventory/device_list.html",
        {
            "devices": devices,
            "query": query,
            "selected_status": status,
            "selected_status_label": dict(Device.Status.choices).get(status, ""),
        },
    )


@login_required
def device_detail(request, device_id):
    devices = scoped_devices_for(request.user)
    device = get_object_or_404(
        devices.prefetch_related(
            "components__component_type",
            "assignments__user",
            "invoice_records",
        ),
        pk=device_id,
    )
    can_view_internal_history = user_is_it(request.user)
    components = device.components.select_related("component_type")
    if not can_view_internal_history:
        components = components.filter(removed_at__isnull=True)

    current_assignment = (
        device.assignments.filter(ended_at__isnull=True)
        .select_related("user")
        .first()
    )
    assignments = (
        device.assignments.select_related("user", "assigned_by").all()
        if can_view_internal_history
        else []
    )
    invoices = device.invoice_records.all() if can_view_internal_history else []
    issues = Issue.objects.filter(device=device).select_related(
        "reported_by", "assigned_to"
    )
    if not can_view_internal_history:
        issues = issues.filter(reported_by=request.user)

    return render(
        request,
        "inventory/device_detail.html",
        {
            "device": device,
            "components": components,
            "current_assignment": current_assignment,
            "assignments": assignments,
            "invoices": invoices,
            "issues": issues,
            "can_view_internal_history": can_view_internal_history,
        },
    )


@login_required
def device_qr_label(request, device_id):
    device = get_object_or_404(scoped_devices_for(request.user), pk=device_id)
    detail_path = reverse("inventory:device_detail", kwargs={"device_id": device.pk})
    qr_base_url = getattr(settings, "QR_BASE_URL", "")
    target_url = (
        f"{qr_base_url}{detail_path}"
        if qr_base_url
        else request.build_absolute_uri(detail_path)
    )

    qr_image = qrcode.make(target_url, box_size=8, border=3)
    image_buffer = BytesIO()
    qr_image.save(image_buffer, format="PNG")
    qr_image_base64 = base64.b64encode(image_buffer.getvalue()).decode("ascii")

    return render(
        request,
        "inventory/device_qr_label.html",
        {
            "device": device,
            "qr_image_base64": qr_image_base64,
            "qr_target_url": target_url,
        },
    )


@login_required
def reports(request):
    require_it_access(request)
    devices = scoped_devices_for(request.user)
    visible_issues = visible_issues_for(request.user)
    status_summary = [
        {"label": label, "count": visible_issues.filter(status=value).count()}
        for value, label in Issue.Status.choices
    ]
    department_summary = (
        devices.values("department__name")
        .annotate(count=Count("id"))
        .order_by("department__name")
    )
    unit_summary = (
        devices.values("department__name", "unit__name")
        .annotate(count=Count("id"))
        .order_by("department__name", "unit__name")
    )
    device_type_summary = (
        devices.values("device_type__name")
        .annotate(count=Count("id"))
        .order_by("device_type__name")
    )
    device_status_summary = [
        {"label": label, "count": devices.filter(status=value).count()}
        for value, label in Device.Status.choices
    ]
    active_assignment_devices = AssignmentHistory.objects.filter(
        ended_at__isnull=True, device__in=devices
    ).values("device_id")
    assignment_summary = [
        {"label": "Atanmış", "count": devices.filter(pk__in=active_assignment_devices).distinct().count()},
        {"label": "Atanmamış", "count": devices.exclude(pk__in=active_assignment_devices).count()},
    ]
    component_summary = (
        DeviceComponent.objects.filter(device__in=devices, removed_at__isnull=True)
        .values("component_type__name")
        .annotate(count=Count("id"))
        .order_by("component_type__name")
    )
    can_view_internal_history = user_is_it(request.user)
    expired_warranties = []
    upcoming_warranties = []
    if can_view_internal_history:
        today = timezone.localdate()
        warranty_records = InvoiceInfo.objects.filter(
            device__in=devices, warranty_until__isnull=False
        ).select_related("device")
        expired_warranties = warranty_records.filter(
            warranty_until__lt=today
        ).order_by("warranty_until")[:10]
        upcoming_warranties = warranty_records.filter(
            warranty_until__gte=today,
            warranty_until__lte=today + timedelta(days=30),
        ).order_by("warranty_until")[:10]
    return render(
        request,
        "inventory/reports.html",
        {
            "device_count": devices.count(),
            "active_device_count": devices.filter(is_active=True).count(),
            "repair_count": devices.filter(status=Device.Status.REPAIR).count(),
            "open_issue_count": visible_issues.exclude(status__in=[Issue.Status.RESOLVED, Issue.Status.CLOSED]).count(),
            "status_summary": status_summary,
            "department_summary": department_summary,
            "unit_summary": unit_summary,
            "device_type_summary": device_type_summary,
            "device_status_summary": device_status_summary,
            "assignment_summary": assignment_summary,
            "component_summary": component_summary,
            "can_view_internal_history": can_view_internal_history,
            "expired_warranties": expired_warranties,
            "upcoming_warranties": upcoming_warranties,
        },
    )


def csv_response(filename):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    return response


def safe_csv_value(value):
    value = "" if value is None else str(value)
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


@login_required
def export_devices_csv(request):
    require_it_access(request)
    active_assignments = AssignmentHistory.objects.filter(ended_at__isnull=True).select_related("user")
    devices = (
        scoped_devices_for(request.user)
        .prefetch_related(Prefetch("assignments", queryset=active_assignments, to_attr="active_assignments"))
        .annotate(component_count=Count("components", filter=Q(components__removed_at__isnull=True)))
        .order_by("asset_tag")
    )
    response = csv_response(f"cihaz-raporu-{timezone.localdate():%Y-%m-%d}.csv")
    writer = csv.writer(response)
    writer.writerow([
        "Demirbaş numarası", "Cihaz türü", "Marka", "Model", "Seri numarası", "IP adresi",
        "MAC adresi", "Departman", "Birim", "Atanan kullanıcı", "Durum", "Aktif", "Takılı bileşen sayısı",
    ])
    for device in devices:
        assignment = device.active_assignments[0] if device.active_assignments else None
        row = [
            device.asset_tag, device.device_type.name, device.brand, device.model_name, device.serial_number,
            device.ip_address, device.mac_address, device.department.name,
            device.unit.name if device.unit_id else "", assignment.user if assignment else "",
            device.get_status_display(), "Evet" if device.is_active else "Hayır", device.component_count,
        ]
        writer.writerow([safe_csv_value(value) for value in row])
    return response


@login_required
def export_issues_csv(request):
    require_it_access(request)
    issues = visible_issues_for(request.user).select_related(
        "device", "reported_by", "assigned_to", "assigned_unit"
    )
    response = csv_response(f"ariza-raporu-{timezone.localdate():%Y-%m-%d}.csv")
    writer = csv.writer(response)
    writer.writerow([
        "Konu", "Cihaz", "Destek ekibi", "Bildiren", "Atanan IT sorumlusu", "Durum", "Öncelik", "Oluşturulma tarihi", "Tamamlanma tarihi",
    ])
    for issue in issues.order_by("-created_at"):
        row = [
            issue.title, issue.device.asset_tag, issue.assigned_unit or "", issue.reported_by,
            issue.assigned_to or "", issue.get_status_display(), issue.get_priority_display(),
            timezone.localtime(issue.created_at).strftime("%d.%m.%Y %H:%M"),
            timezone.localtime(issue.resolved_at).strftime("%d.%m.%Y %H:%M") if issue.resolved_at else "",
        ]
        writer.writerow([safe_csv_value(value) for value in row])
    return response


@login_required
def issue_list(request):
    issues = visible_issues_for(request.user).select_related(
        "device", "reported_by", "assigned_to", "assigned_unit"
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    team_id = request.GET.get("team", "").strip()
    view = request.GET.get("view", "").strip()
    if user_is_it(request.user):
        if view == "mine":
            issues = issues.filter(assigned_to=request.user)
        elif view == "queue":
            issues = issues.filter(assigned_to__isnull=True)
        else:
            view = ""
    else:
        view = ""
    team_choices = it_units_for(request.user) if user_is_it(request.user) else Unit.objects.none()
    if team_id and user_is_it(request.user):
        selected_team = team_choices.filter(pk=team_id).first()
        if selected_team:
            issues = issues.filter(assigned_unit=selected_team)
        else:
            team_id = ""
    else:
        team_id = ""
    if query:
        query_filter = (
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(device__asset_tag__icontains=query)
            | Q(assigned_unit__name__icontains=query)
        )
        if user_is_it(request.user):
            query_filter |= (
                Q(reported_by__username__icontains=query)
                | Q(reported_by__first_name__icontains=query)
                | Q(reported_by__last_name__icontains=query)
                | Q(assigned_to__username__icontains=query)
            )
        issues = issues.filter(query_filter)
    if status in dict(Issue.Status.choices):
        issues = issues.filter(status=status)
    else:
        status = ""
    if priority in dict(Issue.Priority.choices):
        issues = issues.filter(priority=priority)
    else:
        priority = ""

    paginator = Paginator(issues.order_by("-created_at"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "support/issue_list.html",
        {
            "issues": page_obj.object_list,
            "page_obj": page_obj,
            "query": query,
            "selected_status": status,
            "selected_priority": priority,
            "selected_team": team_id,
            "selected_team_id": int(team_id) if team_id else None,
            "selected_view": view,
            "team_choices": team_choices,
            "status_choices": Issue.Status.choices,
            "priority_choices": Issue.Priority.choices,
            "can_manage": user_is_it(request.user),
        },
    )


@login_required
@transaction.atomic
def issue_create(request):
    from .forms import IssueCreateForm
    from support.models import IssueUpdate

    if request.method == "POST":
        form = IssueCreateForm(request.POST, request.FILES, devices=scoped_devices_for(request.user))
        if form.is_valid():
            issue = form.save(commit=False)
            issue.reported_by = request.user
            issue.assigned_unit = issue.device.unit
            issue.save()
            for uploaded_file in form.cleaned_data.get("attachments", []):
                IssueAttachment.objects.create(
                    issue=issue,
                    uploaded_by=request.user,
                    file=uploaded_file,
                    original_name=uploaded_file.name,
                )
            IssueUpdate.objects.create(
                issue=issue,
                author=request.user,
                message=f"Durum: {dict(Issue.Status.choices)[issue.status]}",
                new_status=issue.status,
            )
            notify_new_issue(issue, request.user)
            return redirect("inventory:issue_detail", issue_id=issue.pk)
    else:
        form = IssueCreateForm(
            devices=scoped_devices_for(request.user),
            initial={"device": request.GET.get("device")},
        )
    return render(request, "support/issue_form.html", {"form": form})


@login_required
@transaction.atomic
def issue_detail(request, issue_id):
    from .forms import (
        IssueAttachmentForm,
        IssueInternalNoteForm,
        IssueManagementForm,
        IssueParticipantForm,
        IssuePublicCommentForm,
    )
    from support.models import IssueParticipant

    visible_issues = visible_issues_for(request.user)
    issue = get_object_or_404(
        visible_issues.select_related("device", "reported_by", "assigned_to", "assigned_unit"), pk=issue_id
    )
    can_manage = user_is_it(request.user)
    is_reporter = issue.reported_by_id == request.user.pk
    is_participant = issue.participants.filter(user=request.user).exists()
    can_share = is_reporter and getattr(request.user, "role", None) == "unit_user"
    can_comment = can_manage or is_reporter or is_participant
    can_attach = can_manage or is_reporter or is_participant
    internal_note_form = IssueInternalNoteForm() if can_manage else None
    public_comment_form = IssuePublicCommentForm() if can_comment else None
    share_form = IssueParticipantForm(issue=issue) if can_share else None
    attachment_form = IssueAttachmentForm(allow_internal=can_manage) if can_attach else None
    transitions = {
        Issue.Status.IN_PROGRESS: (Issue.Status.WAITING, Issue.Status.RESOLVED),
        Issue.Status.WAITING: (Issue.Status.IN_PROGRESS, Issue.Status.RESOLVED),
    }
    transition_error = ""
    transition_note = ""
    if request.method == "POST" and request.POST.get("action") == "internal_note" and can_manage:
        internal_note_form = IssueInternalNoteForm(request.POST)
        if internal_note_form.is_valid():
            IssueUpdate.objects.create(
                issue=issue,
                author=request.user,
                message=internal_note_form.cleaned_data["message"].strip(),
                is_internal=True,
            )
            return redirect("inventory:issue_detail", issue_id=issue.pk)

    if request.method == "POST" and request.POST.get("action") == "public_comment" and can_comment:
        public_comment_form = IssuePublicCommentForm(request.POST)
        if public_comment_form.is_valid():
            IssueUpdate.objects.create(
                issue=issue,
                author=request.user,
                message=public_comment_form.cleaned_data["message"],
            )
            notify_public_activity(issue, request.user, Notification.Event.REPLY)
            return redirect("inventory:issue_detail", issue_id=issue.pk)

    if request.method == "POST" and request.POST.get("action") == "share" and can_share:
        share_form = IssueParticipantForm(request.POST, issue=issue)
        if share_form.is_valid():
            selected_users = share_form.cleaned_data["participants"]
            selected_ids = list(selected_users.values_list("pk", flat=True))
            existing_ids = set(
                IssueParticipant.objects.filter(issue=issue).values_list("user_id", flat=True)
            )
            IssueParticipant.objects.filter(issue=issue).exclude(user_id__in=selected_ids).delete()
            for participant in selected_users:
                IssueParticipant.objects.get_or_create(
                    issue=issue,
                    user=participant,
                    defaults={"invited_by": request.user},
                )
            added_users = selected_users.exclude(pk__in=existing_ids)
            notify_shared_users(issue, request.user, added_users)
            return redirect("inventory:issue_detail", issue_id=issue.pk)

    if request.method == "POST" and request.POST.get("action") == "upload_attachments" and can_attach:
        attachment_form = IssueAttachmentForm(
            request.POST,
            request.FILES,
            allow_internal=can_manage,
        )
        if attachment_form.is_valid():
            is_internal = can_manage and attachment_form.cleaned_data.get("is_internal", False)
            uploaded_files = attachment_form.cleaned_data["attachments"]
            for uploaded_file in uploaded_files:
                IssueAttachment.objects.create(
                    issue=issue,
                    uploaded_by=request.user,
                    file=uploaded_file,
                    original_name=uploaded_file.name,
                    is_internal=is_internal,
                )
            IssueUpdate.objects.create(
                issue=issue,
                author=request.user,
                message=f"{len(uploaded_files)} dosya eki eklendi.",
                is_internal=is_internal,
            )
            notify_attachment_added(issue, request.user, is_internal=is_internal)
            return redirect("inventory:issue_detail", issue_id=issue.pk)

    if request.method == "POST" and request.POST.get("action") == "quick_start" and can_manage:
        if issue.status == Issue.Status.NEW and issue.assigned_to_id in (None, request.user.pk):
            old_status = issue.status
            issue.status = Issue.Status.IN_PROGRESS
            issue.assigned_to = request.user
            issue.save(update_fields=["status", "assigned_to", "updated_at"])
            IssueUpdate.objects.create(
                issue=issue,
                author=request.user,
                message=f"{request.user.get_full_name() or request.user.username} bildirimi üstlendi ve işe başladı.",
                old_status=old_status,
                new_status=issue.status,
            )
            notify_public_activity(issue, request.user, Notification.Event.STATUS)
        return redirect("inventory:issue_detail", issue_id=issue.pk)

    if request.method == "POST" and request.POST.get("action") == "transition" and can_manage:
        next_status = request.POST.get("next_status")
        if next_status in transitions.get(issue.status, ()):
            note = request.POST.get("update_note", "").strip()[:500]
            transition_note = note
            if next_status == Issue.Status.WAITING and not note:
                transition_error = "Beklemeye almadan önce kullanıcıdan beklenen bilgi veya işlemi yaz."
            else:
                old_status = issue.status
                issue.status = next_status
                if next_status == Issue.Status.RESOLVED:
                    issue.resolved_at = issue.resolved_at or timezone.now()
                else:
                    issue.resolved_at = None
                issue.save(update_fields=["status", "resolved_at", "updated_at"])
                labels = dict(Issue.Status.choices)
                message = f"Durum: {labels[old_status]} → {labels[next_status]}"
                if note:
                    message = f"{message}. {note}"
                IssueUpdate.objects.create(
                    issue=issue,
                    author=request.user,
                    message=message,
                    old_status=old_status,
                    new_status=next_status,
                )
                notify_public_activity(issue, request.user, Notification.Event.STATUS)
                return redirect("inventory:issue_detail", issue_id=issue.pk)

    if request.method == "POST" and request.POST.get("action") == "reporter_confirmation":
        choice = request.POST.get("confirmation")
        if issue.reported_by_id == request.user.pk and issue.status in {Issue.Status.RESOLVED, Issue.Status.CLOSED}:
            old_status = issue.status
            if choice == "fixed" and issue.status == Issue.Status.RESOLVED:
                issue.status = Issue.Status.CLOSED
                message = "Bildiren kullanıcı çözümü onayladı ve kaydı kapattı."
            elif choice == "not_fixed" and issue.status == Issue.Status.RESOLVED:
                issue.status = Issue.Status.IN_PROGRESS
                issue.resolved_at = None
                message = "Bildiren kullanıcı sorunun devam ettiğini bildirdi; kayıt yeniden açıldı."
            elif choice == "reopen" and issue.status == Issue.Status.CLOSED:
                issue.status = Issue.Status.IN_PROGRESS
                issue.resolved_at = None
                message = "Bildiren kullanıcı sorunun tekrar ettiğini bildirdi; kayıt yeniden açıldı."
            else:
                return redirect("inventory:issue_detail", issue_id=issue.pk)
            issue.save(update_fields=["status", "resolved_at", "updated_at"])
            IssueUpdate.objects.create(
                issue=issue,
                author=request.user,
                message=message,
                old_status=old_status,
                new_status=issue.status,
            )
            notify_public_activity(issue, request.user, Notification.Event.STATUS)
            return redirect("inventory:issue_detail", issue_id=issue.pk)

    if request.method == "POST" and request.POST.get("action") == "manage" and can_manage:
        management_form = IssueManagementForm(
            request.POST,
            actor=request.user,
            device=issue.device,
            current_team=issue.assigned_unit or issue.device.unit,
        )
        if management_form.is_valid():
            old_priority = issue.priority
            old_assigned_to_id = issue.assigned_to_id
            old_assigned_unit_id = issue.assigned_unit_id
            old_assignee = issue.assigned_to
            old_team = issue.assigned_unit
            issue.priority = management_form.cleaned_data["priority"]
            issue.assigned_unit = management_form.cleaned_data["assigned_unit"]
            issue.assigned_to = management_form.cleaned_data["assigned_to"]
            issue.save()
            if (
                old_priority != issue.priority
                or old_assigned_to_id != issue.assigned_to_id
                or old_assigned_unit_id != issue.assigned_unit_id
            ):
                changes = []
                if old_assigned_unit_id != issue.assigned_unit_id:
                    changes.append(
                        f"Ekip: {old_team.name if old_team else 'Atanmadı'} → "
                        f"{issue.assigned_unit.name if issue.assigned_unit else 'Atanmadı'}"
                    )
                if old_assigned_to_id != issue.assigned_to_id:
                    changes.append(
                        f"Sorumlu: {old_assignee or 'Atanmadı'} → "
                        f"{issue.assigned_to or 'Ekip kuyruğu'}"
                    )
                if old_priority != issue.priority:
                    changes.append(f"Öncelik: {issue.get_priority_display()}")
                IssueUpdate.objects.create(
                    issue=issue,
                    author=request.user,
                    message=" · ".join(changes),
                    is_internal=True,
                )
                if old_assigned_to_id != issue.assigned_to_id or old_assigned_unit_id != issue.assigned_unit_id:
                    notify_assignment_changed(issue, request.user)
            return redirect("inventory:issue_detail", issue_id=issue.pk)
    else:
        management_form = None
    if can_manage and management_form is None:
        available_team_ids = set(it_units_for(request.user).values_list("pk", flat=True))
        requested_team_id = request.GET.get("route_unit", "").strip()
        if "route_unit" in request.GET and not requested_team_id:
            initial_team_id = None
        elif requested_team_id and str(requested_team_id).isdigit() and int(requested_team_id) in available_team_ids:
            initial_team_id = int(requested_team_id)
        else:
            initial_team_id = issue.assigned_unit_id or issue.device.unit_id
        management_form = IssueManagementForm(
            actor=request.user,
            device=issue.device,
            current_team=issue.assigned_unit or issue.device.unit,
            initial={
                "priority": issue.priority,
                "assigned_to": issue.assigned_to_id,
                "assigned_unit": initial_team_id if initial_team_id and initial_team_id in available_team_ids else None,
            }
        )
    updates = issue.updates.select_related("author").order_by("created_at")
    if not can_manage:
        updates = updates.filter(is_internal=False)
    status_labels = dict(Issue.Status.choices)
    for update in updates:
        update.is_status_update = bool(update.old_status or update.new_status)
        update.old_status_label = status_labels.get(update.old_status, update.old_status)
        update.new_status_label = status_labels.get(update.new_status, update.new_status)
        if update.old_status:
            generic_message = f"Durum: {update.old_status_label} → {update.new_status_label}"
        else:
            generic_message = f"Durum: {update.new_status_label}"
        update.activity_note = update.message
        if update.activity_note == generic_message:
            update.activity_note = ""
        elif update.activity_note.startswith(f"{generic_message}. "):
            update.activity_note = update.activity_note[len(generic_message) + 2:]
    return render(
        request,
        "support/issue_detail.html",
        {
            "issue": issue,
            "transition_error": transition_error,
            "transition_note": transition_note,
            "updates": updates,
            "management_form": management_form if can_manage else None,
            "internal_note_form": internal_note_form,
            "public_comment_form": public_comment_form,
            "share_form": share_form,
            "attachment_form": attachment_form,
            "can_attach": can_attach,
            "attachments": (
                issue.attachments.select_related("uploaded_by")
                if can_manage
                else issue.attachments.select_related("uploaded_by").filter(is_internal=False)
            ),
            "can_share": can_share,
            "has_share_candidates": bool(share_form and share_form.fields["participants"].queryset.exists()),
            "can_comment": can_comment,
            "is_participant": is_participant,
            "issue_participants": issue.participants.select_related("user"),
            "can_manage": can_manage,
            "can_view_device": scoped_devices_for(request.user).filter(pk=issue.device_id).exists(),
            "available_transitions": [
                (status, dict(Issue.Status.choices)[status])
                for status in transitions.get(issue.status, ())
            ] if can_manage else [],
            "can_quick_start": (
                can_manage
                and issue.status == Issue.Status.NEW
                and issue.assigned_to_id in (None, request.user.pk)
            ),
            "can_confirm_resolution": (
                not can_manage
                and issue.reported_by_id == request.user.pk
                and issue.status in {Issue.Status.RESOLVED, Issue.Status.CLOSED}
            ),
            "workflow_steps": (
                (Issue.Status.NEW, dict(Issue.Status.choices)[Issue.Status.NEW]),
                (Issue.Status.IN_PROGRESS, dict(Issue.Status.choices)[Issue.Status.IN_PROGRESS]),
                (Issue.Status.WAITING, dict(Issue.Status.choices)[Issue.Status.WAITING]),
                (Issue.Status.RESOLVED, dict(Issue.Status.choices)[Issue.Status.RESOLVED]),
                (Issue.Status.CLOSED, dict(Issue.Status.choices)[Issue.Status.CLOSED]),
            ),
            "workflow_current_step": {
                Issue.Status.NEW: 0,
                Issue.Status.IN_PROGRESS: 1,
                Issue.Status.WAITING: 2,
                Issue.Status.RESOLVED: 3,
                Issue.Status.CLOSED: 4,
            }.get(issue.status, 0),
            "status_guidance": {
                Issue.Status.NEW: (
                    "Bildirim IT ekibine iletildi. Bir sorumlu işe başladığında durum burada güncellenecek."
                    if not can_manage else
                    "Bildirim sırada. Üstlenip işe başlayabilir veya doğru IT sorumlusuna atayabilirsin."
                ),
                Issue.Status.IN_PROGRESS: (
                    "IT ekibi sorunu inceliyor. Yeni bir bilgi gerekirse aşağıdaki durum geçmişinde not bırakılır."
                    if not can_manage else
                    "İnceleme sürüyor. Çözüm için beklemeye alabilir veya sorun giderildiyse çözüldü olarak işaretleyebilirsin."
                ),
                Issue.Status.WAITING: (
                    "Bu kayıtta senden bilgi veya işlem bekleniyor. İstenen adım, durum geçmişindeki son notta yazıyor."
                    if not can_manage else
                    "Kullanıcıdan beklenen bilgi veya işlemi durum notunda açıkça belirt. Yanıt geldiğinde çalışmaya devam edebilirsin."
                ),
                Issue.Status.RESOLVED: (
                    "Çözümünü kontrol et. Sorun giderildiyse onayla; devam ediyorsa yeniden aç."
                    if not can_manage else
                    "Çözüm kullanıcı onayını bekliyor. Kullanıcı onayladığında kayıt kapanır; sorun sürüyorsa yeniden açılır."
                ),
                Issue.Status.CLOSED: (
                    "Bu bildirim kapatıldı. Sorun tekrar ederse kaydı yeniden açabilirsin."
                    if not can_manage else
                    "Bildirim kapalı. Kullanıcı sorun tekrar ettiğini bildirirse kayıt yeniden açılabilir."
                ),
            }.get(issue.status, ""),
        },
    )


@login_required
def issue_attachment_download(request, issue_id, attachment_id):
    attachment = _visible_issue_attachment(request, issue_id, attachment_id)
    try:
        file_handle = attachment.file.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404("Dosya bulunamadı.") from exc
    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=attachment.original_name,
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def issue_attachment_preview(request, issue_id, attachment_id):
    attachment = _visible_issue_attachment(request, issue_id, attachment_id)
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    content_type = content_types.get(Path(attachment.original_name).suffix.lower())
    if not content_type:
        raise Http404("Bu dosyanın önizlemesi bulunamadı.")
    try:
        file_handle = attachment.file.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404("Dosya bulunamadı.") from exc
    response = FileResponse(
        file_handle,
        as_attachment=False,
        filename=attachment.original_name,
        content_type=content_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    return response


def _visible_issue_attachment(request, issue_id, attachment_id):
    issue = get_object_or_404(visible_issues_for(request.user), pk=issue_id)
    attachments = IssueAttachment.objects.filter(issue=issue)
    if not user_is_it(request.user):
        attachments = attachments.filter(is_internal=False)
    return get_object_or_404(attachments, pk=attachment_id)
