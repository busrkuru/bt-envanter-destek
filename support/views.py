from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Notification
from .services import visible_notifications_for


@login_required
def notification_list(request):
    notifications = visible_notifications_for(request.user)
    selected_filter = request.GET.get("filter", "all")
    if selected_filter == "unread":
        notifications = notifications.filter(read_at__isnull=True)
    else:
        selected_filter = "all"
    if request.method == "POST" and request.POST.get("action") == "mark_all_read":
        visible_notifications_for(request.user).filter(read_at__isnull=True).update(read_at=timezone.now())
        return redirect("support:notification_list")
    return render(
        request,
        "support/notification_list.html",
        {"notifications": notifications[:100], "selected_filter": selected_filter},
    )


@login_required
def notification_open(request, notification_id):
    notification = get_object_or_404(
        visible_notifications_for(request.user),
        pk=notification_id,
    )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return redirect("inventory:issue_detail", issue_id=notification.issue_id)
