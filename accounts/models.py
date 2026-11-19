from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Ana Admin"
        IT_MANAGER = "it_manager", "IT Sorumlusu"
        UNIT_USER = "unit_user", "Birim Kullanıcısı"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.UNIT_USER, verbose_name="Uygulama rolü")

    class Meta(AbstractUser.Meta):
        verbose_name = "Kullanıcı"
        verbose_name_plural = "Kullanıcılar"

    def __str__(self):
        return self.get_full_name() or self.username
