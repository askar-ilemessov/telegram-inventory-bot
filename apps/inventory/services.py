"""
Inventory Business Logic Services.
Handles purchases and transfers.
"""
from decimal import Decimal
from typing import Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from apps.core.models import Location
from .models import Product, StorageStock, DisplayStock, PurchaseTransaction, TransferTransaction


class InventoryService:
    """Service for managing inventory operations."""

    @staticmethod
    @transaction.atomic
    def purchase(
        product: Product,
        location: Location,
        quantity: Decimal,
        purchase_price: Decimal,
        created_by: User,
        supplier: str = "",
        notes: str = ""
    ) -> PurchaseTransaction:
        """
        Create purchase transaction and update storage stock.
        
        Args:
            product: Product being purchased
            location: Location for purchase
            quantity: Quantity purchased
            purchase_price: Price per unit
            created_by: User creating the purchase
            supplier: Supplier name (optional)
            notes: Additional notes (optional)
            
        Returns:
            Created PurchaseTransaction instance
            
        Raises:
            ValidationError: If validation fails
        """
        if quantity <= Decimal('0.00'):
            raise ValidationError("Количество должно быть больше нуля")
        
        if purchase_price < Decimal('0.00'):
            raise ValidationError("Цена закупки не может быть отрицательной")
        
        # Lock StorageStock for update (auto-create if missing for legacy products)
        storage_stock, _ = StorageStock.objects.select_for_update().get_or_create(
            product=product,
            location=location,
            defaults={'quantity': Decimal('0.00')}
        )

        # Create purchase transaction
        purchase = PurchaseTransaction.objects.create(
            product=product,
            location=location,
            quantity=quantity,
            purchase_price=purchase_price,
            total_cost=quantity * purchase_price,
            supplier=supplier,
            created_by=created_by,
            notes=notes
        )
        
        # Update storage stock
        storage_stock.update_quantity(quantity)
        storage_stock.last_purchase_price = purchase_price
        storage_stock.save(update_fields=['last_purchase_price'])
        
        return purchase

    @staticmethod
    @transaction.atomic
    def transfer(
        product: Product,
        location: Location,
        quantity: Decimal,
        created_by: User,
        notes: str = ""
    ) -> TransferTransaction:
        """
        Transfer product from storage to display.
        
        Args:
            product: Product being transferred
            location: Location for transfer
            quantity: Quantity to transfer
            created_by: User creating the transfer
            notes: Additional notes (optional)
            
        Returns:
            Created TransferTransaction instance
            
        Raises:
            ValidationError: If validation fails or insufficient stock
        """
        if quantity <= Decimal('0.00'):
            raise ValidationError("Количество должно быть больше нуля")
        
        # Lock both stocks for update (auto-create if missing for legacy products)
        storage_stock, _ = StorageStock.objects.select_for_update().get_or_create(
            product=product,
            location=location,
            defaults={'quantity': Decimal('0.00')}
        )
        
        # Validate storage stock
        if storage_stock.quantity < quantity:
            raise ValidationError(
                f"Недостаточно товара на складе. Доступно: {storage_stock.quantity}"
            )
        
        # Get or create DisplayStock
        display_stock, created = DisplayStock.objects.select_for_update().get_or_create(
            product=product,
            location=location,
            defaults={'quantity': Decimal('0.00')}
        )
        
        # Create transfer transaction
        transfer = TransferTransaction.objects.create(
            product=product,
            location=location,
            quantity=quantity,
            created_by=created_by,
            notes=notes
        )
        
        # Update stocks
        storage_stock.update_quantity(-quantity)
        display_stock.update_quantity(quantity)
        
        return transfer