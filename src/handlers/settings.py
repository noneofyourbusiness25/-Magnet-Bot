from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ForceReply
from src.database.db import db
import os
import json

# State machine for conversation logic
user_states = {}

def is_sudo(user_id: int) -> bool:
    sudo_users_str = os.environ.get("SUDO_USERS", "")
    if not sudo_users_str:
        return True # If no sudo users defined, allow anyone for now
    sudo_users = [int(x.strip()) for x in sudo_users_str.split(",") if x.strip()]
    return user_id in sudo_users

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    if not is_sudo(message.from_user.id):
        return await message.reply("You are not authorized to use this bot.")
    await message.reply("👋 Hello! I am your Telegram Forwarder Bot.\n\nUse /settings to configure me.")


@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client: Client, message: Message):
    if not is_sudo(message.from_user.id):
        return await message.reply("You are not authorized to use this bot.")

    user_settings = await db.get_settings(message.from_user.id)
    await message.reply("⚙️ **Settings Panel**", reply_markup=get_settings_keyboard(user_settings))

def get_settings_keyboard(user_settings: dict) -> InlineKeyboardMarkup:
    mode = user_settings.get("upload_mode", "Document")
    meta_toggle = "✅ On" if user_settings.get("toggle_metadata", True) else "❌ Off"

    keyboard = [
        [
            InlineKeyboardButton(f"Upload Mode: {mode}", callback_data="toggle_mode"),
            InlineKeyboardButton(f"Metadata Edit: {meta_toggle}", callback_data="toggle_meta")
        ],
        [
            InlineKeyboardButton("Set Channels", callback_data="set_channels"),
            InlineKeyboardButton("Set Metadata Rules", callback_data="set_rules")
        ],
        [
            InlineKeyboardButton("Text Blacklist", callback_data="set_blacklist"),
            InlineKeyboardButton("Thumbnail", callback_data="set_thumbnail")
        ],
        [
            InlineKeyboardButton("Close", callback_data="close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

@Client.on_callback_query(filters.regex("^(toggle_mode|toggle_meta|close|set_channels|set_rules|set_blacklist|set_thumbnail)$"))
async def settings_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_sudo(user_id):
        return await callback_query.answer("Unauthorized", show_alert=True)

    data = callback_query.data
    user_settings = await db.get_settings(user_id)

    if data == "close":
        await callback_query.message.delete()
        user_states.pop(user_id, None)
        return

    elif data == "toggle_mode":
        current = user_settings.get("upload_mode", "Document")
        new_mode = "Video" if current == "Document" else "Document"
        await db.update_setting(user_id, "upload_mode", new_mode)
        user_settings["upload_mode"] = new_mode
        await callback_query.message.edit_reply_markup(reply_markup=get_settings_keyboard(user_settings))

    elif data == "toggle_meta":
        current = user_settings.get("toggle_metadata", True)
        new_toggle = not current
        await db.update_setting(user_id, "toggle_metadata", new_toggle)
        user_settings["toggle_metadata"] = new_toggle
        await callback_query.message.edit_reply_markup(reply_markup=get_settings_keyboard(user_settings))

    elif data == "set_channels":
        user_states[user_id] = "awaiting_channels"
        msg = "Please send the **Source Channel ID** and **Target Channel ID** separated by a space.\nExample: `-100123456 -100987654`"
        await callback_query.message.reply(msg, reply_markup=ForceReply(selective=True))

    elif data == "set_rules":
        user_states[user_id] = "awaiting_rules"
        msg = "Send a JSON payload for metadata rules.\nExample:\n`{\"video_rules\": [{\"pattern\": \".*\", \"action\": \"replace\", \"replacement\": \"My Title\"}]}`"
        await callback_query.message.reply(msg, reply_markup=ForceReply(selective=True))

    elif data == "set_blacklist":
        user_states[user_id] = "awaiting_blacklist"
        msg = "Send a comma-separated list of words to blacklist.\nExample: `spam.com, @spamchannel`"
        await callback_query.message.reply(msg, reply_markup=ForceReply(selective=True))

    elif data == "set_thumbnail":
        user_states[user_id] = "awaiting_thumbnail"
        msg = "Please send the new thumbnail image (as a Photo)."
        await callback_query.message.reply(msg, reply_markup=ForceReply(selective=True))

@Client.on_message(filters.private & filters.reply)
async def state_machine_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states:
        return

    state = user_states[user_id]

    if state == "awaiting_channels":
        parts = message.text.split()
        if len(parts) == 2:
            try:
                source = int(parts[0])
                target = int(parts[1])
                await db.update_setting(user_id, "source_channel", source)
                await db.update_setting(user_id, "target_channel", target)
                await message.reply("✅ Channels updated.")
            except ValueError:
                await message.reply("❌ Invalid format. IDs must be numbers.")
        else:
            await message.reply("❌ Please provide exactly two IDs.")

    elif state == "awaiting_rules":
        try:
            rules = json.loads(message.text)
            if "video_rules" in rules:
                await db.update_setting(user_id, "video_rules", rules["video_rules"])
            if "audio_rules" in rules:
                await db.update_setting(user_id, "audio_rules", rules["audio_rules"])
            if "sub_rules" in rules:
                await db.update_setting(user_id, "sub_rules", rules["sub_rules"])
            await message.reply("✅ Metadata rules updated.")
        except Exception as e:
            await message.reply(f"❌ Invalid JSON format: {e}")

    elif state == "awaiting_blacklist":
        if message.text:
            words = [w.strip() for w in message.text.split(",") if w.strip()]
            await db.update_setting(user_id, "blacklisted_words", words)
            await message.reply("✅ Blacklist updated.")
        else:
            await message.reply("❌ Invalid text input.")

    elif state == "awaiting_thumbnail":
        if message.photo:
            file_id = message.photo.file_id
            await db.update_setting(user_id, "thumbnail", file_id)
            await message.reply("✅ Thumbnail saved successfully.")
        else:
            await message.reply("❌ Please send an image/photo.")

    # Reset state
    user_states.pop(user_id, None)
