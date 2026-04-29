from io import BytesIO

import httpx
import structlog
import telegram
from telegram.ext import (
    ContextTypes,
)

from p2i.config import settings
from p2i.storage.deps import get_storage_service

logger = structlog.getLogger(__name__)


async def user_authorization_handler(
    update: telegram.Update, _context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Check if sender user id is included in allowed user ids."""
    if not update.effective_user:
        return

    if update.effective_user.id not in settings.bot.allowed_user_ids:
        logger.warning(
            "attempt to access by an unathorized user", user_id=update.effective_user.id
        )
        return


async def command_start_handler(
    update: telegram.Update, _context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Respond with a greeting message when command /start is sent."""
    if not update.effective_message:
        logger.debug(
            "got an update with no effective_message", extra={"update": update}
        )
        return

    if not update.effective_sender:
        logger.debug("got an update with no effective_sender", extra={"update": update})
        return

    await update.effective_message.reply_text(
        f"Hi {update.effective_sender.full_name}. "
        "Good to see you here. I can download files "
        "from telegram, links from web, and youtube "
        "videos. Just send me what ever you please.",
        reply_to_message_id=update.effective_message.id,
    )


async def _process_media(  # noqa: PLR0913
    chat: telegram.Chat,
    msg: telegram.Message,
    context: ContextTypes.DEFAULT_TYPE,
    file_id: str,
    file_size: int,
    file_name: str,
    media_type: str,
    file_ext: str,  # noqa: ARG001
) -> None:

    if file_size > 20 * 1024 * 1024:
        await chat.send_message(
            (
                "Sorry. I cannot download telegram files that are larger "
                "than 20 megabytes. This is Telegram's limitation."
            ),
            reply_to_message_id=msg.id,
        )
        return

    sent_msg = await chat.send_message(
        f"Uploading {media_type}...", reply_to_message_id=msg.id
    )

    # Get file from telegram
    try:
        file = await context.bot.get_file(file_id)

        file_content = BytesIO()
        await file.download_to_memory(file_content)
        file_content.seek(0)
    except Exception as e:
        logger.exception("couldn't download file from telegram", error=e)
        await sent_msg.edit_text("Sorry :(\nCouldn't download your file.")
        return

    # Upload to s3
    try:
        storage_service = get_storage_service()
        obj_key = await storage_service.upload(msg.chat_id, file_name, file_content)
    except Exception as e:
        logger.exception("couldn't upload file to s3", error=e)
        await sent_msg.edit_text("Sorry :(\nCouldn't upload your file to storage.")
        return

    # Return URL
    get_url = await storage_service.get_signed_get_url(obj_key)
    emoji_map = {"photo": "📸", "voice": "🎙️", "video": "🎬", "document": "📄"}
    await sent_msg.edit_text(
        f"{emoji_map.get(media_type, '📎')} Download link:\n{get_url}"
    )


async def process_file(
    chat: telegram.Chat, msg: telegram.Message, context: ContextTypes.DEFAULT_TYPE
) -> None:
    doc = msg.document
    if not doc or not (doc.file_size and doc.file_name):
        logger.warning("received an upload request that has no file_size or file_name.")
        await chat.send_message(
            "Cannot process file. Sorry.", reply_to_message_id=msg.id
        )
        return

    await _process_media(
        chat,
        msg,
        context,
        file_id=doc.file_id,
        file_size=doc.file_size,
        file_name=doc.file_name,
        media_type="document",
        file_ext="",
    )


async def process_photo(
    chat: telegram.Chat, msg: telegram.Message, context: ContextTypes.DEFAULT_TYPE
) -> None:
    photo = msg.photo[-1]
    if not photo or not photo.file_size:
        logger.warning("received a photo request that has no file_size.")
        await chat.send_message(
            "Cannot process photo. Sorry.", reply_to_message_id=msg.id
        )
        return

    await _process_media(
        chat,
        msg,
        context,
        file_id=photo.file_id,
        file_size=photo.file_size,
        file_name=f"photo_{msg.message_id}.jpg",
        media_type="photo",
        file_ext=".jpg",
    )


async def process_voice(
    chat: telegram.Chat, msg: telegram.Message, context: ContextTypes.DEFAULT_TYPE
) -> None:
    voice = msg.voice
    if not voice or not voice.file_size:
        logger.warning("received a voice request that has no file_size.")
        await chat.send_message(
            "Cannot process voice. Sorry.", reply_to_message_id=msg.id
        )
        return

    await _process_media(
        chat,
        msg,
        context,
        file_id=voice.file_id,
        file_size=voice.file_size,
        file_name=f"voice_{msg.message_id}.ogg",
        media_type="voice",
        file_ext=".ogg",
    )


async def process_video(
    chat: telegram.Chat, msg: telegram.Message, context: ContextTypes.DEFAULT_TYPE
) -> None:
    video = msg.video
    if not video or not video.file_size:
        logger.warning("received a video request that has no file_size.")
        await chat.send_message(
            "Cannot process video. Sorry.", reply_to_message_id=msg.id
        )
        return

    await _process_media(
        chat,
        msg,
        context,
        file_id=video.file_id,
        file_size=video.file_size,
        file_name=f"video_{msg.message_id}.mp4",
        media_type="video",
        file_ext=".mp4",
    )


async def process_text(chat: telegram.Chat, msg: telegram.Message) -> None:
    if not msg.text:
        logger.warning("received a text message with no text")
        await chat.send_message(
            "Cannot process this link. Sorry.", reply_to_message_id=msg.id
        )
        return

    url = msg.text.strip()

    if not url.startswith(("http://", "https://")):
        await chat.send_message(
            "Please send a valid URL starting with http:// or https://",
            reply_to_message_id=msg.id,
        )
        return

    sent_msg = await chat.send_message("Fetching URL...", reply_to_message_id=msg.id)

    # Download file
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await sent_msg.edit_text("Downloading file...")

            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
    except Exception as e:
        logger.exception("couldn't fetch url", url=url, error=e)
        await sent_msg.edit_text("Sorry :(\nCouldn't download your file.")
        return

    # Upload to s3
    try:
        await sent_msg.edit_text("Uploading to bucket...")

        storage_service = get_storage_service()
        obj_key = await storage_service.upload(
            chat.id, f"webpage_{msg.message_id}.html", response.content
        )
    except Exception as e:
        logger.exception("couldn't upload file to storage", error=e)
        await sent_msg.edit_text("Sorry :(\nCouldn't upload your file to stroage..")

    # Get url
    get_url = await storage_service.get_signed_get_url(obj_key)
    await sent_msg.edit_text(f"🔗 Download link:\n{get_url}")


async def user_input_handler(
    update: telegram.Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Take user message (text, video, file, etc.), upload the file to bucket and reply back the download url."""  # noqa: E501
    if not update.effective_chat:
        logger.debug("got an update with no effective_chat", extra={"update": update})
        return

    if not update.effective_message:
        logger.debug(
            "got an update with no effective_message", extra={"update": update}
        )
        return

    chat = update.effective_chat
    msg = update.effective_message

    if msg.text:
        await process_text(chat, msg)
    elif msg.photo:
        await process_photo(chat, msg, context)
    elif msg.voice:
        await process_voice(chat, msg, context)
    elif msg.video:
        await process_video(chat, msg, context)
    elif msg.document:
        await process_file(chat, msg, context)
