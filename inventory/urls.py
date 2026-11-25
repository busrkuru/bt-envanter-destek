from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cihazlar/", views.device_list, name="device_list"),
    path("cihazlar/<int:device_id>/", views.device_detail, name="device_detail"),
    path("cihazlar/<int:device_id>/qr-etiketi/", views.device_qr_label, name="device_qr_label"),
    path("raporlar/", views.reports, name="reports"),
    path("raporlar/cihazlar.csv", views.export_devices_csv, name="export_devices_csv"),
    path("raporlar/arizalar.csv", views.export_issues_csv, name="export_issues_csv"),
    path("arizalar/", views.issue_list, name="issue_list"),
    path("arizalar/yeni/", views.issue_create, name="issue_create"),
    path("arizalar/<int:issue_id>/", views.issue_detail, name="issue_detail"),
    path("arizalar/<int:issue_id>/ekler/<int:attachment_id>/", views.issue_attachment_download, name="issue_attachment_download"),
    path("arizalar/<int:issue_id>/ekler/<int:attachment_id>/onizle/", views.issue_attachment_preview, name="issue_attachment_preview"),
]
