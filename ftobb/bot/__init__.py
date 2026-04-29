import structlog
import telegram
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from ftobb.bot import handlers
from ftobb.config import settings

logger = structlog.getLogger(__name__)


# Setup bot
tgbot = Application.builder().token(settings.bot.token)

if settings.bot.base_url:
    tgbot.base_url(settings.bot.base_url)

tgbot = tgbot.build()

# Register handlers

## Middlewares
tgbot.add_handler(
    TypeHandler(telegram.Update, handlers.user_authorization_handler), group=1
)
tgbot.add_handler(
    CommandHandler(
        "start",
        handlers.command_start_handler,
    ),
    group=2,
)

## Main Handlers
tgbot.add_handler(
    MessageHandler(
        filters.TEXT
        | filters.VIDEO
        | filters.VOICE
        | filters.AUDIO
        | filters.ATTACHMENT,
        handlers.user_input_handler,
    ),
    group=2,
)

logger.info("bot started")
tgbot.run_polling()
