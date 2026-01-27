"""
Tests for POS services.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.core.models import StaffProfile, Location
from apps.inventory.models import Product, Category
from apps.pos.models import Shift, Transaction, Payment
from apps.pos.services import ShiftService, TransactionService, ReportService

User = get_user_model()


class ShiftServiceTestCase(TestCase):
    """Test ShiftService."""

    def setUp(self):
        """Set up test data."""
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create location
        self.location = Location.objects.create(
            name='Test Bar',
            address='Test Address',
            is_active=True
        )

        # Create staff profile
        self.staff = StaffProfile.objects.create(
            user=self.user,
            telegram_id=123456789,
            role=StaffProfile.Role.CASHIER,
            location=self.location,
            is_active=True
        )

        # Create category
        self.category = Category.objects.create(
            name='Drinks',
            is_active=True
        )

        # Create product
        self.product = Product.objects.create(
            name='Beer',
            category=self.category,
            location=self.location,
            price=Decimal('500.00'),
            stock_quantity=Decimal('100.00'),
            unit='шт',
            is_active=True
        )

    def test_start_shift(self):
        """Test starting a shift."""
        shift = ShiftService.start_shift(
            staff=self.staff,
            location=self.location,
            notes='Test shift'
        )

        self.assertIsNotNone(shift)
        self.assertEqual(shift.staff, self.staff)
        self.assertEqual(shift.location, self.location)
        self.assertFalse(shift.is_closed)
        self.assertEqual(shift.total_sales, Decimal('0.00'))

    def test_cannot_start_multiple_shifts(self):
        """Test that only one shift can be open per location."""
        ShiftService.start_shift(self.staff, self.location)

        with self.assertRaises(ValidationError):
            ShiftService.start_shift(self.staff, self.location)

    def test_close_shift(self):
        """Test closing a shift."""
        shift = ShiftService.start_shift(self.staff, self.location)

        # Create a sale
        TransactionService.create_sale(
            shift=shift,
            product=self.product,
            qty=Decimal('2.00'),
            payment_method=Payment.PaymentMethod.CASH
        )

        # Close shift
        closed_shift = ShiftService.close_shift(shift)

        self.assertTrue(closed_shift.is_closed)
        self.assertIsNotNone(closed_shift.closed_at)
        self.assertEqual(closed_shift.total_sales, Decimal('1000.00'))
        self.assertEqual(closed_shift.total_cash, Decimal('1000.00'))


class TransactionServiceTestCase(TestCase):
    """Test TransactionService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.location = Location.objects.create(name='Test Bar', address='Test Address', is_active=True)
        self.staff = StaffProfile.objects.create(
            user=self.user,
            telegram_id=123456789,
            role=StaffProfile.Role.CASHIER,
            location=self.location,
            is_active=True
        )
        self.category = Category.objects.create(name='Drinks', is_active=True)
        self.product = Product.objects.create(
            name='Beer',
            category=self.category,
            location=self.location,
            price=Decimal('500.00'),
            stock_quantity=Decimal('100.00'),
            unit='шт',
            is_active=True
        )
        self.shift = ShiftService.start_shift(self.staff, self.location)

    def test_create_sale_cash(self):
        """Test creating a cash sale."""
        initial_stock = self.product.stock_quantity

        transaction = TransactionService.create_sale(
            shift=self.shift,
            product=self.product,
            qty=Decimal('2.00'),
            payment_method=Payment.PaymentMethod.CASH
        )

        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.SALE)
        self.assertEqual(transaction.qty, Decimal('2.00'))
        self.assertEqual(transaction.amount, Decimal('1000.00'))

        # Check stock decreased
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, initial_stock - Decimal('2.00'))

        # Check payment
        payment = transaction.payments.first()
        self.assertEqual(payment.method, Payment.PaymentMethod.CASH)
        self.assertEqual(payment.amount, Decimal('1000.00'))

    def test_create_sale_transfer(self):
        """Test creating a transfer sale."""
        transaction = TransactionService.create_sale(
            shift=self.shift,
            product=self.product,
            qty=Decimal('1.00'),
            payment_method=Payment.PaymentMethod.TRANSFER
        )

        payment = transaction.payments.first()
        self.assertEqual(payment.method, Payment.PaymentMethod.TRANSFER)
        self.assertEqual(payment.amount, Decimal('500.00'))

    def test_create_refund(self):
        """Test creating a refund."""
        # First create a sale
        TransactionService.create_sale(
            shift=self.shift,
            product=self.product,
            qty=Decimal('5.00'),
            payment_method=Payment.PaymentMethod.CASH
        )

        self.product.refresh_from_db()
        stock_after_sale = self.product.stock_quantity

        # Create refund
        refund = TransactionService.create_refund(
            shift=self.shift,
            product=self.product,
            qty=Decimal('2.00'),
            payment_method=Payment.PaymentMethod.CASH
        )

        self.assertEqual(refund.transaction_type, Transaction.TransactionType.REFUND)
        self.assertEqual(refund.qty, Decimal('2.00'))
        self.assertEqual(refund.amount, Decimal('1000.00'))

        # Check stock increased
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, stock_after_sale + Decimal('2.00'))

    def test_cannot_sell_more_than_stock(self):
        """Test that we cannot sell more than available stock."""
        with self.assertRaises(ValidationError):
            TransactionService.create_sale(
                shift=self.shift,
                product=self.product,
                qty=Decimal('200.00'),  # More than stock
                payment_method=Payment.PaymentMethod.CASH
            )


class ReportServiceTestCase(TestCase):
    """Test ReportService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.location = Location.objects.create(name='Test Bar', address='Test Address', is_active=True)
        self.staff = StaffProfile.objects.create(
            user=self.user,
            telegram_id=123456789,
            role=StaffProfile.Role.CASHIER,
            location=self.location,
            is_active=True
        )
        self.category = Category.objects.create(name='Drinks', is_active=True)
        self.product1 = Product.objects.create(
            name='Beer',
            category=self.category,
            location=self.location,
            price=Decimal('500.00'),
            stock_quantity=Decimal('100.00'),
            unit='шт',
            is_active=True
        )
        self.product2 = Product.objects.create(
            name='Vodka',
            category=self.category,
            location=self.location,
            price=Decimal('1000.00'),
            stock_quantity=Decimal('50.00'),
            unit='шт',
            is_active=True
        )
        self.shift = ShiftService.start_shift(self.staff, self.location)

    def test_shift_summary_with_sales(self):
        """Test shift summary with sales."""
        # Create sales
        TransactionService.create_sale(self.shift, self.product1, Decimal('3.00'), Payment.PaymentMethod.CASH)
        TransactionService.create_sale(self.shift, self.product2, Decimal('2.00'), Payment.PaymentMethod.CARD)
        TransactionService.create_sale(self.shift, self.product1, Decimal('1.00'), Payment.PaymentMethod.TRANSFER)

        summary = ReportService.get_shift_summary(self.shift)

        self.assertEqual(summary['sales_count'], 3)
        self.assertEqual(summary['sales_total'], Decimal('4000.00'))  # 1500 + 2000 + 500
        self.assertEqual(summary['total_cash'], Decimal('1500.00'))
        self.assertEqual(summary['total_card'], Decimal('2000.00'))
        self.assertEqual(summary['total_transfer'], Decimal('500.00'))

    def test_shift_summary_with_refunds(self):
        """Test shift summary with refunds."""
        # Create sale and refund
        TransactionService.create_sale(self.shift, self.product1, Decimal('5.00'), Payment.PaymentMethod.CASH)
        TransactionService.create_refund(self.shift, self.product1, Decimal('2.00'), Payment.PaymentMethod.CASH)

        summary = ReportService.get_shift_summary(self.shift)

        self.assertEqual(summary['sales_count'], 1)
        self.assertEqual(summary['refunds_count'], 1)
        self.assertEqual(summary['sales_total'], Decimal('2500.00'))
        self.assertEqual(summary['refunds_total'], Decimal('1000.00'))
        self.assertEqual(summary['net_total'], Decimal('1500.00'))
        self.assertEqual(summary['total_cash'], Decimal('1500.00'))  # 2500 - 1000


class ReportDetailsTestCase(TestCase):
    """Test detailed report methods."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.location = Location.objects.create(name='Test Bar', address='Test Address', is_active=True)
        self.staff = StaffProfile.objects.create(
            user=self.user,
            telegram_id=123456789,
            role=StaffProfile.Role.CASHIER,
            location=self.location,
            is_active=True
        )
        self.category = Category.objects.create(name='Drinks', is_active=True)
        self.product1 = Product.objects.create(
            name='Beer',
            category=self.category,
            location=self.location,
            price=Decimal('500.00'),
            stock_quantity=Decimal('100.00'),
            unit='шт',
            is_active=True
        )
        self.product2 = Product.objects.create(
            name='Vodka',
            category=self.category,
            location=self.location,
            price=Decimal('1000.00'),
            stock_quantity=Decimal('50.00'),
            unit='шт',
            is_active=True
        )
        self.shift = ShiftService.start_shift(self.staff, self.location)

    def test_get_sales_details(self):
        """Test get_sales_details returns correct sales list."""
        # Create sales with different payment methods
        TransactionService.create_sale(self.shift, self.product1, Decimal('3.00'), Payment.PaymentMethod.CASH)
        TransactionService.create_sale(self.shift, self.product2, Decimal('2.00'), Payment.PaymentMethod.CARD)
        TransactionService.create_sale(self.shift, self.product1, Decimal('1.00'), Payment.PaymentMethod.TRANSFER)

        details = ReportService.get_sales_details(self.shift)

        # Should have 3 sales
        self.assertEqual(len(details), 3)

        # Check first sale
        self.assertEqual(details[0]['product'], 'Beer')
        self.assertEqual(details[0]['qty'], Decimal('3.00'))
        self.assertEqual(details[0]['amount'], Decimal('1500.00'))
        self.assertEqual(details[0]['payment_method'], 'Наличные')
        self.assertEqual(details[0]['payment_method_code'], Payment.PaymentMethod.CASH)

        # Check second sale
        self.assertEqual(details[1]['product'], 'Vodka')
        self.assertEqual(details[1]['qty'], Decimal('2.00'))
        self.assertEqual(details[1]['amount'], Decimal('2000.00'))
        self.assertEqual(details[1]['payment_method'], 'Карта')
        self.assertEqual(details[1]['payment_method_code'], Payment.PaymentMethod.CARD)

        # Check third sale
        self.assertEqual(details[2]['product'], 'Beer')
        self.assertEqual(details[2]['qty'], Decimal('1.00'))
        self.assertEqual(details[2]['amount'], Decimal('500.00'))
        self.assertEqual(details[2]['payment_method'], 'Перевод')
        self.assertEqual(details[2]['payment_method_code'], Payment.PaymentMethod.TRANSFER)

    def test_get_sales_details_empty(self):
        """Test get_sales_details returns empty list when no sales."""
        details = ReportService.get_sales_details(self.shift)
        self.assertEqual(len(details), 0)
        self.assertEqual(details, [])

    def test_get_refunds_details(self):
        """Test get_refunds_details returns correct refunds list."""
        # Create sales first
        TransactionService.create_sale(self.shift, self.product1, Decimal('5.00'), Payment.PaymentMethod.CASH)
        TransactionService.create_sale(self.shift, self.product2, Decimal('3.00'), Payment.PaymentMethod.CARD)

        # Create refunds
        TransactionService.create_refund(self.shift, self.product1, Decimal('2.00'), Payment.PaymentMethod.CASH)
        TransactionService.create_refund(self.shift, self.product2, Decimal('1.00'), Payment.PaymentMethod.CARD)

        details = ReportService.get_refunds_details(self.shift)

        # Should have 2 refunds
        self.assertEqual(len(details), 2)

        # Check first refund
        self.assertEqual(details[0]['product'], 'Beer')
        self.assertEqual(details[0]['qty'], Decimal('2.00'))
        self.assertEqual(details[0]['amount'], Decimal('1000.00'))
        self.assertEqual(details[0]['payment_method'], 'Наличные')
        self.assertEqual(details[0]['payment_method_code'], Payment.PaymentMethod.CASH)

        # Check second refund
        self.assertEqual(details[1]['product'], 'Vodka')
        self.assertEqual(details[1]['qty'], Decimal('1.00'))
        self.assertEqual(details[1]['amount'], Decimal('1000.00'))
        self.assertEqual(details[1]['payment_method'], 'Карта')
        self.assertEqual(details[1]['payment_method_code'], Payment.PaymentMethod.CARD)

    def test_get_refunds_details_empty(self):
        """Test get_refunds_details returns empty list when no refunds."""
        details = ReportService.get_refunds_details(self.shift)
        self.assertEqual(len(details), 0)
        self.assertEqual(details, [])

    def test_get_inventory_report(self):
        """Test get_inventory_report returns correct inventory."""
        # Create another category and products
        category2 = Category.objects.create(name='Food', is_active=True)
        product3 = Product.objects.create(
            name='Pizza',
            category=category2,
            location=self.location,
            price=Decimal('1500.00'),
            stock_quantity=Decimal('20.00'),
            unit='шт',
            is_active=True
        )

        inventory = ReportService.get_inventory_report(self.location)

        # Should have 3 products
        self.assertEqual(len(inventory), 3)

        # Check products are grouped by category
        drinks = [item for item in inventory if item['category'] == 'Drinks']
        food = [item for item in inventory if item['category'] == 'Food']

        self.assertEqual(len(drinks), 2)
        self.assertEqual(len(food), 1)

        # Check Beer details
        beer = next(item for item in inventory if item['product'] == 'Beer')
        self.assertEqual(beer['stock'], Decimal('100.00'))
        self.assertEqual(beer['unit'], 'шт')
        self.assertEqual(beer['price'], Decimal('500.00'))

        # Check Pizza details
        pizza = next(item for item in inventory if item['product'] == 'Pizza')
        self.assertEqual(pizza['stock'], Decimal('20.00'))
        self.assertEqual(pizza['unit'], 'шт')
        self.assertEqual(pizza['price'], Decimal('1500.00'))

    def test_get_financial_report(self):
        """Test get_financial_report calculates totals correctly."""
        # Create mixed transactions
        TransactionService.create_sale(self.shift, self.product1, Decimal('3.00'), Payment.PaymentMethod.CASH)
        TransactionService.create_sale(self.shift, self.product2, Decimal('2.00'), Payment.PaymentMethod.CARD)
        TransactionService.create_sale(self.shift, self.product1, Decimal('1.00'), Payment.PaymentMethod.TRANSFER)

        financial = ReportService.get_financial_report(self.shift)

        # Check totals
        self.assertEqual(financial['sales_total'], Decimal('4000.00'))
        self.assertEqual(financial['refunds_total'], Decimal('0.00'))
        self.assertEqual(financial['net_total'], Decimal('4000.00'))

        # Check payment method breakdown
        self.assertEqual(financial['net_cash'], Decimal('1500.00'))
        self.assertEqual(financial['net_card'], Decimal('2000.00'))
        self.assertEqual(financial['net_transfer'], Decimal('500.00'))

        # Check total in register
        self.assertEqual(financial['total_in_register'], Decimal('4000.00'))

    def test_get_financial_report_with_refunds(self):
        """Test get_financial_report with sales and refunds."""
        # Create sales
        TransactionService.create_sale(self.shift, self.product1, Decimal('5.00'), Payment.PaymentMethod.CASH)
        TransactionService.create_sale(self.shift, self.product2, Decimal('3.00'), Payment.PaymentMethod.CARD)

        # Create refunds
        TransactionService.create_refund(self.shift, self.product1, Decimal('2.00'), Payment.PaymentMethod.CASH)
        TransactionService.create_refund(self.shift, self.product2, Decimal('1.00'), Payment.PaymentMethod.CARD)

        financial = ReportService.get_financial_report(self.shift)

        # Check totals
        self.assertEqual(financial['sales_total'], Decimal('5500.00'))  # 2500 + 3000
        self.assertEqual(financial['refunds_total'], Decimal('2000.00'))  # 1000 + 1000
        self.assertEqual(financial['net_total'], Decimal('3500.00'))  # 5500 - 2000

        # Check payment method breakdown (net after refunds)
        self.assertEqual(financial['net_cash'], Decimal('1500.00'))  # 2500 - 1000
        self.assertEqual(financial['net_card'], Decimal('2000.00'))  # 3000 - 1000
        self.assertEqual(financial['net_transfer'], Decimal('0.00'))

        # Check total in register
        self.assertEqual(financial['total_in_register'], Decimal('3500.00'))  # 1500 + 2000 + 0


