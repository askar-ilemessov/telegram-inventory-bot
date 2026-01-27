"""
Middlewares for Telegram Bot.
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from asgiref.sync import sync_to_async
from apps.core.models import StaffProfile

logger = logging.getLogger('bot')


class AuthMiddleware(BaseMiddleware):
    """
    Middleware to check if user is authenticated and has access.
    Adds staff_profile to handler data.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Process event through middleware."""
        
        # Get user from event
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        telegram_id = user.id

        # Check if user exists in database
        @sync_to_async
        def get_staff_profile():
            try:
                return StaffProfile.objects.select_related(
                    'user', 'location'
                ).get(telegram_id=telegram_id, is_active=True)
            except StaffProfile.DoesNotExist:
                return None

        staff_profile = await get_staff_profile()

        if staff_profile is None:
            # User not found or not active
            logger.warning(f"Unauthorized access attempt from Telegram ID: {telegram_id}")

            if isinstance(event, Message):
                await event.answer(
                    "❌ У вас нет доступа к боту.\n"
                    "Обратитесь к администратору для получения доступа."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ У вас нет доступа к боту", show_alert=True)

            return  # Don't call handler

        # Add staff profile to handler data
        data['staff_profile'] = staff_profile

        logger.info(f"User {staff_profile.full_name} (ID: {telegram_id}) authenticated")
        
        # Call handler
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Middleware for logging all updates."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Log event and call handler."""
        
        if isinstance(event, Message):
            logger.debug(
                f"Message from {event.from_user.id}: {event.text or '[media]'}"
            )
        elif isinstance(event, CallbackQuery):
            logger.debug(
                f"Callback from {event.from_user.id}: {event.data}"
            )
        
        return await handler(event, data)

