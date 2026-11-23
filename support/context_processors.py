from .services import visible_notifications_for


def notification_unread_count(request):
    if not request.user.is_authenticated:
        return {"notification_unread_count": 0}
    return {
        "notification_unread_count": visible_notifications_for(request.user)
        .filter(read_at__isnull=True)
        .count()
    }
