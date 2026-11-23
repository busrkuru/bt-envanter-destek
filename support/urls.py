from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("bildirimler/", views.notification_list, name="notification_list"),
    path(
        "bildirimler/<int:notification_id>/",
        views.notification_open,
        name="notification_open",
    ),
]
