from django.conf import settings
from django.db import models

from inventory.models import Device
from organization.models import Unit


class Issue(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Yeni"
        IN_PROGRESS = "in_progress", "Üzerinde çalışılıyor"
        WAITING = "waiting", "Beklemede"
        RESOLVED = "resolved", "Çözüldü"
        CLOSED = "closed", "Kapatıldı"

    class Priority(models.TextChoices):
        LOW = "low", "Düşük"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Yüksek"
        URGENT = "urgent", "Acil"

    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="issues", verbose_name="Cihaz")
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_issues", verbose_name="Bildiren kullanıcı")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="assigned_issues", verbose_name="Atanan IT sorumlusu"
    )
    assigned_unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_issues",
        verbose_name="Yönlendirilen ekip",
    )
    title = models.CharField(max_length=160, verbose_name="Başlık")
    description = models.TextField(verbose_name="Açıklama")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, verbose_name="Durum")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL, verbose_name="Öncelik")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme tarihi")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Çözülme tarihi")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Arıza bildirimi"
        verbose_name_plural = "Arıza bildirimleri"
        indexes = [models.Index(fields=["status", "priority", "created_at"])]

    def __str__(self):
        return self.title


class IssueUpdate(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="updates", verbose_name="Arıza bildirimi")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="issue_updates", verbose_name="Yazan kullanıcı")
    message = models.TextField(verbose_name="Güncelleme")
    old_status = models.CharField(max_length=20, blank=True, verbose_name="Önceki durum")
    new_status = models.CharField(max_length=20, blank=True, verbose_name="Yeni durum")
    is_internal = models.BooleanField(default=False, verbose_name="Yalnızca IT ekibine görünür")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma tarihi")

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Arıza güncellemesi"
        verbose_name_plural = "Arıza güncellemeleri"

    def __str__(self):
        return f"{self.issue}: {self.created_at:%Y-%m-%d %H:%M}"


class IssueParticipant(models.Model):
    """A unit colleague explicitly invited to follow a support request."""

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Arıza bildirimi",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="issue_participations",
        verbose_name="Katılımcı",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_issue_participations",
        verbose_name="Davet eden",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Davet tarihi")

    class Meta:
        ordering = ["created_at", "user__username"]
        verbose_name = "Arıza talebi katılımcısı"
        verbose_name_plural = "Arıza talebi katılımcıları"
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "user"],
                name="unique_issue_participant",
            )
        ]

    def __str__(self):
        return f"{self.user} — {self.issue}"


class Notification(models.Model):
    class Event(models.TextChoices):
        NEW_ISSUE = "new_issue", "Yeni arıza"
        ASSIGNMENT = "assignment", "Atama değişikliği"
        STATUS = "status", "Durum değişikliği"
        REPLY = "reply", "Yeni yanıt"
        SHARED = "shared", "Talep paylaşımı"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Alıcı",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
        verbose_name="İşlemi yapan",
    )
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Arıza bildirimi",
    )
    event = models.CharField(max_length=20, choices=Event.choices, verbose_name="Bildirim türü")
    message = models.CharField(max_length=240, verbose_name="Bildirim")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma tarihi")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Okunma tarihi")

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["recipient", "read_at", "created_at"])]
        verbose_name = "Uygulama bildirimi"
        verbose_name_plural = "Uygulama bildirimleri"

    def __str__(self):
        return f"{self.recipient}: {self.message}"
