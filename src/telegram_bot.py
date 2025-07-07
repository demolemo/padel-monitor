from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.error import TelegramError
import logging
from src.schedule_manager import ScheduleManager


logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
        self.application = None
        self.schedule_manager = ScheduleManager()
        
    async def send_message(self, content: str):
        """Send message to the configured chat"""
        try:
            result = await self.bot.send_message(
                chat_id=self.chat_id,
                text=content
            )
            logger.info(f"Message sent to chat {self.chat_id}, message_id: {result.message_id}")
            return result
        except TelegramError as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    async def send_chat_message(self, content: str, chat_id: str):
        """Send message to specific chat (legacy method)"""
        try:
            result = await self.bot.send_message(
                chat_id=chat_id,
                text=content
            )
            logger.info(f"Message sent to chat {chat_id}, message_id: {result.message_id}")
            return result
        except TelegramError as e:
            logger.error(f"Failed to send message: {e}")
            raise

    async def ping_handler(self, update, context):
        """Handle ping command"""
        try:
            # Only respond in the configured chat
            if str(update.effective_chat.id) == str(self.chat_id):
                await update.message.reply_text("pong")
                logger.info(f"Responded to ping command in chat {self.chat_id}")
        except Exception as e:
            logger.error(f"Error handling ping command: {e}")

    async def message_handler(self, update, context):
        """Handle messages that mention the bot with 'ping'"""
        try:
            # Only respond in the configured chat
            if str(update.effective_chat.id) != str(self.chat_id):
                return
                
            message = update.message
            if message and message.text:
                # Check if bot is mentioned and message contains 'ping'
                bot_username = (await context.bot.get_me()).username
                if f"@{bot_username}" in message.text.lower() and "ping" in message.text.lower():
                    await message.reply_text("pong")
                    logger.info(f"Responded to ping mention in chat {self.chat_id}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def add_handler(self, update, context):
        """Handle /add command - parse slot info from replied message"""
        try:
            # Only respond in the configured chat
            if str(update.effective_chat.id) != str(self.chat_id):
                return
                
            message = update.message
            if not message.reply_to_message:
                await message.reply_text("❌ Используйте /add как ответ на сообщение с информацией о слоте")
                return
                
            # Get the replied message text
            replied_text = message.reply_to_message.text
            if not replied_text:
                await message.reply_text("❌ Не удалось получить текст сообщения")
                return
            
            # Try to parse slot info
            slot = self.schedule_manager.add_slot(replied_text)
            
            if slot:
                date_str = slot.start_time.strftime('%d.%m.%Y')
                time_str = f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"
                
                response = f"""✅ **Слот добавлен!**

📅 **Дата:** {date_str}
⏰ **Время:** {time_str}

Всего слотов: {self.schedule_manager.get_slot_count()}"""
                
                await message.reply_text(response, parse_mode='Markdown')
                logger.info(f"Added slot: {date_str} {time_str}")
                
            else:
                # Check if it was a parsing error or duplicate
                slot_info = self.schedule_manager.parse_slot_info(replied_text)
                if slot_info:
                    # Parsing worked, so it was a duplicate
                    date_str = slot_info['start_time'].strftime('%d.%m.%Y')
                    time_str = f"{slot_info['start_time'].strftime('%H:%M')}-{slot_info['end_time'].strftime('%H:%M')}"
                    await message.reply_text(f"❌ Слот на {date_str} в {time_str} уже существует")
                else:
                    # Parsing failed
                    await message.reply_text("❌ Не удалось распознать дату и время в сообщении")
                
        except Exception as e:
            logger.error(f"Error handling add command: {e}")
            await message.reply_text("❌ Произошла ошибка при обработке команды")

    async def list_handler(self, update, context):
        """Handle /list command - show upcoming slots"""
        try:
            # Only respond in the configured chat
            if str(update.effective_chat.id) != str(self.chat_id):
                return
                
            message = update.message
            upcoming_slots = self.schedule_manager.get_upcoming_slots()
            formatted_list = self.schedule_manager.format_slot_list(upcoming_slots)
            
            await message.reply_text(formatted_list, parse_mode='Markdown')
            logger.info(f"Displayed {len(upcoming_slots)} upcoming slots")
            
        except Exception as e:
            logger.error(f"Error handling list command: {e}")
            await message.reply_text("❌ Произошла ошибка при получении списка слотов")

    async def help_handler(self, update, context):
        """Handle /help command - show all available commands"""
        try:
            # Only respond in the configured chat
            if str(update.effective_chat.id) != str(self.chat_id):
                return
                
            message = update.message
            
            help_text = """🎾 **Падла Бот - Справка**

**Доступные команды:**

🏓 `/ping` - Проверка на живость
📅 `/add` - Добавить слот в расписание
📋 `/list` - Показать запланированные слоты
❓ `/help` - Показать что умеет

**Как добавить слот:**
1. Найдите сообщение с датой и временем слота
2. Ответьте на это сообщение командой `/add`
3. Бот автоматически распознает дату и время слота
"""
            
            await message.reply_text(help_text, parse_mode='Markdown')
            logger.info("Help command executed")
            
        except Exception as e:
            logger.error(f"Error handling help command: {e}")
            await message.reply_text("❌ Произошла ошибка при показе справки")

    def setup_handlers(self):
        """Setup command and message handlers"""
        if not self.application:
            self.application = Application.builder().token(self.bot_token).build()
            
            # Add ping command handler
            self.application.add_handler(CommandHandler("ping", self.ping_handler))
            
            # Add add command handler
            self.application.add_handler(CommandHandler("add", self.add_handler))
            
            # Add list command handler
            self.application.add_handler(CommandHandler("list", self.list_handler))
            
            # Add help command handler
            self.application.add_handler(CommandHandler("help", self.help_handler))
            
            # Add message handler for mentions
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
            
            logger.info("Telegram bot handlers configured (ping, add, list, help)")

    async def start_polling(self):
        """Start the bot's polling for incoming messages"""
        if not self.application:
            self.setup_handlers()
            
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot polling started")
        except Exception as e:
            logger.error(f"Failed to start bot polling: {e}")
            raise

    async def stop_polling(self):
        """Stop the bot's polling"""
        if self.application and self.application.updater.running:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("Telegram bot polling stopped")
            except Exception as e:
                logger.error(f"Error stopping bot polling: {e}")
    
    async def close(self):
        """Close the bot session"""
        await self.stop_polling()
        await self.bot.shutdown() 