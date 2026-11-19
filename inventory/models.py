import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from organization.models import Department, Unit


class DeviceType(models.Model):
    name = models.CharField(max_length=80, unique=True, verbose_name="Cihaz türü")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")

    class Meta:
        ordering = ["name"]
        verbose_name = "Cihaz türü"
        verbose_name_plural = "Cihaz türleri"

    def __str__(self):
        return self.name


class ComponentType(models.Model):
    name = models.CharField(max_length=80, unique=True, verbose_name="Bileşen türü")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")

    class Meta:
        ordering = ["name"]
        verbose_name = "Bileşen türü"
        verbose_name_plural = "Bileşen türleri"

    def __str__(self):
        return self.name


class Device(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Kullanımda"
        REPAIR = "repair", "Onarımda"
        STORAGE = "storage", "Depoda"
        RETIRED = "retired", "Hurdaya ayrıldı"

    asset_tag = models.CharField(max_length=60, unique=True, verbose_name="Demirbaş numarası")
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name="devices", verbose_name="Cihaz türü")
    brand = models.CharField(max_length=100, blank=True, verbose_name="Marka")
    model_name = models.CharField(max_length=120, blank=True, verbose_name="Model")
    serial_number = models.CharField(max_length=120, blank=True, db_index=True, verbose_name="Seri numarası")
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True, verbose_name="IP adresi")
    mac_address = models.CharField(
        max_length=17,
        blank=True,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r"^(?:[0-9A-Fa-f]{12}|(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})$",
                message="MAC adresini AA:BB:CC:DD:EE:FF biçiminde girin.",
            )
        ],
        verbose_name="MAC adresi",
    )
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="devices", verbose_name="Departman")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True, related_name="devices", verbose_name="Birim")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name="Durum")
    specifications = models.JSONField(default=dict, blank=True, help_text="Cihaz türüne özel genişletilebilir bilgiler", verbose_name="Teknik özellikler")
    notes = models.TextField(blank=True, verbose_name="Notlar")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_devices", verbose_name="Kaydı oluşturan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme tarihi")

    class Meta:
        ordering = ["asset_tag"]
        verbose_name = "Cihaz"
        verbose_name_plural = "Cihazlar"
        indexes = [
            models.Index(fields=["department", "status"]),
            models.Index(fields=["device_type", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["serial_number"],
                condition=~Q(serial_number=""),
                name="unique_device_serial_nonblank",
            ),
            models.UniqueConstraint(
                fields=["mac_address"],
                condition=~Q(mac_address=""),
                name="unique_device_mac_nonblank",
            ),
        ]

    def __str__(self):
        return f"{self.asset_tag} — {self.brand} {self.model_name}".strip()

    def clean(self):
        super().clean()
        self.serial_number = self.serial_number.strip().upper()
        if self.mac_address:
            compact_mac = re.sub(r"[:-]", "", self.mac_address)
            if re.fullmatch(r"[0-9A-Fa-f]{12}", compact_mac):
                self.mac_address = ":".join(
                    compact_mac[index : index + 2].upper()
                    for index in range(0, 12, 2)
                )
        if self.unit_id and self.unit.department_id != self.department_id:
            raise ValidationError({"unit": "Birim seçilen departmana bağlı olmalı."})

    def save(self, *args, **kwargs):
        self.serial_number = self.serial_number.strip().upper()
        if self.mac_address:
            compact_mac = re.sub(r"[:-]", "", self.mac_address)
            if re.fullmatch(r"[0-9A-Fa-f]{12}", compact_mac):
                self.mac_address = ":".join(
                    compact_mac[index : index + 2].upper()
                    for index in range(0, 12, 2)
                )
        return super().save(*args, **kwargs)


class DeviceComponent(models.Model):
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="components", verbose_name="Cihaz")
    component_type = models.ForeignKey(ComponentType, on_delete=models.PROTECT, related_name="components", verbose_name="Bileşen türü")
    brand = models.CharField(max_length=100, blank=True, verbose_name="Marka")
    model_name = models.CharField(max_length=120, blank=True, verbose_name="Model")
    serial_number = models.CharField(max_length=120, blank=True, db_index=True, verbose_name="Seri numarası")
    specifications = models.JSONField(default=dict, blank=True, verbose_name="Teknik özellikler")
    installed_at = models.DateField(null=True, blank=True, verbose_name="Takılma tarihi")
    removed_at = models.DateField(null=True, blank=True, verbose_name="Çıkarılma tarihi")
    replacement_for = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="replacements", verbose_name="Yerine geçtiği bileşen")
    notes = models.TextField(blank=True, verbose_name="Notlar")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Kaydı oluşturan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma tarihi")

    class Meta:
        ordering = ["device", "component_type", "-created_at"]
        verbose_name = "Cihaz bileşeni"
        verbose_name_plural = "Cihaz bileşenleri"
        indexes = [models.Index(fields=["device", "component_type", "removed_at"])]

    @property
    def is_installed(self):
        return self.removed_at is None

    def __str__(self):
        return f"{self.component_type} — {self.brand} {self.model_name}".strip()


class AssignmentHistory(models.Model):
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="assignments", verbose_name="Cihaz")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="device_assignments", verbose_name="Atanan kullanıcı")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="made_assignments", verbose_name="Atamayı yapan")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Atama tarihi")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Teslim tarihi")
    notes = models.CharField(max_length=250, blank=True, verbose_name="Notlar")

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Atama geçmişi"
        verbose_name_plural = "Atama geçmişleri"
        constraints = [
            models.UniqueConstraint(fields=["device"], condition=Q(ended_at__isnull=True), name="one_active_assignment_per_device")
        ]

    def clean(self):
        super().clean()
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({"ended_at": "Teslim tarihi atama tarihinden önce olamaz."})


class InvoiceInfo(models.Model):
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="invoice_records", verbose_name="Cihaz")
    invoice_number = models.CharField(max_length=100, blank=True, verbose_name="Fatura numarası")
    vendor = models.CharField(max_length=160, blank=True, verbose_name="Tedarikçi")
    invoice_date = models.DateField(null=True, blank=True, verbose_name="Fatura tarihi")
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Tutar")
    currency = models.CharField(max_length=3, default="TRY", verbose_name="Para birimi")
    warranty_until = models.DateField(null=True, blank=True, verbose_name="Garanti bitiş tarihi")
    notes = models.CharField(max_length=250, blank=True, verbose_name="Notlar")

    class Meta:
        ordering = ["-invoice_date"]
        verbose_name = "Fatura bilgisi"
        verbose_name_plural = "Fatura bilgileri"

    def __str__(self):
        return self.invoice_number or f"{self.device} faturası"
