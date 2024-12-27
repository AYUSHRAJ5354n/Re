from dotenv import load_dotenv
load_dotenv("config.env", override=True)

import asyncio
import os
import shutil
import time

import psutil
from PIL import Image
from pyrogram import Client, filters, enums
from pyrogram.errors import (
    FloodWait,
    InputUserDeactivated,
    PeerIdInvalid,
    UserIsBlocked,
)
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from helpers.database import Database
from helpers.utils import (
    UserSettings,
    get_readable_file_size,
    get_readable_time
)
from config import Config
from helpers.constants import (
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,
    SUBTITLE_EXTENSIONS,
    BROADCAST_MSG,
)

# Global variables
botStartTime = time.time()
db = Database()
queueDB = {}
replyDB = {}
formatDB = {}

class MergeBot(Client):
    def start(self):
        super().start()
        try:
            self.send_message(
                chat_id=int(Config.OWNER),
                text="<b>Bot Started!</b>",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception as err:
            LOGGER.error("Bot alert failed! Owner might not have started the bot in PM.")
        return LOGGER.info("Bot Started!")

    def stop(self):
        super().stop()
        return LOGGER.info("Bot Stopped")


mergeApp = MergeBot(
    name="merge-bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins"),
)

if not os.path.exists("downloads"):
    os.makedirs("downloads")


@mergeApp.on_message(filters.command(["start"]) & filters.private)
async def start_handler(c: Client, m: Message):
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if not user.allowed and m.from_user.id != int(Config.OWNER):
        await m.reply_text(
            f"Hi **{m.from_user.first_name}**\n\nSorry, you are not authorized to use me.\nContact my Owner: @{Config.OWNER_USERNAME}",
            quote=True,
        )
        return

    user.allowed = True
    user.set()
    await m.reply_text(
        text=f"Hi **{m.from_user.first_name}!**\n\nI'm your video merger bot. Send me videos and I will merge them for you!",
        parse_mode=enums.ParseMode.HTML,
        quote=True,
    )


@mergeApp.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def files_handler(c: Client, m: Message):
    user_id = m.from_user.id
    user = UserSettings(user_id, m.from_user.first_name)

    # Ensure the user is authorized
    if not user.allowed and user_id != int(Config.OWNER):
        await m.reply_text(
            f"Hi **{m.from_user.first_name}**\n\nYou are unauthorized to use this bot.\nContact: @{Config.OWNER_USERNAME}",
            quote=True,
        )
        return

    media = m.video or m.document or m.audio
    if not media or not media.file_name:
        await m.reply_text("File name not found. Please re-upload or contact the bot owner.", quote=True)
        return

    # Check file type and merge mode
    file_extension = media.file_name.split(".")[-1].lower()

    if user.merge_mode == 1 and file_extension not in VIDEO_EXTENSIONS:
        await m.reply_text("This format is not allowed. Only MP4, MKV, or WEBM are supported.", quote=True)
        return

    # Process queued files
    input_queue = queueDB.get(user_id, {"videos": []})
    input_queue["videos"].append(m.id)

    queueDB[user_id] = input_queue
    msg_text = f"Video {len(input_queue['videos'])} saved. Send me more, or press 'Merge Now' when done."

    await m.reply_text(msg_text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Merge Now", callback_data="merge_now")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_process")]
    ]))


@mergeApp.on_message(filters.command(["help"]) & filters.private)
async def help_handler(c: Client, m: Message):
    await m.reply_text(
        text=(
            "How to use this bot:\n"
            "1. Send me videos you want to merge.\n"
            "2. Optionally, send me a custom thumbnail.\n"
            "3. When ready, press 'Merge Now'.\n"
            "For more help, contact: @{Config.OWNER_USERNAME}"
        ),
        parse_mode=enums.ParseMode.HTML,
        quote=True,
    )


@mergeApp.on_callback_query(filters.regex("merge_now"))
async def merge_now_callback_handler(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    queued_videos = queueDB.get(user_id, {}).get("videos", [])

    if not queued_videos or len(queued_videos) < 2:
        await cb.message.reply_text("You need at least 2 videos to merge.", quote=True)
        return

    await cb.message.reply_text("Starting merge process...")
    # (Perform the merge process here)

    # Cleanup
    queueDB[user_id] = {"videos": []}


@mergeApp.on_callback_query(filters.regex("cancel_process"))
async def cancel_callback_handler(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    queueDB[user_id] = {"videos": []}
    await cb.message.reply_text("Merge process canceled.", quote=True)
