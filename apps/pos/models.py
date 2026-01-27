"""
POS models: Shift, Transaction, Payment, StockCount
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from apps.core.models import Location, StaffProfile
from apps.inventory.models import Product


class Shift(models.Model):
    """
    Work shift for a staff member at a location.
    Only one open shift per location is allowed (enforced by UniqueConstraint).
    """
    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.PROTECT,
        related_name='shifts',
        verbose_name="Сотрудник"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='shifts',
        verbose_name="Локация"
    )
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Начало смены")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Конец смены")
    is_closed = models.BooleanField(default=False, db_index=True, verbose_name="Закрыта")
    
    # Totals calculated on shift close
    total_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Общая сумма продаж"
    )
    total_cash = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Наличные"
    )
    total_card = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Карта"
    )
    total_transfer = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Перевод"
    )

    notes = models.TextField(blank=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Смена"
        verbose_name_plural = "Смены"
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['location'],
                condition=models.Q(is_closed=False),
                name='unique_open_shift_per_location'
            )
        ]
        indexes = [
            models.Index(fields=['location', 'is_closed']),
            models.Index(fields=['staff', '-started_at']),
        ]

    def __str__(self) -> str:
        status = "Открыта" if not self.is_closed else "Закрыта"
        return f"Смена {self.staff.full_name} - {self.location.name} ({status})"

    def clean(self) -> None:
        """Validate that only one open shift exists per location."""
        if not self.is_closed and not self.pk:
            existing = Shift.objects.filter(
                location=self.location,
                is_closed=False
            ).exists()
            if existing:
                raise ValidationError(
                    f"В локации {self.location.name} уже есть открытая смена"
                )


class Transaction(models.Model):
    """
    Append-only transaction log.
    Records all sales and inventory movements.
    """
    class TransactionType(models.TextChoices):
        SALE = 'SALE', 'Продажа'
        REFUND = 'REFUND', 'Возврат'
        ADJUSTMENT = 'ADJUSTMENT', 'Корректировка'
        WRITEOFF = 'WRITEOFF', 'Списание'

    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name="Смена"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name="Товар"
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        default=TransactionType.SALE,
        verbose_name="Тип транзакции"
    )
    qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Количество"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Сумма"
    )
    notes = models.TextField(blank=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Создано")
    exported_at = models.DateTimeField(null=True, blank=True, verbose_name="Экспортировано")

    class Meta:
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shift', '-created_at']),
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['exported_at']),
        ]

    def __str__(self) -> str:
        return f"{self.get_transaction_type_display()}: {self.product.name} x {self.qty}"


class Payment(models.Model):
    """
    Payment record for a transaction.
    Multiple payments can be linked to one transaction (split payment).
    """
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Наличные'
        CARD = 'CARD', 'Карта'
        TRANSFER = 'TRANSFER', 'Перевод'

    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Транзакция"
    )
    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        verbose_name="Способ оплаты"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Сумма"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.get_method_display()}: {self.amount}"


class StockCount(models.Model):
    """
    Stock count snapshot taken during shift close.
    Stores inventory state at a specific point in time.
    """
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name='stock_counts',
        verbose_name="Смена"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='stock_counts',
        verbose_name="Товар"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Количество"
    )
    notes = models.TextField(blank=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Ревизия остатков"
        verbose_name_plural = "Ревизии остатков"
        ordering = ['-created_at']
        unique_together = [['shift', 'product']]
        indexes = [
            models.Index(fields=['shift', 'product']),
        ]

    def __str__(self) -> str:
        return f"{self.product.name}: {self.quantity} ({self.shift})"

