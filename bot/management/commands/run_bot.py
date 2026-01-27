"""
Django management command to run Telegram bot.
"""
import asyncio
import logging
from django.core.management.base import BaseCommand
from bot.loader import bot, dp
from bot.handlers import router
from bot.middlewares import AuthMiddleware, LoggingMiddleware

logger = logging.getLogger('bot')


class Command(BaseCommand):
    help = 'Run Telegram Bot'

    def handle(self, *args, **options):
        """Run the bot."""
        self.stdout.write(self.style.SUCCESS('Starting Telegram Bot...'))
        
        # Register middlewares
        dp.message.middleware(LoggingMiddleware())
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(LoggingMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        
        # Register router
        dp.include_router(router)
        
        logger.info("Bot middlewares and handlers registered")
        
        # Run bot
        try:
            asyncio.run(self._start_bot())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            self.stdout.write(self.style.WARNING('Bot stopped'))
    
    async def _start_bot(self):
        """Start bot polling."""
        logger.info("Starting bot polling...")
        self.stdout.write(self.style.SUCCESS('Bot is running. Press Ctrl+C to stop.'))
        
        # Delete webhook if exists
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Start polling
        await dp.start_polling(bot)

