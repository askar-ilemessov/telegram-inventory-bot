"""
Core models: StaffProfile, Location
"""
from django.db import models
from django.contrib.auth.models import User
from typing import Optional


class Location(models.Model):
    """
    Physical location (bar/restaurant branch).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    address = models.TextField(blank=True, verbose_name="Адрес")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Локация"
        verbose_name_plural = "Локации"
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class StaffProfile(models.Model):
    """
    Staff profile linked to Django User.
    Stores Telegram ID and role information.
    """
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Администратор'
        MANAGER = 'MANAGER', 'Менеджер'
        CASHIER = 'CASHIER', 'Кассир'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='staff_profile',
        verbose_name="Пользователь"
    )
    telegram_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        verbose_name="Telegram ID"
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CASHIER,
        verbose_name="Роль"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff',
        verbose_name="Локация"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Профиль сотрудника"
        verbose_name_plural = "Профили сотрудников"
        ordering = ['user__username']

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def full_name(self) -> str:
        """Get full name or username."""
        return self.user.get_full_name() or self.user.username

    def can_manage_shifts(self) -> bool:
        """Check if user can manage shifts."""
        return self.role in [self.Role.ADMIN, self.Role.MANAGER]

    def can_close_shift(self) -> bool:
        """Check if user can close shifts."""
        return self.role in [self.Role.ADMIN, self.Role.MANAGER]

