"""
POS Business Logic Services.
All transaction operations must go through these services.
"""
from decimal import Decimal
from typing import Dict, List, Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import StaffProfile, Location
from apps.inventory.models import Product
from .models import Shift, Transaction, Payment, StockCount


class ShiftService:
    """Service for managing shifts."""
    
    @staticmethod
    @transaction.atomic
    def start_shift(staff: StaffProfile, location: Location, notes: str = "") -> Shift:
        """
        Start a new shift for staff at location.
        
        Args:
            staff: StaffProfile instance
            location: Location instance
            notes: Optional notes
            
        Returns:
            Created Shift instance
            
        Raises:
            ValidationError: If shift already exists or validation fails
        """
        # Check if there's already an open shift at this location
        existing_shift = Shift.objects.filter(
            location=location,
            is_closed=False
        ).first()
        
        if existing_shift:
            raise ValidationError(
                f"В локации {location.name} уже открыта смена сотрудником {existing_shift.staff.full_name}"
            )
        
        # Create new shift
        shift = Shift.objects.create(
            staff=staff,
            location=location,
            notes=notes
        )
        
        return shift
    
    @staticmethod
    @transaction.atomic
    def close_shift(shift: Shift, stock_counts: Optional[Dict[int, Decimal]] = None) -> Shift:
        """
        Close a shift and calculate totals.
        
        Args:
            shift: Shift instance to close
            stock_counts: Optional dict of {product_id: quantity} for stock count
            
        Returns:
            Updated Shift instance
            
        Raises:
            ValidationError: If shift is already closed
        """
        if shift.is_closed:
            raise ValidationError("Смена уже закрыта")
        
        # Calculate totals from transactions
        transactions = shift.transactions.filter(
            transaction_type=Transaction.TransactionType.SALE
        ).select_related('product')
        
        total_sales = sum(
            (t.amount for t in transactions),
            Decimal('0.00')
        )
        
        # Calculate payment method totals
        total_cash = Decimal('0.00')
        total_card = Decimal('0.00')
        total_transfer = Decimal('0.00')

        for trans in transactions:
            payments = trans.payments.all()
            for payment in payments:
                if payment.method == Payment.PaymentMethod.CASH:
                    total_cash += payment.amount
                elif payment.method == Payment.PaymentMethod.CARD:
                    total_card += payment.amount
                elif payment.method == Payment.PaymentMethod.TRANSFER:
                    total_transfer += payment.amount

        # Update shift
        shift.is_closed = True
        shift.closed_at = timezone.now()
        shift.total_sales = total_sales
        shift.total_cash = total_cash
        shift.total_card = total_card
        shift.total_transfer = total_transfer
        shift.save()
        
        # Create stock count snapshots if provided
        if stock_counts:
            for product_id, quantity in stock_counts.items():
                try:
                    product = Product.objects.get(id=product_id)
                    StockCount.objects.create(
                        shift=shift,
                        product=product,
                        quantity=quantity
                    )
                except Product.DoesNotExist:
                    pass  # Skip invalid product IDs
        
        return shift


class TransactionService:
    """Service for managing transactions."""
    
    @staticmethod
    @transaction.atomic
    def create_sale(
        shift: Shift,
        product: Product,
        qty: Decimal,
        payment_method: str,
        notes: str = ""
    ) -> Transaction:
        """
        Create a sale transaction with payment.
        Uses select_for_update to prevent race conditions.
        
        Args:
            shift: Active Shift instance
            product: Product being sold
            qty: Quantity sold (must be positive)
            payment_method: Payment method (CASH, CARD, TRANSFER)
            notes: Optional notes
            
        Returns:
            Created Transaction instance
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate shift is open
        if shift.is_closed:
            raise ValidationError("Смена закрыта. Невозможно создать продажу.")
        
        # Validate shift location matches product location
        if shift.location != product.location:
            raise ValidationError(
                f"Товар {product.name} не принадлежит локации {shift.location.name}"
            )
        
        # Validate product is active
        if not product.is_active:
            raise ValidationError(f"Товар {product.name} неактивен")
        
        # Validate quantity
        if qty <= Decimal('0.00'):
            raise ValidationError("Количество должно быть больше нуля")

        # Lock product row to prevent concurrent modifications
        product = Product.objects.select_for_update().get(pk=product.pk)

        # Validate sufficient stock
        if product.stock_quantity < qty:
            raise ValidationError(
                f"Недостаточно товара {product.name}. "
                f"В наличии: {product.stock_quantity}, требуется: {qty}"
            )

        # Calculate amount
        amount = product.price * qty

        # Create transaction
        trans = Transaction.objects.create(
            shift=shift,
            product=product,
            transaction_type=Transaction.TransactionType.SALE,
            qty=qty,
            amount=amount,
            notes=notes
        )

        # Create payment
        Payment.objects.create(
            transaction=trans,
            method=payment_method,
            amount=amount
        )

        # Update product stock
        product.update_stock(-qty)

        return trans

    @staticmethod
    @transaction.atomic
    def create_refund(
        shift: Shift,
        product: Product,
        qty: Decimal,
        payment_method: str,
        notes: str = ""
    ) -> Transaction:
        """
        Create a refund transaction.

        Args:
            shift: Active Shift instance
            product: Product being refunded
            qty: Quantity refunded (must be positive)
            payment_method: Payment method for refund
            notes: Optional notes

        Returns:
            Created Transaction instance

        Raises:
            ValidationError: If validation fails
        """
        # Validate shift is open
        if shift.is_closed:
            raise ValidationError("Смена закрыта. Невозможно создать возврат.")

        # Validate quantity
        if qty <= Decimal('0.00'):
            raise ValidationError("Количество должно быть больше нуля")

        # Lock product row
        product = Product.objects.select_for_update().get(pk=product.pk)

        # Calculate amount
        amount = product.price * qty

        # Create transaction
        trans = Transaction.objects.create(
            shift=shift,
            product=product,
            transaction_type=Transaction.TransactionType.REFUND,
            qty=qty,
            amount=amount,
            notes=notes
        )

        # Create payment (negative for refund)
        Payment.objects.create(
            transaction=trans,
            method=payment_method,
            amount=amount
        )

        # Update product stock (add back)
        product.update_stock(qty)

        return trans

    @staticmethod
    @transaction.atomic
    def create_adjustment(
        shift: Shift,
        product: Product,
        qty: Decimal,
        notes: str = ""
    ) -> Transaction:
        """
        Create an inventory adjustment transaction.

        Args:
            shift: Active Shift instance
            product: Product being adjusted
            qty: Quantity adjustment (can be positive or negative)
            notes: Reason for adjustment

        Returns:
            Created Transaction instance

        Raises:
            ValidationError: If validation fails
        """
        if shift.is_closed:
            raise ValidationError("Смена закрыта.")

        if qty == Decimal('0.00'):
            raise ValidationError("Количество корректировки не может быть нулевым")

        # Lock product row
        product = Product.objects.select_for_update().get(pk=product.pk)

        # Create transaction (amount is 0 for adjustments)
        trans = Transaction.objects.create(
            shift=shift,
            product=product,
            transaction_type=Transaction.TransactionType.ADJUSTMENT,
            qty=abs(qty),
            amount=Decimal('0.00'),
            notes=notes
        )

        # Update product stock
        product.update_stock(qty)

        return trans


class ReportService:
    """Service for generating reports."""

    @staticmethod
    def get_shift_summary(shift: Shift) -> Dict:
        """
        Get summary of shift transactions.

        Args:
            shift: Shift instance

        Returns:
            Dictionary with shift summary
        """
        transactions = shift.transactions.select_related('product').prefetch_related('payments')

        sales = transactions.filter(transaction_type=Transaction.TransactionType.SALE)
        refunds = transactions.filter(transaction_type=Transaction.TransactionType.REFUND)

        sales_count = sales.count()
        sales_total = sum((t.amount for t in sales), Decimal('0.00'))

        refunds_count = refunds.count()
        refunds_total = sum((t.amount for t in refunds), Decimal('0.00'))

        net_total = sales_total - refunds_total

        # Calculate payment method totals from actual transactions (not from shift fields)
        # This works for both open and closed shifts
        total_cash = Decimal('0.00')
        total_card = Decimal('0.00')
        total_transfer = Decimal('0.00')

        for trans in sales:
            for payment in trans.payments.all():
                if payment.method == Payment.PaymentMethod.CASH:
                    total_cash += payment.amount
                elif payment.method == Payment.PaymentMethod.CARD:
                    total_card += payment.amount
                elif payment.method == Payment.PaymentMethod.TRANSFER:
                    total_transfer += payment.amount

        # Subtract refunds from payment totals
        for trans in refunds:
            for payment in trans.payments.all():
                if payment.method == Payment.PaymentMethod.CASH:
                    total_cash -= payment.amount
                elif payment.method == Payment.PaymentMethod.CARD:
                    total_card -= payment.amount
                elif payment.method == Payment.PaymentMethod.TRANSFER:
                    total_transfer -= payment.amount

        # Group sales by product
        product_summary: Dict[str, Dict] = {}
        for trans in sales:
            product_name = trans.product.name
            if product_name not in product_summary:
                product_summary[product_name] = {
                    'qty': Decimal('0.00'),
                    'amount': Decimal('0.00')
                }
            product_summary[product_name]['qty'] += trans.qty
            product_summary[product_name]['amount'] += trans.amount

        # Group refunds by product
        refund_summary: Dict[str, Dict] = {}
        for trans in refunds:
            product_name = trans.product.name
            if product_name not in refund_summary:
                refund_summary[product_name] = {
                    'qty': Decimal('0.00'),
                    'amount': Decimal('0.00')
                }
            refund_summary[product_name]['qty'] += trans.qty
            refund_summary[product_name]['amount'] += trans.amount

        return {
            'shift': shift,
            'sales_count': sales_count,
            'sales_total': sales_total,
            'refunds_count': refunds_count,
            'refunds_total': refunds_total,
            'net_total': net_total,
            'total_cash': total_cash,
            'total_card': total_card,
            'total_transfer': total_transfer,
            'product_summary': product_summary,
            'refund_summary': refund_summary,
        }

    @staticmethod
    def get_sales_details(shift: Shift) -> List[Dict]:
        """
        Get detailed list of all sales transactions.

        Args:
            shift: Shift instance

        Returns:
            List of dictionaries with sale details
        """
        sales = shift.transactions.filter(
            transaction_type=Transaction.TransactionType.SALE
        ).select_related('product').prefetch_related('payments').order_by('created_at')

        details = []
        for trans in sales:
            payment = trans.payments.first()
            details.append({
                'time': trans.created_at,
                'product': trans.product.name,
                'qty': trans.qty,
                'amount': trans.amount,
                'payment_method': payment.get_method_display() if payment else 'Н/Д',
                'payment_method_code': payment.method if payment else None,
            })

        return details

    @staticmethod
    def get_refunds_details(shift: Shift) -> List[Dict]:
        """
        Get detailed list of all refund transactions.

        Args:
            shift: Shift instance

        Returns:
            List of dictionaries with refund details
        """
        refunds = shift.transactions.filter(
            transaction_type=Transaction.TransactionType.REFUND
        ).select_related('product').prefetch_related('payments').order_by('created_at')

        details = []
        for trans in refunds:
            payment = trans.payments.first()
            details.append({
                'time': trans.created_at,
                'product': trans.product.name,
                'qty': trans.qty,
                'amount': trans.amount,
                'payment_method': payment.get_method_display() if payment else 'Н/Д',
                'payment_method_code': payment.method if payment else None,
            })

        return details

    @staticmethod
    def get_inventory_report(location) -> List[Dict]:
        """
        Get inventory report for a location.

        Args:
            location: Location instance

        Returns:
            List of dictionaries with product inventory
        """
        from apps.inventory.models import Product

        products = Product.objects.filter(
            location=location,
            is_active=True
        ).select_related('category').order_by('category__name', 'name')

        inventory = []
        for product in products:
            inventory.append({
                'category': product.category.name,
                'product': product.name,
                'stock': product.stock_quantity,
                'unit': product.unit,
                'price': product.price,
            })

        return inventory

    @staticmethod
    def get_financial_report(shift: Shift) -> Dict:
        """
        Get detailed financial report.

        Args:
            shift: Shift instance

        Returns:
            Dictionary with financial details
        """
        summary = ReportService.get_shift_summary(shift)

        # Calculate net by payment method
        net_cash = summary['total_cash']
        net_card = summary['total_card']
        net_transfer = summary['total_transfer']
        total_in_register = net_cash + net_card + net_transfer

        return {
            'total_in_register': total_in_register,
            'net_cash': net_cash,
            'net_card': net_card,
            'net_transfer': net_transfer,
            'sales_total': summary['sales_total'],
            'refunds_total': summary['refunds_total'],
            'net_total': summary['net_total'],
        }

