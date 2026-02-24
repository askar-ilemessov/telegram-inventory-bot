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


class PurchaseStates(StatesGroup):
    """States for purchase process (supplier → storage)."""
    waiting_for_product = State()
    waiting_for_quantity = State()
    waiting_for_price = State()
    waiting_for_supplier = State()


class TransferStates(StatesGroup):
    """States for transfer process (storage → display)."""
    waiting_for_product = State()
    waiting_for_quantity = State()

