"""
Keyboards for Telegram Bot.
"""
from typing import List
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apps.inventory.models import Product, Category
from apps.pos.models import Payment


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard."""
    keyboard = [
        [KeyboardButton(text="📦 Продажа"), KeyboardButton(text="↩️ Возврат")],
        [KeyboardButton(text="📊 Смена"), KeyboardButton(text="📈 Отчеты")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_reports_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get reports menu keyboard."""
    keyboard = [
        [KeyboardButton(text="📊 Общий отчет")],
        [KeyboardButton(text="💰 Финансовый отчет")],
        [KeyboardButton(text="📦 Отчет продаж"), KeyboardButton(text="↩️ Отчет возвратов")],
        [KeyboardButton(text="📋 Инвентаризация")],
        [KeyboardButton(text="◀️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_shift_menu_keyboard(has_open_shift: bool) -> ReplyKeyboardMarkup:
    """Get shift management keyboard."""
    if has_open_shift:
        keyboard = [
            [KeyboardButton(text="🔴 Закрыть смену")],
            [KeyboardButton(text="◀️ Назад")]
        ]
    else:
        keyboard = [
            [KeyboardButton(text="🟢 Открыть смену")],
            [KeyboardButton(text="◀️ Назад")]
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_payment_method_keyboard() -> ReplyKeyboardMarkup:
    """Get payment method selection keyboard."""
    keyboard = [
        [KeyboardButton(text="💵 Наличные"), KeyboardButton(text="💳 Карта")],
        [KeyboardButton(text="🔄 Перевод")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Get cancel keyboard."""
    keyboard = [[KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """Get yes/no confirmation keyboard."""
    keyboard = [
        [KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_categories_inline_keyboard(location_id: int) -> InlineKeyboardMarkup:
    """Get inline keyboard with product categories."""
    categories = Category.objects.filter(
        is_active=True,
        products__location_id=location_id,
        products__is_active=True
    ).distinct()
    
    buttons = []
    for category in categories:
        buttons.append([
            InlineKeyboardButton(
                text=category.name,
                callback_data=f"category:{category.id}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_products_inline_keyboard(category_id: int, location_id: int) -> InlineKeyboardMarkup:
    """Get inline keyboard with products in category."""
    products = Product.objects.filter(
        category_id=category_id,
        location_id=location_id,
        is_active=True
    ).order_by('name')
    
    buttons = []
    for product in products:
        stock_info = f" (ост: {product.stock_quantity})" if product.stock_quantity > 0 else " (нет в наличии)"
        buttons.append([
            InlineKeyboardButton(
                text=f"{product.name} - {product.price}₸{stock_info}",
                callback_data=f"product:{product.id}"
            )
        ])
    
    # Add back button
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_categories")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def parse_payment_method(text: str) -> str:
    """Parse payment method from button text."""
    mapping = {
        "💵 Наличные": Payment.PaymentMethod.CASH,
        "💳 Карта": Payment.PaymentMethod.CARD,
        "🔄 Перевод": Payment.PaymentMethod.TRANSFER,
    }
    return mapping.get(text, Payment.PaymentMethod.CASH)

