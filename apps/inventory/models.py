"""
Inventory models: Category, Product
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import Location


class Category(models.Model):
    """
    Product category (e.g., Drinks, Food, Snacks).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """
    Product in inventory.
    Uses Decimal for price to ensure precision.
    """
    name = models.CharField(max_length=200, verbose_name="Название")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name="Категория"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Локация"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Цена"
    )
    unit = models.CharField(
        max_length=20,
        default='шт',
        verbose_name="Единица измерения"
    )
    stock_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Остаток на складе"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['category', 'name']
        unique_together = [['name', 'location']]
        indexes = [
            models.Index(fields=['location', 'is_active']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.location.name})"

    def update_stock(self, quantity: Decimal) -> None:
        """
        Update stock quantity.
        
        Args:
            quantity: Quantity to add (positive) or subtract (negative)
        """
        self.stock_quantity += quantity
        self.save(update_fields=['stock_quantity', 'updated_at'])

    @property
    def is_in_stock(self) -> bool:
        """Check if product is in stock."""
        return self.stock_quantity > Decimal('0.00')

