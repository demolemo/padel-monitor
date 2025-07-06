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

    async def schedule_handler(self, update, context):
        """Handle /schedule command - parse visit info from replied message"""
        try:
            # Only respond in the configured chat
            if str(update.effective_chat.id) != str(self.chat_id):
                return
                
            message = update.message
            if not message.reply_to_message:
                await message.reply_text("❌ Используйте /schedule как ответ на сообщение с информацией о визите")
                return
                
            # Get the replied message text
            replied_text = message.reply_to_message.text
            if not replied_text:
                await message.reply_text("❌ Не удалось получить текст сообщения")
                return
            
            # Try to parse visit info
            visit = self.schedule_manager.add_visit(replied_text)
            
            if visit:
                date_str = visit.start_time.strftime('%d.%m.%Y')
                time_str = f"{visit.start_time.strftime('%H:%M')}-{visit.end_time.strftime('%H:%M')}"
                
                response = f"""✅ **Визит добавлен!**

📅 **Дата:** {date_str}
⏰ **Время:** {time_str}

Всего визитов: {self.schedule_manager.get_visit_count()}"""
                
                await message.reply_text(response, parse_mode='Markdown')
                logger.info(f"Added visit: {date_str} {time_str}")
                
            else:
                await message.reply_text("❌ Не удалось распознать дату и время в сообщении")
                
        except Exception as e:
            logger.error(f"Error handling schedule command: {e}")
            await message.reply_text("❌ Произошла ошибка при обработке команды")

    async def list_handler(self, update, context):
        """Handle /list command - show upcoming visits"""
        try:
            # Only respond in the configured chat
            if str(update.effective_chat.id) != str(self.chat_id):
                return
                
            message = update.message
            upcoming_visits = self.schedule_manager.get_upcoming_visits()
            formatted_list = self.schedule_manager.format_visit_list(upcoming_visits)
            
            await message.reply_text(formatted_list, parse_mode='Markdown')
            logger.info(f"Displayed {len(upcoming_visits)} upcoming visits")
            
        except Exception as e:
            logger.error(f"Error handling list command: {e}")
            await message.reply_text("❌ Произошла ошибка при получении списка визитов")

    async def help_handler(self, update, context):
        """Handle /help command - show all available commands"""
        try:
            # Only respond in the configured chat
            if str(update.effective_chat.id) != str(self.chat_id):
                return
                
            message = update.message
            
            help_text = """🎾 **Падел Бот - Справка**

**Доступные команды:**

🏓 `/ping` - Проверить работу бота
📅 `/schedule` - Добавить визит в расписание
📋 `/list` - Показать запланированные визиты
❓ `/help` - Показать эту справку

**Как добавить визит:**
1. Найдите сообщение с датой и временем
2. Ответьте на это сообщение командой `/schedule`
3. Бот автоматически распознает дату и время

**Поддерживаемые форматы дат:**
• Полные: `12 июля 2025`, `5 января 2024`
• Без года: `12 июля`, `15 марта`
• Дни недели: `понедельник`, `вторник`, `среда`
• Короткие: `пн`, `вт`, `ср`, `чт`, `пт`, `сб`, `вс`
• Относительные: `сегодня`, `завтра`, `послезавтра`

**Поддерживаемые форматы времени:**
• Классические: `с 16:00 до 17:00`, `от 16 до 17`
• Короткие: `16-17`, `16:30-17:30`
• Одиночное: `в 16:00`, `в 16` (1 час)

**Примеры сообщений:**
• "Играем в понедельник 16-17"
• "Завтра с 16 до 17"
• "Среда в 16:00"
• "пт 16-17"
• "вт время 16.00-17.00"
• "12 июля, 16:30-17:30"
• "Сегодня от 16 до 17"

Бот работает только в этом чате и запоминает визиты до перезапуска."""
            
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
            
            # Add schedule command handler
            self.application.add_handler(CommandHandler("schedule", self.schedule_handler))
            
            # Add list command handler
            self.application.add_handler(CommandHandler("list", self.list_handler))
            
            # Add help command handler
            self.application.add_handler(CommandHandler("help", self.help_handler))
            
            # Add message handler for mentions
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
            
            logger.info("Telegram bot handlers configured (ping, schedule, list, help)")

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