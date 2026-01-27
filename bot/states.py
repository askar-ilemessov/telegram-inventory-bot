"""
FSM States for Telegram Bot.
"""
from aiogram.fsm.state import State, StatesGroup


class SaleStates(StatesGroup):
    """States for sale process."""
    waiting_for_product = State()
    waiting_for_quantity = State()
    waiting_for_payment_method = State()


class RefundStates(StatesGroup):
    """States for refund process."""
    waiting_for_product = State()
    waiting_for_quantity = State()
    waiting_for_payment_method = State()


class ShiftStates(StatesGroup):
    """States for shift management."""
    waiting_for_close_confirmation = State()
    waiting_for_stock_count = State()


class AdjustmentStates(StatesGroup):
    """States for inventory adjustment."""
    waiting_for_product = State()
    waiting_for_quantity = State()
    waiting_for_notes = State()

