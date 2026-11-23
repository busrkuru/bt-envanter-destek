from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Notification

User = get_user_model()


def _create_notifications(issue, actor, recipients, event, message):
    recipient_ids = {
        user.pk
        for user in recipients
        if user.pk and user.is_active and user.pk != getattr(actor, "pk", None)
    }
    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=recipient_id,
                actor=actor if getattr(actor, "is_authenticated", False) else None,
                issue=issue,
                event=event,
                message=message[:240],
            )
            for recipient_id in recipient_ids
        ]
    )


def _support_users(issue):
    unit = issue.assigned_unit or issue.device.unit
    if not unit:
        return User.objects.none()
    return User.objects.filter(
        is_active=True,
        role="it_manager",
        scopes__department_id=unit.department_id,
    ).filter(Q(scopes__unit_id=unit.pk) | Q(scopes__unit__isnull=True)).distinct()


def _assigned_support_users(issue):
    if issue.assigned_to_id and issue.assigned_to.is_active:
        return [issue.assigned_to]
    return _support_users(issue)


def _requester_users(issue):
    user_ids = set(issue.participants.values_list("user_id", flat=True))
    user_ids.add(issue.reported_by_id)
    return User.objects.filter(pk__in=user_ids, is_active=True)


def notify_new_issue(issue, actor):
    _create_notifications(
        issue,
        actor,
        _support_users(issue),
        Notification.Event.NEW_ISSUE,
        f"Yeni arıza bildirimi: {issue.title}",
    )


def notify_assignment_changed(issue, actor):
    assignee = issue.assigned_to if issue.assigned_to_id else None
    if assignee:
        recipients = [assignee]
        message = f"{issue.title} arızası size atandı."
    else:
        recipients = _support_users(issue)
        message = f"{issue.title} arızası ekibinizin kuyruğuna yönlendirildi."
    _create_notifications(issue, actor, recipients, Notification.Event.ASSIGNMENT, message)


def notify_public_activity(issue, actor, event):
    if getattr(actor, "role", None) == "unit_user":
        recipients = _assigned_support_users(issue)
        if event == Notification.Event.REPLY:
            message = f"{issue.title} talebine kullanıcı yanıt verdi."
        else:
            message = f"{issue.title} talebinin durumu kullanıcı tarafından güncellendi."
    else:
        recipients = _requester_users(issue)
        if event == Notification.Event.REPLY:
            message = f"{issue.title} talebine yeni bir IT yanıtı eklendi."
        else:
            message = f"{issue.title} talebinin durumu: {issue.get_status_display()}."
    _create_notifications(issue, actor, recipients, event, message)


def notify_shared_users(issue, actor, users):
    _create_notifications(
        issue,
        actor,
        users,
        Notification.Event.SHARED,
        f"{issue.title} arıza talebi sizinle paylaşıldı.",
    )


def visible_notifications_for(user):
    from organization.access import visible_issues_for

    return Notification.objects.filter(
        recipient=user,
        issue__in=visible_issues_for(user),
    ).select_related("issue", "actor", "issue__device")
