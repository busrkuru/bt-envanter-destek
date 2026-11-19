from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True, verbose_name="Departman adı")
    code = models.CharField(max_length=30, unique=True, verbose_name="Departman kodu")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma tarihi")

    class Meta:
        ordering = ["name"]
        verbose_name = "Departman"
        verbose_name_plural = "Departmanlar"

    def __str__(self):
        return self.name


class Unit(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="units", verbose_name="Departman")
    name = models.CharField(max_length=120, verbose_name="Birim adı")
    code = models.CharField(max_length=30, verbose_name="Birim kodu")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")

    class Meta:
        ordering = ["department__name", "name"]
        verbose_name = "Birim"
        verbose_name_plural = "Birimler"
        constraints = [
            models.UniqueConstraint(fields=["department", "name"], name="unique_unit_name_per_department"),
            models.UniqueConstraint(fields=["department", "code"], name="unique_unit_code_per_department"),
        ]

    def __str__(self):
        return f"{self.department}: {self.name}"


class UserScope(models.Model):
    """Department/unit scope for IT staff; admins bypass scopes."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scopes", verbose_name="Kullanıcı")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="user_scopes", verbose_name="Departman")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True, related_name="user_scopes", verbose_name="Birim")

    class Meta:
        verbose_name = "Kullanıcı yetki kapsamı"
        verbose_name_plural = "Kullanıcı yetki kapsamları"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "department", "unit"],
                name="unique_user_scope",
                nulls_distinct=False,
            )
        ]

    def clean(self):
        if self.unit_id and self.unit.department_id != self.department_id:
            raise ValidationError({"unit": "Birim seçilen departmana bağlı olmalı."})

    def __str__(self):
        return f"{self.user} → {self.unit or self.department}"
