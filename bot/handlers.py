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
from apps.inventory.models import Product, StorageStock, DisplayStock
from apps.pos.models import Shift
from apps.pos.services import ShiftService, TransactionService, ReportService
from apps.inventory.services import InventoryService
from .states import SaleStates, RefundStates, ShiftStates, PurchaseStates, TransferStates
from .keyboards import (
    get_main_menu_keyboard,
    get_manager_menu_keyboard,
    get_shift_menu_keyboard,
    get_payment_method_keyboard,
    get_cancel_keyboard,
    get_confirmation_keyboard,
    get_categories_inline_keyboard,
    get_products_inline_keyboard,
    get_reports_menu_keyboard,
    get_cashier_reports_menu_keyboard,
    parse_payment_method
)
from .shift_logger import ShiftLogger

logger = logging.getLogger('bot')
router = Router()


def _menu_keyboard(staff_profile):
    """Return the role-appropriate main keyboard."""
    if staff_profile and staff_profile.role in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        return get_manager_menu_keyboard()
    return get_main_menu_keyboard()


# ============================================================================
# START & MAIN MENU
# ============================================================================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, staff_profile: StaffProfile = None):
    """Handle /start command. Always clears any active FSM state."""
    await state.clear()
    if not staff_profile:
        await message.answer(
            "👋 Добро пожаловать в Inventory POS Bot!\n\n"
            "❌ У вас нет доступа к боту.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return

    is_manager = staff_profile.role in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]

    if is_manager:
        features = (
            f"📦 Оформление продаж и возвратов\n"
            f"🛒 Закупка товара (склад)\n"
            f"🔄 Перемещение товара (склад → витрина)\n"
            f"📊 Управление сменами\n"
            f"📈 Просмотр отчетов и статистики\n"
            f"📋 Контроль остатков (склад + витрина)"
        )
        keyboard = get_manager_menu_keyboard()
    else:
        features = (
            f"📦 Оформление продаж и возвратов\n"
            f"📊 Просмотр статуса смены\n"
            f"🏪 Остатки на витрине"
        )
        keyboard = get_main_menu_keyboard()

    welcome_text = (
        f"👋 Привет, {staff_profile.full_name}!\n\n"
        f"📍 Локация: {staff_profile.location.name if staff_profile.location else 'Не назначена'}\n"
        f"👤 Роль: {staff_profile.get_role_display()}\n\n"
        f"📋 <b>Доступные функции:</b>\n"
        f"{features}\n\n"
        f"Выберите действие:"
    )

    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(F.text == "◀️ Назад")
async def back_to_main(message: Message, state: FSMContext, staff_profile: StaffProfile = None):
    """Return to main menu."""
    await state.clear()
    if staff_profile and staff_profile.role in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        keyboard = get_manager_menu_keyboard()
    else:
        keyboard = get_main_menu_keyboard()
    await message.answer("Главное меню:", reply_markup=keyboard)


@router.message(F.text == "❌ Отмена")
async def cancel_action(message: Message, state: FSMContext, staff_profile: StaffProfile = None):
    """Cancel current action and return to main menu."""
    await state.clear()
    if staff_profile and staff_profile.role in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        keyboard = get_manager_menu_keyboard()
    else:
        keyboard = get_main_menu_keyboard()
    await message.answer("Действие отменено.", reply_markup=keyboard)


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

    @sync_to_async
    def can_manage():
        return staff_profile.can_manage_shifts()

    if not await can_manage():
        await message.answer("❌ У вас нет прав на открытие смены.")
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

        if staff_profile.role in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
            kb = get_manager_menu_keyboard()
        else:
            kb = get_main_menu_keyboard()

        await message.answer(
            f"✅ <b>Смена успешно открыта!</b>\n\n"
            f"📍 Локация: {shift.location.name}\n"
            f"👤 Сотрудник: {staff_profile.full_name}\n"
            f"🕐 Время открытия: {shift.started_at.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=kb,
            parse_mode="HTML"
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
async def close_shift_confirmed(message: Message, state: FSMContext, staff_profile: StaffProfile = None):
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

        kb = get_manager_menu_keyboard()  # only managers/admins can close shifts

        await message.answer(
            f"✅ Смена закрыта!\n\n"
            f"💰 Итого продаж: {shift.total_sales}₸\n"
            f"💵 Наличные: {shift.total_cash}₸\n"
            f"💳 Карта: {shift.total_card}₸\n"
            f"📱 Перевод: {shift.total_transfer}₸",
            reply_markup=kb
        )

        logger.info(f"Shift {shift.id} closed")

    except Exception as e:
        await message.answer(f"❌ Ошибка при закрытии смены: {e}")
        logger.error(f"Error closing shift: {e}")

    await state.clear()


@router.message(ShiftStates.waiting_for_close_confirmation, F.text == "❌ Нет")
async def close_shift_cancelled(message: Message, state: FSMContext, staff_profile: StaffProfile = None):
    """Cancel shift closing."""
    await state.clear()
    await message.answer(
        "Закрытие смены отменено.",
        reply_markup=get_manager_menu_keyboard()  # only managers/admins can close shifts
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
        await message.answer(
            "❌ Смена не открыта.\n\n"
            "💡 Для оформления продажи сначала откройте смену:\n"
            "📊 Смена → 🟢 Открыть смену"
        )
        return

    await state.set_state(SaleStates.waiting_for_product)
    await state.update_data(shift_id=open_shift.id)

    # Send instruction message (will be deleted later)
    instruction_msg = await message.answer(
        "📦 <b>Оформление продажи</b>\n\n"
        "Шаг 1: Выберите категорию товара из списка ниже\n\n"
        "💡 Для отмены нажмите <b>❌ Отмена</b>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

    # Send inline keyboard with categories
    @sync_to_async
    def get_categories_keyboard():
        return get_categories_inline_keyboard(staff_profile.location.id)

    categories_keyboard = await get_categories_keyboard()

    categories_msg = await message.answer(
        "📂 Категории:",
        reply_markup=categories_keyboard
    )

    # Store message IDs for later cleanup
    await state.update_data(
        instruction_msg_id=instruction_msg.message_id,
        categories_msg_id=categories_msg.message_id
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
async def sale_product_selected(callback: CallbackQuery, state: FSMContext, staff_profile: StaffProfile):
    """Handle product selection for sale."""
    product_id = int(callback.data.split(":")[1])

    @sync_to_async
    def get_product_and_display_stock():
        product = Product.objects.get(id=product_id, location=staff_profile.location, is_active=True)
        display = DisplayStock.objects.filter(product=product, location=staff_profile.location).first()
        return product, display

    try:
        product, display = await get_product_and_display_stock()
    except Product.DoesNotExist:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    if display is None or display.quantity <= 0:
        await callback.answer("❌ Товар отсутствует на витрине", show_alert=True)
        return

    await state.update_data(product_id=product_id)
    await state.set_state(SaleStates.waiting_for_quantity)

    await callback.message.edit_text(
        f"📦 Товар: {product.name}\n"
        f"💰 Цена: {product.price}₸/{product.unit}\n"
        f"🏪 На витрине: {display.quantity} {product.unit}\n\n"
        f"Введите количество для продажи:"
    )
    await callback.answer()


@router.message(SaleStates.waiting_for_quantity)
async def sale_quantity_entered(message: Message, state: FSMContext, staff_profile: StaffProfile):
    """Handle quantity input for sale."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Продажа отменена", reply_markup=_menu_keyboard(staff_profile))
        return

    try:
        quantity = Decimal(message.text.replace(',', '.'))
        if quantity <= 0:
            raise ValueError
    except (ValueError, InvalidOperation):
        await message.answer("❌ Неверное количество. Введите положительное число:")
        return

    data = await state.get_data()
    product_id = data['product_id']

    @sync_to_async
    def validate_stock():
        product = Product.objects.get(id=product_id)
        display = DisplayStock.objects.filter(product=product, location=staff_profile.location).first()
        return product, display

    product, display = await validate_stock()
    if display is None:
        await message.answer(
            "❌ Товар отсутствует на витрине. Переместите товар со склада (🔄 Перемещение).",
            reply_markup=_menu_keyboard(staff_profile)
        )
        await state.clear()
        return

    # Check if enough stock on DISPLAY
    if quantity > display.quantity:
        await message.answer(
            f"❌ Недостаточно товара на витрине!\n\n"
            f"🏪 Доступно: {display.quantity} {product.unit}\n"
            f"❌ Запрошено: {quantity} {product.unit}\n\n"
            f"💡 Переместите товар со склада (🔄 Перемещение)\n\n"
            f"Введите корректное количество:"
        )
        return

    total_amount = quantity * product.price

    await state.update_data(quantity=quantity, total_amount=total_amount)
    await state.set_state(SaleStates.waiting_for_payment_method)

    confirmation_text = (
        f"✅ ПОДТВЕРЖДЕНИЕ ПРОДАЖИ\n\n"
        f"📦 Товар: {product.name}\n"
        f"📊 Количество: {quantity} {product.unit}\n"
        f"💰 Цена: {product.price}₸/{product.unit}\n"
        f"💵 Итого: {total_amount}₸\n\n"
        f"Выберите способ оплаты:"
    )

    await message.answer(
        confirmation_text,
        reply_markup=get_payment_method_keyboard()
    )


@router.message(SaleStates.waiting_for_payment_method)
async def select_payment_method(message: Message, state: FSMContext, staff_profile: StaffProfile = None):
    """Handle payment method selection."""
    if message.text == "❌ Отмена":
        await state.clear()
        # Delete user's message
        try:
            await message.delete()
        except:
            pass
        await message.answer("❌ Продажа отменена.", reply_markup=_menu_keyboard(staff_profile))
        return

    payment_method = parse_payment_method(message.text)

    # Get data from state
    data = await state.get_data()
    shift_id = data['shift_id']
    product_id = data['product_id']
    qty = data['quantity']

    # Verify the shift is still open before processing payment
    @sync_to_async
    def check_shift_open():
        return Shift.objects.filter(id=shift_id, is_closed=False).exists()

    if not await check_shift_open():
        await state.clear()
        await message.answer(
            "❌ Смена была закрыта. Продажа отменена.",
            reply_markup=_menu_keyboard(staff_profile)
        )
        return

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

        # Delete user's payment method selection message
        try:
            await message.delete()
        except:
            pass

        # Delete instruction message
        if 'instruction_msg_id' in data:
            try:
                await message.bot.delete_message(message.chat.id, data['instruction_msg_id'])
            except:
                pass

        # Send only the final success message
        await message.answer(
            f"✅ <b>Продажа оформлена!</b>\n\n"
            f"📦 Товар: {product.name}\n"
            f"📊 Количество: {qty} {product.unit}\n"
            f"💰 Сумма: {transaction.amount}₸\n"
            f"💳 Оплата: {payment_display}\n"
            f"📊 Остаток (склад+витрина): {current_stock} {product.unit}",
            reply_markup=_menu_keyboard(staff_profile),
            parse_mode="HTML"
        )

        logger.info(f"Sale created: {transaction.id}, new stock: {current_stock}")

    except ValidationError as e:
        await message.answer(f"❌ Ошибка: {e.message}", reply_markup=_menu_keyboard(staff_profile))
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании продажи: {e}", reply_markup=_menu_keyboard(staff_profile))
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
        await message.answer(
            "❌ Смена не открыта.\n\n"
            "💡 Для оформления возврата сначала откройте смену:\n"
            "📊 Смена → 🟢 Открыть смену"
        )
        return

    await state.set_state(RefundStates.waiting_for_product)
    await state.update_data(shift_id=open_shift.id)

    instruction_msg = await message.answer(
        "↩️ <b>Оформление возврата</b>\n\n"
        "Шаг 1: Выберите категорию товара для возврата\n\n"
        "💡 Для отмены нажмите <b>❌ Отмена</b>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

    # Send inline keyboard with categories
    @sync_to_async
    def get_categories_keyboard():
        return get_categories_inline_keyboard(staff_profile.location.id)

    categories_keyboard = await get_categories_keyboard()

    categories_msg = await message.answer(
        "📂 Категории:",
        reply_markup=categories_keyboard
    )

    # Store message IDs for cleanup
    await state.update_data(
        refund_instruction_msg_id=instruction_msg.message_id,
        refund_categories_msg_id=categories_msg.message_id
    )


@router.callback_query(RefundStates.waiting_for_product, F.data.startswith("product:"))
async def refund_product_selected(callback: CallbackQuery, state: FSMContext, staff_profile: StaffProfile):
    """Handle product selection for refund."""
    product_id = int(callback.data.split(":")[1])

    @sync_to_async
    def get_product():
        return Product.objects.get(id=product_id, location=staff_profile.location, is_active=True)

    try:
        product = await get_product()
    except Product.DoesNotExist:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    await state.update_data(product_id=product_id)
    await state.set_state(RefundStates.waiting_for_quantity)

    await callback.message.edit_text(
        f"↩️ Возврат: {product.name}\n"
        f"💰 Цена: {product.price}₸/{product.unit}\n\n"
        f"Введите количество для возврата:"
    )
    await callback.answer()


@router.message(RefundStates.waiting_for_quantity)
async def refund_quantity_entered(message: Message, state: FSMContext, staff_profile: StaffProfile):
    """Handle quantity input for refund."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Возврат отменен", reply_markup=_menu_keyboard(staff_profile))
        return

    try:
        quantity = Decimal(message.text.replace(',', '.'))
        if quantity <= 0:
            raise ValueError
    except (ValueError, InvalidOperation):
        await message.answer("❌ Неверное количество. Введите положительное число:")
        return

    data = await state.get_data()
    product_id = data['product_id']

    @sync_to_async
    def get_product():
        return Product.objects.get(id=product_id)

    product = await get_product()
    total_amount = quantity * product.price

    await state.update_data(quantity=quantity, total_amount=total_amount)
    await state.set_state(RefundStates.waiting_for_payment_method)

    confirmation_text = (
        f"✅ ПОДТВЕРЖДЕНИЕ ВОЗВРАТА\n\n"
        f"📦 Товар: {product.name}\n"
        f"� Количество: {quantity} {product.unit}\n"
        f"� Цена: {product.price}₸/{product.unit}\n"
        f"� Сумма возврата: {total_amount}₸\n\n"
        f"⚠️ Товар будет возвращен на витрину\n\n"
        f"Выберите способ возврата:"
    )

    await message.answer(
        confirmation_text,
        reply_markup=get_payment_method_keyboard()
    )


@router.message(RefundStates.waiting_for_payment_method)
async def select_refund_payment_method(message: Message, state: FSMContext, staff_profile: StaffProfile = None):
    """Handle payment method selection for refund."""
    if message.text == "❌ Отмена":
        await state.clear()
        # Delete user's message
        try:
            await message.delete()
        except:
            pass
        await message.answer("❌ Возврат отменен.", reply_markup=_menu_keyboard(staff_profile))
        return

    payment_method = parse_payment_method(message.text)

    # Get data from state
    data = await state.get_data()
    shift_id = data['shift_id']
    product_id = data['product_id']
    qty = data['quantity']

    # Verify the shift is still open before processing refund
    @sync_to_async
    def check_shift_open_refund():
        return Shift.objects.filter(id=shift_id, is_closed=False).exists()

    if not await check_shift_open_refund():
        await state.clear()
        await message.answer(
            "❌ Смена была закрыта. Возврат отменен.",
            reply_markup=_menu_keyboard(staff_profile)
        )
        return

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

        # Delete user's payment method selection message
        try:
            await message.delete()
        except:
            pass

        # Delete instruction message
        if 'refund_instruction_msg_id' in data:
            try:
                await message.bot.delete_message(message.chat.id, data['refund_instruction_msg_id'])
            except:
                pass

        # Send only the final success message
        await message.answer(
            f"✅ <b>Возврат оформлен!</b>\n\n"
            f"📦 Товар: {product.name}\n"
            f"📊 Количество: {qty} {product.unit}\n"
            f"💰 Сумма: {abs(transaction.amount)}₸\n"
            f"💳 Возврат: {payment_display}\n"
            f"📊 Остаток (склад+витрина): {current_stock} {product.unit}",
            reply_markup=_menu_keyboard(staff_profile),
            parse_mode="HTML"
        )

        logger.info(f"Refund created: {transaction.id}, new stock: {current_stock}")

    except ValidationError as e:
        await message.answer(f"❌ Ошибка: {e.message}", reply_markup=_menu_keyboard(staff_profile))
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании возврата: {e}", reply_markup=_menu_keyboard(staff_profile))
        logger.error(f"Error creating refund: {e}")

    await state.clear()


# ============================================================================
# REPORTS
# ============================================================================

@router.message(F.text == "🏪 Витрина")
async def show_vitrina(message: Message, staff_profile: StaffProfile):
    """Show current display stock levels and open shift status for cashiers."""
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    @sync_to_async
    def get_vitrina_data():
        shift = Shift.objects.filter(
            location=staff_profile.location,
            is_closed=False
        ).select_related('staff__user').first()

        display_stocks = list(
            DisplayStock.objects.filter(
                location=staff_profile.location,
            ).select_related('product').order_by('product__name')
        )
        return shift, display_stocks

    shift, display_stocks = await get_vitrina_data()

    if shift:
        shift_info = (
            f"🟢 Смена открыта\n"
            f"👤 {shift.staff.full_name} с {shift.started_at.strftime('%H:%M')}"
        )
    else:
        shift_info = "🔴 Смена не открыта"

    if display_stocks:
        stock_lines = "\n".join(
            f"  • {ds.product.name}: {ds.quantity} {ds.product.unit}"
            for ds in display_stocks
        )
    else:
        stock_lines = "  Витрина пуста"

    await message.answer(
        f"🏪 <b>Витрина</b>\n\n"
        f"{shift_info}\n\n"
        f"📦 <b>Остатки на витрине:</b>\n{stock_lines}",
        parse_mode="HTML"
    )


@router.message(F.text == "📈 Отчеты")
async def show_reports_menu(message: Message, staff_profile: StaffProfile):
    """Show reports menu. Cashiers see a limited subset."""
    if staff_profile.role in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        kb = get_reports_menu_keyboard()
    else:
        kb = get_cashier_reports_menu_keyboard()
    await message.answer("📊 Выберите тип отчета:", reply_markup=kb)


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
    """Show financial report (ADMIN/MANAGER only)."""
    if staff_profile.role not in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        await message.answer("❌ У вас нет доступа к финансовому отчету.")
        return
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
    """Show detailed refunds report (ADMIN/MANAGER only)."""
    if staff_profile.role not in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        await message.answer("❌ У вас нет доступа к отчету возвратов.")
        return
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
    """Show inventory report (ADMIN/MANAGER only)."""
    if staff_profile.role not in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        await message.answer("❌ У вас нет доступа к инвентаризации.")
        return
    if not staff_profile.location:
        await message.answer("❌ У вас не назначена локация.")
        return

    @sync_to_async
    def get_inventory_data():
        products = Product.objects.filter(
            location=staff_profile.location,
            is_active=True
        ).select_related('category', 'storage_stock', 'display_stock').order_by('category__name', 'name')
        
        inventory = []
        for product in products:
            storage = getattr(product, 'storage_stock', None)
            display = getattr(product, 'display_stock', None)
            
            storage_qty = storage.quantity if storage else Decimal('0.00')
            display_qty = display.quantity if display else Decimal('0.00')
            total_qty = storage_qty + display_qty
            
            inventory.append({
                'category': product.category.name,
                'product': product.name,
                'storage': storage_qty,
                'display': display_qty,
                'total': total_qty,
                'unit': product.unit,
                'price': product.price
            })
        
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
            stock_status = "✅" if item['total'] > 0 else "❌"
            inventory_lines.append(
                f"  {stock_status} {item['product']}:\n"
                f"     📦 Склад: {item['storage']} {item['unit']}\n"
                f"     🏪 Витрина: {item['display']} {item['unit']}\n"
                f"     📊 Всего: {item['total']} {item['unit']} ({item['price']}₸/{item['unit']})"
            )
            total_items += 1

    header = (
        f"📋 ИНВЕНТАРИЗАЦИЯ\n"
        f"📍 Локация: {staff_profile.location.name}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    footer = f"━━━━━━━━━━━━━━━━━━━━\n📊 Всего товаров: {total_items}"

    # Split into chunks to stay within Telegram's 4096-char limit
    MAX_LEN = 3800
    chunks = []
    current = header
    for line in inventory_lines:
        candidate = current + line + "\n"
        if len(candidate) > MAX_LEN:
            chunks.append(current)
            current = line + "\n"
        else:
            current = candidate
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await message.answer(chunk + "\n" + footer)
        else:
            await message.answer(chunk)


# ============================================================================
# HELP
# ============================================================================

@router.message(F.text == "❓ Помощь")
async def show_help(message: Message, staff_profile: StaffProfile = None):
    """Show role-appropriate help message."""
    is_manager = staff_profile and staff_profile.role in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]

    help_text = (
        "📖 <b>ИНСТРУКЦИЯ ПО РАБОТЕ С БОТОМ</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>УПРАВЛЕНИЕ СМЕНОЙ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🟢 <b>Открыть смену:</b>\n"
        "1. Нажмите кнопку <b>📊 Смена</b>\n"
        "2. Нажмите <b>🟢 Открыть смену</b>\n"
        "3. Смена открыта! Теперь можно оформлять продажи\n\n"

        "🔴 <b>Закрыть смену:</b>\n"
        "1. Нажмите <b>📊 Смена</b>\n"
        "2. Нажмите <b>🔴 Закрыть смену</b>\n"
        "3. Подтвердите закрытие\n"
        "4. Получите полный отчет по смене\n\n"

        "⚠️ <b>Важно:</b> Продажи можно оформлять только при открытой смене!\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>ОФОРМЛЕНИЕ ПРОДАЖИ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "1. Нажмите кнопку <b>📦 Продажа</b>\n"
        "2. Выберите категорию товара из списка\n"
        "3. Выберите товар (показаны цена и остаток на витрине)\n"
        "4. Введите количество (например: 2 или 1.5)\n"
        "5. Проверьте сумму и подтвердите\n"
        "6. Выберите способ оплаты:\n"
        "   • 💵 <b>Наличные</b> - оплата наличными\n"
        "   • 💳 <b>Карта</b> - оплата картой\n"
        "   • 🔄 <b>Перевод</b> - банковский перевод\n"
        "7. Готово! Продажа оформлена ✅\n\n"

        "💡 <b>Подсказки:</b>\n"
        "• Остаток товара на витрине показан в скобках\n"
        "• Нельзя продать больше, чем есть на витрине\n"
        "• Можно отменить в любой момент кнопкой <b>❌ Отмена</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "↩️ <b>ОФОРМЛЕНИЕ ВОЗВРАТА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "1. Нажмите кнопку <b>↩️ Возврат</b>\n"
        "2. Выберите категорию товара\n"
        "3. Выберите товар для возврата\n"
        "4. Введите количество для возврата\n"
        "5. Проверьте сумму возврата\n"
        "6. Выберите способ возврата (как при продаже)\n"
        "7. Готово! Возврат оформлен ✅\n\n"

        "⚠️ <b>Важно:</b> Возврат добавляет товар обратно на витрину!\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏪 <b>ВИТРИНА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "Нажмите <b>🏪 Витрина</b> чтобы увидеть:\n"
        "• Статус текущей смены (открыта/закрыта)\n"
        "• Остатки всех товаров на витрине\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📈 <b>ОТЧЕТЫ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "Нажмите <b>📈 Отчеты</b> и выберите нужный отчет:\n\n"

        "📊 <b>Общий отчет</b>\n"
        "→ Итоги смены: продажи, возвраты, оплаты\n\n"

        "📦 <b>Отчет продаж</b>\n"
        "→ Список всех продаж с временем и суммами\n\n"
    ) + (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🛒 <b>ЗАКУПКА ТОВАРА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "1. Нажмите кнопку <b>🛒 Закупка</b>\n"
        "2. Выберите категорию и товар\n"
        "3. Введите количество и цену закупки\n"
        "4. Введите поставщика (или '-' пропустить)\n"
        "5. Товар добавлен на склад ✅\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 <b>ПЕРЕМЕЩЕНИЕ ТОВАРА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "1. Нажмите кнопку <b>🔄 Перемещение</b>\n"
        "2. Выберите категорию и товар\n"
        "3. Введите количество для перемещения\n"
        "4. Товар перемещен на витрину ✅\n\n"

        "💡 СКЛАД → ВИТРИНА → Продажа\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📈 <b>ПОЛНЫЕ ОТЧЕТЫ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "💰 <b>Финансовый отчет</b> — сводка по способам оплаты\n"
        "↩️ <b>Отчет возвратов</b> — все возвраты с деталями\n"
        "📋 <b>Инвентаризация</b> — склад + витрина по каждому товару\n\n"
        if is_manager else ""
    ) + (

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "❓ <b>ЧАСТЫЕ ВОПРОСЫ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "❔ <b>В чем разница между складом и витриной?</b>\n"
        "→ СКЛАД - запас товара (закупки)\n"
        "→ ВИТРИНА - товар для продажи\n"
        "→ Продажи идут только с витрины!\n\n"

        "❔ <b>Как пополнить товар для продажи?</b>\n"
        "→ 1. Закупка (🛒) - товар на склад\n"
        "→ 2. Перемещение (🔄) - склад → витрина\n"
        "→ 3. Теперь можно продавать!\n\n"

        "❔ <b>Можно ли продавать без открытой смены?</b>\n"
        "→ Нет, сначала нужно открыть смену\n\n"

        "❔ <b>Куда возвращается товар при возврате?</b>\n"
        "→ На витрину (готов к повторной продаже)\n\n"

        "❔ <b>Где хранятся все данные?</b>\n"
        "→ Все транзакции сохраняются в базе данных\n"
        "→ Также создаются лог-файлы для каждой смены\n\n"

        "❔ <b>Что делать при ошибке?</b>\n"
        "→ Попробуйте отменить действие и повторить\n"
        "→ Если проблема повторяется - обратитесь к администратору\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📞 <b>ПОДДЕРЖКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "По всем вопросам обращайтесь к администратору системы.\n\n"

        "💡 <b>Совет:</b> Сохраните эту инструкцию, чтобы всегда иметь под рукой!"
    )
    await message.answer(help_text, parse_mode="HTML")


# ============================================================================
# PURCHASE (Закупка: supplier → storage)
# ============================================================================

@router.message(F.text == "🛒 Закупка")
async def start_purchase(message: Message, state: FSMContext, staff_profile: StaffProfile):
    """Start purchase process."""
    if staff_profile.role not in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        await message.answer("❌ У вас нет прав для закупки товара.")
        return

    @sync_to_async
    def get_categories_keyboard():
        return get_categories_inline_keyboard(staff_profile.location.id)

    categories_keyboard = await get_categories_keyboard()

    instruction_msg = await message.answer(
        "🛒 ЗАКУПКА ТОВАРА\n\n"
        "Выберите категорию товара для закупки:",
        reply_markup=get_cancel_keyboard()
    )

    categories_msg = await message.answer(
        "📁 Категории:",
        reply_markup=categories_keyboard
    )

    await state.set_state(PurchaseStates.waiting_for_product)
    await state.update_data(
        instruction_msg_id=instruction_msg.message_id,
        categories_msg_id=categories_msg.message_id
    )


@router.callback_query(PurchaseStates.waiting_for_product, F.data.startswith("product:"))
async def purchase_product_selected(callback: CallbackQuery, state: FSMContext, staff_profile: StaffProfile):
    """Handle product selection for purchase."""
    product_id = int(callback.data.split(":")[1])

    @sync_to_async
    def get_product():
        return Product.objects.get(id=product_id, location=staff_profile.location)

    try:
        product = await get_product()
    except Product.DoesNotExist:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    await state.update_data(product_id=product_id)
    await state.set_state(PurchaseStates.waiting_for_quantity)

    await callback.message.edit_text(
        f"🛒 Закупка: {product.name}\n\n"
        f"Введите количество для закупки ({product.unit}):"
    )
    await callback.answer()


@router.message(PurchaseStates.waiting_for_quantity)
async def purchase_quantity_entered(message: Message, state: FSMContext, staff_profile: StaffProfile = None):
    """Handle quantity input for purchase."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Закупка отменена", reply_markup=_menu_keyboard(staff_profile))
        return

    try:
        quantity = Decimal(message.text.replace(',', '.'))
        if quantity <= 0:
            raise ValueError
    except (ValueError, InvalidOperation):
        await message.answer("❌ Неверное количество. Введите положительное число:")
        return

    await state.update_data(quantity=quantity)
    await state.set_state(PurchaseStates.waiting_for_price)

    await message.answer("💰 Введите цену закупки за единицу (₸):")


@router.message(PurchaseStates.waiting_for_price)
async def purchase_price_entered(message: Message, state: FSMContext):
    """Handle price input for purchase."""
    try:
        price = Decimal(message.text.replace(',', '.'))
        if price < 0:
            raise ValueError
    except (ValueError, InvalidOperation):
        await message.answer("❌ Неверная цена. Введите число >= 0:")
        return

    await state.update_data(purchase_price=price)
    await state.set_state(PurchaseStates.waiting_for_supplier)

    await message.answer("🏢 Введите название поставщика (или '-' чтобы пропустить):")


@router.message(PurchaseStates.waiting_for_supplier)
async def purchase_supplier_entered(message: Message, state: FSMContext, staff_profile: StaffProfile):
    """Handle supplier input and complete purchase."""
    supplier = message.text if message.text != '-' else ''

    data = await state.get_data()
    product_id = data['product_id']
    quantity = data['quantity']
    purchase_price = data['purchase_price']

    @sync_to_async
    def create_purchase():
        product = Product.objects.get(id=product_id)
        purchase = InventoryService.purchase(
            product=product,
            location=staff_profile.location,
            quantity=quantity,
            purchase_price=purchase_price,
            created_by=staff_profile.user,
            supplier=supplier
        )
        storage = StorageStock.objects.get(product=product, location=staff_profile.location)
        return product, purchase, storage

    try:
        product, purchase, storage = await create_purchase()

        total_cost = quantity * purchase_price

        await message.answer(
            f"✅ ЗАКУПКА ВЫПОЛНЕНА\n\n"
            f"📦 Товар: {product.name}\n"
            f"📊 Количество: {quantity} {product.unit}\n"
            f"💰 Цена закупки: {purchase_price}₸/{product.unit}\n"
            f"💵 Общая стоимость: {total_cost}₸\n"
            f"🏢 Поставщик: {supplier or 'Не указан'}\n\n"
            f"📦 На складе: {storage.quantity} {product.unit}",
            reply_markup=_menu_keyboard(staff_profile)
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Purchase error: {e}")
        await message.answer(f"❌ Ошибка закупки: {str(e)}", reply_markup=_menu_keyboard(staff_profile))
        await state.clear()


# ============================================================================
# TRANSFER (Перемещение: storage → display)
# ============================================================================

@router.message(F.text == "🔄 Перемещение")
async def start_transfer(message: Message, state: FSMContext, staff_profile: StaffProfile):
    """Start transfer process (storage → display)."""
    if staff_profile.role not in [StaffProfile.Role.ADMIN, StaffProfile.Role.MANAGER]:
        await message.answer("❌ У вас нет прав для перемещения товара.")
        return

    @sync_to_async
    def get_categories_keyboard():
        return get_categories_inline_keyboard(staff_profile.location.id)

    categories_keyboard = await get_categories_keyboard()

    instruction_msg = await message.answer(
        "🔄 ПЕРЕМЕЩЕНИЕ ТОВАРА\n\n"
        "Перемещение со склада на витрину.\n"
        "Выберите категорию товара:",
        reply_markup=get_cancel_keyboard()
    )

    categories_msg = await message.answer(
        "📁 Категории:",
        reply_markup=categories_keyboard
    )

    await state.set_state(TransferStates.waiting_for_product)
    await state.update_data(
        instruction_msg_id=instruction_msg.message_id,
        categories_msg_id=categories_msg.message_id
    )


@router.callback_query(TransferStates.waiting_for_product, F.data.startswith("product:"))
async def transfer_product_selected(callback: CallbackQuery, state: FSMContext, staff_profile: StaffProfile):
    """Handle product selection for transfer."""
    product_id = int(callback.data.split(":")[1])

    @sync_to_async
    def get_product_and_stock():
        product = Product.objects.get(id=product_id, location=staff_profile.location)
        storage, _ = StorageStock.objects.get_or_create(
            product=product,
            location=staff_profile.location,
            defaults={'quantity': Decimal('0.00')}
        )
        return product, storage

    try:
        product, storage = await get_product_and_stock()
    except Product.DoesNotExist:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    if storage.quantity <= 0:
        await callback.answer("❌ Товар отсутствует на складе", show_alert=True)
        return

    await state.update_data(product_id=product_id)
    await state.set_state(TransferStates.waiting_for_quantity)

    await callback.message.edit_text(
        f"🔄 Перемещение: {product.name}\n\n"
        f"📦 На складе: {storage.quantity} {product.unit}\n\n"
        f"Введите количество для перемещения на витрину:"
    )
    await callback.answer()


@router.message(TransferStates.waiting_for_quantity)
async def transfer_quantity_entered(message: Message, state: FSMContext, staff_profile: StaffProfile):
    """Handle quantity input and complete transfer."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Перемещение отменено", reply_markup=_menu_keyboard(staff_profile))
        return

    try:
        quantity = Decimal(message.text.replace(',', '.'))
        if quantity <= 0:
            raise ValueError
    except (ValueError, InvalidOperation):
        await message.answer("❌ Неверное количество. Введите положительное число:")
        return

    data = await state.get_data()
    product_id = data['product_id']

    @sync_to_async
    def create_transfer():
        product = Product.objects.get(id=product_id)
        transfer = InventoryService.transfer(
            product=product,
            location=staff_profile.location,
            quantity=quantity,
            created_by=staff_profile.user
        )
        storage, _ = StorageStock.objects.get_or_create(
            product=product, location=staff_profile.location,
            defaults={'quantity': Decimal('0.00')}
        )
        display, _ = DisplayStock.objects.get_or_create(
            product=product, location=staff_profile.location,
            defaults={'quantity': Decimal('0.00')}
        )
        return product, transfer, storage, display

    try:
        product, transfer, storage, display = await create_transfer()

        await message.answer(
            f"✅ ПЕРЕМЕЩЕНИЕ ВЫПОЛНЕНО\n\n"
            f"📦 Товар: {product.name}\n"
            f"📊 Количество: {quantity} {product.unit}\n\n"
            f"📦 На складе: {storage.quantity} {product.unit}\n"
            f"🏪 На витрине: {display.quantity} {product.unit}",
            reply_markup=_menu_keyboard(staff_profile)
        )

        await state.clear()

    except ValidationError as e:
        await message.answer(f"❌ {str(e)}", reply_markup=_menu_keyboard(staff_profile))
        await state.clear()
    except Exception as e:
        logger.error(f"Transfer error: {e}")
        await message.answer(f"❌ Ошибка перемещения: {str(e)}", reply_markup=_menu_keyboard(staff_profile))
        await state.clear()


# ============================================================================
# FALLBACK HANDLERS
# ============================================================================

@router.callback_query(F.data.startswith("product:"))
async def product_selected_no_state(callback: CallbackQuery):
    """Catch product selections that don't match any active flow (stale keyboards)."""
    await callback.answer(
        "❌ Сессия устарела. Начните действие заново из меню.",
        show_alert=True
    )

