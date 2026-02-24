"""
Keyboards for Telegram Bot.
"""
from typing import List
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apps.inventory.models import Product, Category, DisplayStock
from apps.pos.models import Payment


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard for cashiers."""
    keyboard = [
        [KeyboardButton(text="📦 Продажа"), KeyboardButton(text="↩️ Возврат")],
        [KeyboardButton(text="📊 Смена"), KeyboardButton(text="🏪 Витрина")],
        [KeyboardButton(text="📈 Отчеты"), KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_manager_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get manager menu keyboard (with inventory management)."""
    keyboard = [
        [KeyboardButton(text="📦 Продажа"), KeyboardButton(text="↩️ Возврат")],
        [KeyboardButton(text="🛒 Закупка"), KeyboardButton(text="🔄 Перемещение")],
        [KeyboardButton(text="📊 Смена"), KeyboardButton(text="📈 Отчеты")],
        [KeyboardButton(text="📋 Инвентаризация")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_stock_type_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for selecting stock type (storage/display)."""
    keyboard = [
        [
            InlineKeyboardButton(text="📦 Склад", callback_data="stock:storage"),
            InlineKeyboardButton(text="🏪 Витрина", callback_data="stock:display")
        ],
        [InlineKeyboardButton(text="📊 Всего", callback_data="stock:total")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_reports_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get reports menu keyboard for managers/admins (full access)."""
    keyboard = [
        [KeyboardButton(text="📊 Общий отчет")],
        [KeyboardButton(text="💰 Финансовый отчет")],
        [KeyboardButton(text="📦 Отчет продаж"), KeyboardButton(text="↩️ Отчет возвратов")],
        [KeyboardButton(text="📋 Инвентаризация")],
        [KeyboardButton(text="◀️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_cashier_reports_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get reports menu keyboard for cashiers (limited access)."""
    keyboard = [
        [KeyboardButton(text="📊 Общий отчет")],
        [KeyboardButton(text="📦 Отчет продаж")],
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
    """Get inline keyboard with products in category, showing display stock quantity."""
    products = Product.objects.filter(
        category_id=category_id,
        location_id=location_id,
        is_active=True
    ).order_by('name')

    # Fetch display stocks for this location in one query
    display_stocks = {
        ds.product_id: ds.quantity
        for ds in DisplayStock.objects.filter(
            product__category_id=category_id,
            location_id=location_id
        )
    }

    buttons = []
    for product in products:
        display_qty = display_stocks.get(product.id, 0)
        stock_info = f" (витрина: {display_qty})" if display_qty > 0 else " (нет на витрине)"
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

