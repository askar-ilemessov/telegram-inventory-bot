"""
Inventory models: Category, Product
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import F
from apps.core.models import Location
from django.contrib.auth.models import User


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

    def save(self, *args, **kwargs):
        """Auto-create StorageStock when Product is created."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Auto-create StorageStock (required)
            StorageStock.objects.get_or_create(
                product=self,
                location=self.location,
                defaults={'quantity': Decimal('0.00')}
            )

    @property
    def stock_quantity(self) -> Decimal:
        """
        Total stock quantity (storage + display).
        Returns sum of StorageStock and DisplayStock quantities.
        """
        storage = getattr(self, 'storage_stock', None)
        display = getattr(self, 'display_stock', None)
        
        storage_qty = storage.quantity if storage else Decimal('0.00')
        display_qty = display.quantity if display else Decimal('0.00')
        
        return storage_qty + display_qty

    @property
    def is_in_stock(self) -> bool:
        """Check if product is in stock (storage or display)."""
        return self.stock_quantity > Decimal('0.00')


class StorageStock(models.Model):
    """
    Storage inventory for each product.
    Auto-created when Product is created.
    """
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='storage_stock',
        verbose_name="Товар"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='storage_stocks',
        verbose_name="Локация"
    )
    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Количество на складе"
    )
    last_purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Последняя цена закупки"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Остаток на складе"
        verbose_name_plural = "Остатки на складе"
        ordering = ['product__name']
        indexes = [
            models.Index(fields=['location', 'product']),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} (склад): {self.quantity}"

    def update_quantity(self, delta: Decimal) -> None:
        """Update stock quantity (thread-safe)."""
        self.quantity = F('quantity') + delta
        self.save(update_fields=['quantity'])
        self.refresh_from_db()


class DisplayStock(models.Model):
    """
    Display inventory for each product.
    Created manually when needed (transfer from storage).
    """
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='display_stock',
        verbose_name="Товар"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='display_stocks',
        verbose_name="Локация"
    )
    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Количество на витрине"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Остаток на витрине"
        verbose_name_plural = "Остатки на витрине"
        ordering = ['product__name']
        indexes = [
            models.Index(fields=['location', 'product']),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} (витрина): {self.quantity}"

    def update_quantity(self, delta: Decimal) -> None:
        """Update stock quantity (thread-safe)."""
        self.quantity = F('quantity') + delta
        self.save(update_fields=['quantity'])
        self.refresh_from_db()


class PurchaseTransaction(models.Model):
    """
    Purchase transaction (supplier → storage).
    Increases StorageStock.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name="Товар"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name="Локация"
    )
    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Количество"
    )
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена закупки за единицу"
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Общая стоимость"
    )
    supplier = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Поставщик"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name="Создал"
    )
    notes = models.TextField(blank=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата закупки")

    class Meta:
        verbose_name = "Закупка"
        verbose_name_plural = "Закупки"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['location', 'created_at']),
            models.Index(fields=['product', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"Закупка: {self.product.name} x{self.quantity} ({self.created_at.date()})"

    def save(self, *args, **kwargs):
        """Auto-calculate total_cost."""
        if not self.total_cost:
            self.total_cost = self.quantity * self.purchase_price
        super().save(*args, **kwargs)


class TransferTransaction(models.Model):
    """
    Transfer transaction (storage → display).
    Decreases StorageStock, increases DisplayStock.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='transfers',
        verbose_name="Товар"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='transfers',
        verbose_name="Локация"
    )
    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Количество"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='transfers',
        verbose_name="Создал"
    )
    notes = models.TextField(blank=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата перемещения")

    class Meta:
        verbose_name = "Перемещение"
        verbose_name_plural = "Перемещения"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['location', 'created_at']),
            models.Index(fields=['product', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"Перемещение: {self.product.name} x{self.quantity} ({self.created_at.date()})"
