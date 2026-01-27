"""
Telegram Bot Handlers.
"""
import logging
from decimal import Decimal, InvalidOperation
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError
from apps.core.models import StaffProfile
from apps.inventory.models import Product
from apps.pos.models import Shift
from apps.pos.services import ShiftService, TransactionService, ReportService
from .states import SaleStates, RefundStates, ShiftStates
from .keyboards import (
    get_main_menu_keyboard,
    get_shift_menu_keyboard,
    get_payment_method_keyboard,
    get_cancel_keyboard,
    get_confirmation_keyboard,
    get_categories_inline_keyboard,
    get_products_inline_keyboard,
    parse_payment_method
)
from .shift_logger import ShiftLogger

logger = logging.getLogger('bot')
router = Router()


# ============================================================================
# START & MAIN MENU
# ============================================================================

@router.message(Command("start"))
async def cmd_start(message: Message, staff_profile: StaffProfile = None):
    """Handle /start command."""
    if not staff_profile:
        await message.answer(
            "👋 Добро пожаловать в Inventory POS Bot!\n\n"
            "❌ У вас нет доступа к боту.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return
    
    await message.answer(
        f"👋 Привет, {staff_profile.full_name}!\n\n"
        f"📍 Локация: {staff_profile.location.name if staff_profile.location else 'Не назначена'}\n"
        f"👤 Роль: {staff_profile.get_role_display()}\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(F.text == "◀️ Назад")
async def back_to_main(message: Message, state: FSMContext):
    """Return to main menu."""
    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(F.text == "❌ Отмена")
async def cancel_action(message: Message, state: FSMContext):
    """Cancel current action and return to main menu."""
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=get_main_menu_keyboard()
    )


# ============================================================================
# SHIFT MANAGEMENT
# ============================================================================

@router.message(F.text == "📊 Смена")
async def shift_menu(message: Message, staff_profile: StaffProfile):
    """Show shift management menu."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация. Обратитесь к администратору.")
        return

    # Check if there's an open shift
    @sync_to_async
    def get_open_shift():
        shift = Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).select_related('staff__user', 'location').first()

        if shift:
            return {
                'staff_name': shift.staff.full_name,
                'location_name': shift.location.name,
                'started_at': shift.started_at,
            }
        return None

    shift_data = await get_open_shift()
    has_open_shift = shift_data is not None

    if has_open_shift:
        shift_info = (
            f"🟢 Смена открыта\n\n"
            f"👤 Сотрудник: {shift_data['staff_name']}\n"
            f"📍 Локация: {shift_data['location_name']}\n"
            f"🕐 Начало: {shift_data['started_at'].strftime('%d.%m.%Y %H:%M')}\n"
        )
    else:
        shift_info = "🔴 Смена не открыта"

    await message.answer(
        shift_info,
        reply_markup=get_shift_menu_keyboard(has_open_shift)
    )


@router.message(F.text == "🟢 Открыть смену")
async def open_shift(message: Message, staff_profile: StaffProfile):
    """Open a new shift."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    try:
        @sync_to_async
        def start_shift():
            return ShiftService.start_shift(
                staff=staff_profile,
                location=staff_profile.location
            )

        shift = await start_shift()

        # Log shift start
        await sync_to_async(ShiftLogger.log_shift_start)(shift)

        await message.answer(
            f"✅ Смена открыта!\n\n"
            f"📍 Локация: {shift.location.name}\n"
            f"🕐 Время: {shift.started_at.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=get_main_menu_keyboard()
        )

        logger.info(f"Shift {shift.id} opened by {staff_profile.full_name}")

    except ValidationError as e:
        await message.answer(f"❌ Ошибка: {e.message}")


@router.message(F.text == "🔴 Закрыть смену")
async def close_shift_confirm(message: Message, staff_profile: StaffProfile, state: FSMContext):
    """Ask for confirmation to close shift."""
    @sync_to_async
    def can_close():
        return staff_profile.can_close_shift()

    if not await can_close():
        await message.answer("❌ У вас нет прав на закрытие смены.")
        return

    @sync_to_async
    def get_open_shift_and_summary():
        shift = Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).first()
        if shift:
            summary = ReportService.get_shift_summary(shift)
            return shift, summary
        return None, None

    open_shift, summary = await get_open_shift_and_summary()

    if not open_shift:
        await message.answer("❌ Нет открытой смены.")
        return

    summary_text = (
        f"📊 Итоги смены:\n\n"
        f"💰 Продажи: {summary['sales_total']}₸ ({summary['sales_count']} шт)\n"
        f"↩️ Возвраты: {summary['refunds_total']}₸ ({summary['refunds_count']} шт)\n"
        f"💵 Наличные: {summary['total_cash']}₸\n"
        f"💳 Карта: {summary['total_card']}₸\n\n"
        f"Закрыть смену?"
    )

    await state.set_state(ShiftStates.waiting_for_close_confirmation)
    await state.update_data(shift_id=open_shift.id)

    await message.answer(
        summary_text,
        reply_markup=get_confirmation_keyboard()
    )


@router.message(ShiftStates.waiting_for_close_confirmation, F.text == "✅ Да")
async def close_shift_confirmed(message: Message, state: FSMContext):
    """Close shift after confirmation."""
    data = await state.get_data()
    shift_id = data.get('shift_id')

    try:
        @sync_to_async
        def close_shift():
            shift = Shift.objects.get(id=shift_id)
            summary = ReportService.get_shift_summary(shift)
            ShiftService.close_shift(shift)
            return shift, summary

        shift, summary = await close_shift()

        # Log shift close
        await sync_to_async(ShiftLogger.log_shift_close)(shift, summary)

        await message.answer(
            f"✅ Смена закрыта!\n\n"
            f"💰 Итого продаж: {shift.total_sales}₸\n"
            f"💵 Наличные: {shift.total_cash}₸\n"
            f"💳 Карта: {shift.total_card}₸\n"
            f"📱 Перевод: {shift.total_transfer}₸",
            reply_markup=get_main_menu_keyboard()
        )

        logger.info(f"Shift {shift.id} closed")

    except Exception as e:
        await message.answer(f"❌ Ошибка при закрытии смены: {e}")
        logger.error(f"Error closing shift: {e}")

    await state.clear()


@router.message(ShiftStates.waiting_for_close_confirmation, F.text == "❌ Нет")
async def close_shift_cancelled(message: Message, state: FSMContext):
    """Cancel shift closing."""
    await state.clear()
    await message.answer(
        "Закрытие смены отменено.",
        reply_markup=get_main_menu_keyboard()
    )


# ============================================================================
# SALES
# ============================================================================

@router.message(F.text == "📦 Продажа")
async def start_sale(message: Message, staff_profile: StaffProfile, state: FSMContext):
    """Start sale process."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    # Check if shift is open
    @sync_to_async
    def get_open_shift():
        return Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).first()

    open_shift = await get_open_shift()

    if not open_shift:
        await message.answer("❌ Смена не открыта. Откройте смену для продажи.")
        return

    await state.set_state(SaleStates.waiting_for_product)
    await state.update_data(shift_id=open_shift.id)

    await message.answer(
        "Выберите категорию товара:",
        reply_markup=get_cancel_keyboard()
    )

    # Send inline keyboard with categories
    @sync_to_async
    def get_categories_keyboard():
        return get_categories_inline_keyboard(staff_profile.location.id)

    categories_keyboard = await get_categories_keyboard()

    await message.answer(
        "📂 Категории:",
        reply_markup=categories_keyboard
    )


@router.callback_query(F.data.startswith("category:"))
async def select_category(callback: CallbackQuery, staff_profile: StaffProfile):
    """Handle category selection."""
    category_id = int(callback.data.split(":")[1])

    @sync_to_async
    def get_products_keyboard():
        return get_products_inline_keyboard(category_id, staff_profile.location.id)

    products_keyboard = await get_products_keyboard()

    await callback.message.edit_text(
        "📦 Выберите товар:",
        reply_markup=products_keyboard
    )

    await callback.answer()


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, staff_profile: StaffProfile):
    """Return to category selection."""
    @sync_to_async
    def get_categories_keyboard():
        return get_categories_inline_keyboard(staff_profile.location.id)

    categories_keyboard = await get_categories_keyboard()

    await callback.message.edit_text(
        "📂 Категории:",
        reply_markup=categories_keyboard
    )
    await callback.answer()


@router.callback_query(SaleStates.waiting_for_product, F.data.startswith("product:"))
async def select_product(callback: CallbackQuery, state: FSMContext):
    """Handle product selection."""
    product_id = int(callback.data.split(":")[1])

    try:
        @sync_to_async
        def get_product():
            return Product.objects.get(id=product_id)

        product = await get_product()

        await state.update_data(product_id=product_id)
        await state.set_state(SaleStates.waiting_for_quantity)

        await callback.message.answer(
            f"📦 Товар: {product.name}\n"
            f"💰 Цена: {product.price}₸\n"
            f"📊 Остаток: {product.stock_quantity} {product.unit}\n\n"
            f"Введите количество:",
            reply_markup=get_cancel_keyboard()
        )

        await callback.answer()

    except Product.DoesNotExist:
        await callback.answer("❌ Товар не найден", show_alert=True)


@router.message(SaleStates.waiting_for_quantity)
async def enter_quantity(message: Message, state: FSMContext):
    """Handle quantity input."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Продажа отменена.", reply_markup=get_main_menu_keyboard())
        return

    try:
        qty = Decimal(message.text.replace(',', '.'))

        if qty <= 0:
            await message.answer("❌ Количество должно быть больше нуля. Попробуйте снова:")
            return

        await state.update_data(qty=qty)
        await state.set_state(SaleStates.waiting_for_payment_method)

        # Get product to show total
        data = await state.get_data()

        @sync_to_async
        def get_product():
            return Product.objects.get(id=data['product_id'])

        product = await get_product()
        total = product.price * qty

        await message.answer(
            f"💰 Итого: {total}₸\n\n"
            f"Выберите способ оплаты:",
            reply_markup=get_payment_method_keyboard()
        )

    except (InvalidOperation, ValueError):
        await message.answer("❌ Неверный формат. Введите число (например: 1 или 2.5):")


@router.message(SaleStates.waiting_for_payment_method)
async def select_payment_method(message: Message, state: FSMContext):
    """Handle payment method selection."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Продажа отменена.", reply_markup=get_main_menu_keyboard())
        return

    payment_method = parse_payment_method(message.text)

    # Get data from state
    data = await state.get_data()
    shift_id = data['shift_id']
    product_id = data['product_id']
    qty = data['qty']

    try:
        @sync_to_async
        def create_sale():
            shift = Shift.objects.get(id=shift_id)
            product = Product.objects.get(id=product_id)

            # Create sale transaction
            transaction = TransactionService.create_sale(
                shift=shift,
                product=product,
                qty=qty,
                payment_method=payment_method
            )
            return transaction, product

        transaction, product = await create_sale()

        @sync_to_async
        def get_payment_method_display():
            return transaction.payments.first().get_method_display()

        @sync_to_async
        def get_current_stock():
            # Refresh product from DB to get updated stock
            return Product.objects.get(id=product_id).stock_quantity

        @sync_to_async
        def log_sale_action():
            shift = Shift.objects.get(id=shift_id)
            payment = transaction.payments.first()
            ShiftLogger.log_sale(
                shift=shift,
                product_name=product.name,
                qty=float(qty),
                amount=float(transaction.amount),
                payment_method=payment.get_method_display()
            )

        payment_display = await get_payment_method_display()
        current_stock = await get_current_stock()
        await log_sale_action()

        await message.answer(
            f"✅ Продажа оформлена!\n\n"
            f"📦 Товар: {product.name}\n"
            f"📊 Количество: {qty} {product.unit}\n"
            f"💰 Сумма: {transaction.amount}₸\n"
            f"💳 Оплата: {payment_display}\n"
            f"📈 Остаток на складе: {current_stock} {product.unit}",
            reply_markup=get_main_menu_keyboard()
        )

        logger.info(f"Sale created: {transaction.id}, new stock: {current_stock}")

    except ValidationError as e:
        await message.answer(f"❌ Ошибка: {e.message}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании продажи: {e}")
        logger.error(f"Error creating sale: {e}")

    await state.clear()


# ============================================================================
# REFUNDS
# ============================================================================

@router.message(F.text == "↩️ Возврат")
async def start_refund(message: Message, staff_profile: StaffProfile, state: FSMContext):
    """Start refund process."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    # Check if shift is open
    @sync_to_async
    def get_open_shift():
        return Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).first()

    open_shift = await get_open_shift()

    if not open_shift:
        await message.answer("❌ Смена не открыта. Откройте смену для возврата.")
        return

    await state.set_state(RefundStates.waiting_for_product)
    await state.update_data(shift_id=open_shift.id)

    await message.answer(
        "Выберите категорию товара для возврата:",
        reply_markup=get_cancel_keyboard()
    )

    # Send inline keyboard with categories
    @sync_to_async
    def get_categories_keyboard():
        return get_categories_inline_keyboard(staff_profile.location.id)

    categories_keyboard = await get_categories_keyboard()

    await message.answer(
        "📂 Категории:",
        reply_markup=categories_keyboard
    )


@router.callback_query(RefundStates.waiting_for_product, F.data.startswith("product:"))
async def select_refund_product(callback: CallbackQuery, state: FSMContext):
    """Handle product selection for refund."""
    product_id = int(callback.data.split(":")[1])

    try:
        @sync_to_async
        def get_product():
            return Product.objects.get(id=product_id)

        product = await get_product()

        await state.update_data(product_id=product_id)
        await state.set_state(RefundStates.waiting_for_quantity)

        await callback.message.answer(
            f"📦 Товар: {product.name}\n"
            f"💰 Цена: {product.price}₸\n\n"
            f"Введите количество для возврата:",
            reply_markup=get_cancel_keyboard()
        )

        await callback.answer()

    except Product.DoesNotExist:
        await callback.answer("❌ Товар не найден", show_alert=True)


@router.message(RefundStates.waiting_for_quantity)
async def enter_refund_quantity(message: Message, state: FSMContext):
    """Handle quantity input for refund."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Возврат отменен.", reply_markup=get_main_menu_keyboard())
        return

    try:
        qty = Decimal(message.text.replace(',', '.'))

        if qty <= 0:
            await message.answer("❌ Количество должно быть больше нуля. Попробуйте снова:")
            return

        await state.update_data(qty=qty)
        await state.set_state(RefundStates.waiting_for_payment_method)

        # Get product to show total
        data = await state.get_data()

        @sync_to_async
        def get_product():
            return Product.objects.get(id=data['product_id'])

        product = await get_product()
        total = product.price * qty

        await message.answer(
            f"💰 Сумма возврата: {total}₸\n\n"
            f"Выберите способ возврата:",
            reply_markup=get_payment_method_keyboard()
        )

    except (InvalidOperation, ValueError):
        await message.answer("❌ Неверный формат. Введите число (например: 1 или 2.5):")


@router.message(RefundStates.waiting_for_payment_method)
async def select_refund_payment_method(message: Message, state: FSMContext):
    """Handle payment method selection for refund."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Возврат отменен.", reply_markup=get_main_menu_keyboard())
        return

    payment_method = parse_payment_method(message.text)

    # Get data from state
    data = await state.get_data()
    shift_id = data['shift_id']
    product_id = data['product_id']
    qty = data['qty']

    try:
        @sync_to_async
        def create_refund():
            shift = Shift.objects.get(id=shift_id)
            product = Product.objects.get(id=product_id)

            # Create refund transaction
            transaction = TransactionService.create_refund(
                shift=shift,
                product=product,
                qty=qty,
                payment_method=payment_method
            )
            return transaction, product

        transaction, product = await create_refund()

        @sync_to_async
        def get_payment_method_display():
            return transaction.payments.first().get_method_display()

        @sync_to_async
        def get_current_stock():
            # Refresh product from DB to get updated stock
            return Product.objects.get(id=product_id).stock_quantity

        @sync_to_async
        def log_refund_action():
            shift = Shift.objects.get(id=shift_id)
            payment = transaction.payments.first()
            ShiftLogger.log_refund(
                shift=shift,
                product_name=product.name,
                qty=float(qty),
                amount=float(transaction.amount),
                payment_method=payment.get_method_display()
            )

        payment_display = await get_payment_method_display()
        current_stock = await get_current_stock()
        await log_refund_action()

        await message.answer(
            f"✅ Возврат оформлен!\n\n"
            f"📦 Товар: {product.name}\n"
            f"📊 Количество: {qty} {product.unit}\n"
            f"💰 Сумма: {transaction.amount}₸\n"
            f"💳 Возврат: {payment_display}\n"
            f"📈 Остаток на складе: {current_stock} {product.unit}",
            reply_markup=get_main_menu_keyboard()
        )

        logger.info(f"Refund created: {transaction.id}, new stock: {current_stock}")

    except ValidationError as e:
        await message.answer(f"❌ Ошибка: {e.message}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании возврата: {e}")
        logger.error(f"Error creating refund: {e}")

    await state.clear()


# ============================================================================
# REPORTS
# ============================================================================

@router.message(F.text == "📈 Отчеты")
async def show_reports_menu(message: Message, staff_profile: StaffProfile):
    """Show reports menu."""
    from .keyboards import get_reports_menu_keyboard
    await message.answer(
        "📊 Выберите тип отчета:",
        reply_markup=get_reports_menu_keyboard()
    )


@router.message(F.text == "📊 Общий отчет")
async def show_general_report(message: Message, staff_profile: StaffProfile):
    """Show general shift report."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    @sync_to_async
    def get_shift_and_summary():
        shift = Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).select_related('staff__user', 'location').first()

        if shift:
            summary = ReportService.get_shift_summary(shift)
            ShiftLogger.log_report_view(shift, "Общий отчет")
            shift_data = {
                'staff_name': shift.staff.full_name,
                'location_name': shift.location.name,
                'started_at': shift.started_at,
            }
            return shift_data, summary
        return None, None

    shift_data, summary = await get_shift_and_summary()

    if not shift_data:
        await message.answer("❌ Нет открытой смены.")
        return

    # Build product summary for sales
    product_lines = []
    for product_name, data in summary['product_summary'].items():
        product_lines.append(f"  • {product_name}: {data['qty']} шт - {data['amount']}₸")

    product_summary = "\n".join(product_lines) if product_lines else "  Нет продаж"

    # Build product summary for refunds
    refund_lines = []
    for product_name, data in summary['refund_summary'].items():
        refund_lines.append(f"  • {product_name}: {data['qty']} шт - {data['amount']}₸")

    refund_summary = "\n".join(refund_lines) if refund_lines else "  Нет возвратов"

    report_text = (
        f"📊 ОБЩИЙ ОТЧЕТ ПО СМЕНЕ\n\n"
        f"👤 Сотрудник: {shift_data['staff_name']}\n"
        f"📍 Локация: {shift_data['location_name']}\n"
        f"🕐 Начало: {shift_data['started_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"💰 Продажи: {summary['sales_total']}₸ ({summary['sales_count']} шт)\n"
        f"↩️ Возвраты: {summary['refunds_total']}₸ ({summary['refunds_count']} шт)\n"
        f"💵 Наличные: {summary['total_cash']}₸\n"
        f"💳 Карта: {summary['total_card']}₸\n"
        f"📱 Перевод: {summary['total_transfer']}₸\n\n"
        f"📦 Продажи по товарам:\n{product_summary}\n\n"
        f"↩️ Возвраты по товарам:\n{refund_summary}"
    )

    await message.answer(report_text)


@router.message(F.text == "💰 Финансовый отчет")
async def show_financial_report(message: Message, staff_profile: StaffProfile):
    """Show financial report."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    @sync_to_async
    def get_financial_data():
        shift = Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).select_related('staff__user', 'location').first()

        if shift:
            financial = ReportService.get_financial_report(shift)
            shift_data = {
                'staff_name': shift.staff.full_name,
                'location_name': shift.location.name,
                'started_at': shift.started_at,
            }
            return shift_data, financial
        return None, None

    shift_data, financial = await get_financial_data()

    if not shift_data:
        await message.answer("❌ Нет открытой смены.")
        return

    report_text = (
        f"💰 ФИНАНСОВЫЙ ОТЧЕТ\n\n"
        f"👤 Сотрудник: {shift_data['staff_name']}\n"
        f"📍 Локация: {shift_data['location_name']}\n"
        f"🕐 Начало: {shift_data['started_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 КАССА (ИТОГО): {financial['total_in_register']}₸\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Разбивка по методам оплаты:\n"
        f"  💵 Наличные: {financial['net_cash']}₸\n"
        f"  💳 Карта: {financial['net_card']}₸\n"
        f"  📱 Перевод: {financial['net_transfer']}₸\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 Детали:\n"
        f"  ✅ Продажи: +{financial['sales_total']}₸\n"
        f"  ❌ Возвраты: -{financial['refunds_total']}₸\n"
        f"  💰 Чистая прибыль: {financial['net_total']}₸\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await message.answer(report_text)


@router.message(F.text == "📦 Отчет продаж")
async def show_sales_report(message: Message, staff_profile: StaffProfile):
    """Show detailed sales report."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    @sync_to_async
    def get_sales_data():
        shift = Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).select_related('staff__user', 'location').first()

        if shift:
            sales = ReportService.get_sales_details(shift)
            shift_data = {
                'staff_name': shift.staff.full_name,
                'started_at': shift.started_at,
            }
            return shift_data, sales
        return None, None

    shift_data, sales = await get_sales_data()

    if not shift_data:
        await message.answer("❌ Нет открытой смены.")
        return

    if not sales:
        await message.answer("📦 Продаж пока не было.")
        return

    # Build sales list
    sales_lines = []
    for idx, sale in enumerate(sales, 1):
        time_str = sale['time'].strftime('%H:%M')
        payment_icon = {
            'CASH': '💵',
            'CARD': '💳',
            'TRANSFER': '📱'
        }.get(sale['payment_method_code'], '💰')

        sales_lines.append(
            f"{idx}. [{time_str}] {sale['product']}\n"
            f"   {sale['qty']} шт × {sale['amount'] / sale['qty']}₸ = {sale['amount']}₸\n"
            f"   {payment_icon} {sale['payment_method']}"
        )

    sales_text = "\n\n".join(sales_lines)
    total = sum(s['amount'] for s in sales)

    report_text = (
        f"📦 ОТЧЕТ ПРОДАЖ\n\n"
        f"👤 Сотрудник: {shift_data['staff_name']}\n"
        f"🕐 Начало смены: {shift_data['started_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{sales_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 ИТОГО: {total}₸ ({len(sales)} транзакций)"
    )

    await message.answer(report_text)


@router.message(F.text == "↩️ Отчет возвратов")
async def show_refunds_report(message: Message, staff_profile: StaffProfile):
    """Show detailed refunds report."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    @sync_to_async
    def get_refunds_data():
        shift = Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).select_related('staff__user', 'location').first()

        if shift:
            refunds = ReportService.get_refunds_details(shift)
            shift_data = {
                'staff_name': shift.staff.full_name,
                'started_at': shift.started_at,
            }
            return shift_data, refunds
        return None, None

    shift_data, refunds = await get_refunds_data()

    if not shift_data:
        await message.answer("❌ Нет открытой смены.")
        return

    if not refunds:
        await message.answer("↩️ Возвратов пока не было.")
        return

    # Build refunds list
    refund_lines = []
    for idx, refund in enumerate(refunds, 1):
        time_str = refund['time'].strftime('%H:%M')
        payment_icon = {
            'CASH': '💵',
            'CARD': '💳',
            'TRANSFER': '📱'
        }.get(refund['payment_method_code'], '💰')

        refund_lines.append(
            f"{idx}. [{time_str}] {refund['product']}\n"
            f"   {refund['qty']} шт × {refund['amount'] / refund['qty']}₸ = {refund['amount']}₸\n"
            f"   {payment_icon} {refund['payment_method']}"
        )

    refunds_text = "\n\n".join(refund_lines)
    total = sum(r['amount'] for r in refunds)

    report_text = (
        f"↩️ ОТЧЕТ ВОЗВРАТОВ\n\n"
        f"👤 Сотрудник: {shift_data['staff_name']}\n"
        f"🕐 Начало смены: {shift_data['started_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{refunds_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 ИТОГО: {total}₸ ({len(refunds)} транзакций)"
    )

    await message.answer(report_text)


@router.message(F.text == "📋 Инвентаризация")
async def show_inventory_report(message: Message, staff_profile: StaffProfile):
    """Show inventory report."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    @sync_to_async
    def get_inventory_data():
        inventory = ReportService.get_inventory_report(staff_profile.location)
        return inventory

    inventory = await get_inventory_data()

    if not inventory:
        await message.answer("📋 Нет товаров в инвентаре.")
        return

    # Group by category
    categories = {}
    for item in inventory:
        cat = item['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    # Build inventory text
    inventory_lines = []
    total_items = 0

    for category, items in categories.items():
        inventory_lines.append(f"\n📁 {category}:")
        for item in items:
            stock_status = "✅" if item['stock'] > 0 else "❌"
            inventory_lines.append(
                f"  {stock_status} {item['product']}: {item['stock']} {item['unit']} "
                f"({item['price']}₸/{item['unit']})"
            )
            total_items += 1

    inventory_text = "\n".join(inventory_lines)

    report_text = (
        f"📋 ИНВЕНТАРИЗАЦИЯ\n"
        f"📍 Локация: {staff_profile.location.name}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{inventory_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Всего товаров: {total_items}"
    )

    await message.answer(report_text)


# ============================================================================
# HELP
# ============================================================================

@router.message(F.text == "❓ Помощь")
async def show_help(message: Message):
    """Show help message."""
    help_text = (
        "📖 Помощь по боту\n\n"
        "📦 Продажа - оформить продажу товара\n"
        "↩️ Возврат - оформить возврат товара\n"
        "📊 Смена - управление сменой\n"
        "📈 Отчет - отчет по текущей смене\n\n"
        "По вопросам обращайтесь к администратору."
    )
    await message.answer(help_text)

