from pyrogram import Client, filters
from database import db
from user_client import user_bot

# Helper to check if user bot is ready
def check_user_bot(func):
    async def wrapper(client, message):
        if not user_bot.is_running():
            await message.reply("⚠️ User Client is not running. Use /login first.")
            return
        return await func(client, message)
    return wrapper

@Client.on_message(filters.command("add") & filters.private)
@check_user_bot
async def add_rule(client, message):
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Usage: /add <source_id> <dest_id>")
        return

    try:
        source_id = int(args[1])
        dest_id = int(args[2])
    except ValueError:
        await message.reply("IDs must be integers.")
        return

    if db.add_rule(source_id, dest_id):
        await message.reply(f"✅ Rule added: {source_id} -> {dest_id}")
    else:
        await message.reply("⚠️ Rule already exists.")

@Client.on_message(filters.command("del") & filters.private)
@check_user_bot
async def del_rule(client, message):
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Usage: /del <source_id> <dest_id>")
        return

    try:
        source_id = int(args[1])
        dest_id = int(args[2])
    except ValueError:
        await message.reply("IDs must be integers.")
        return

    if db.remove_rule(source_id, dest_id):
        await message.reply(f"🗑️ Rule removed: {source_id} -> {dest_id}")
    else:
        await message.reply("⚠️ Rule not found.")

@Client.on_message(filters.command("list") & filters.private)
@check_user_bot
async def list_rules(client, message):
    rules = db.get_rules()
    if not rules:
        await message.reply("No forwarding rules set.")
        return

    text = "**Forwarding Rules:**\n"
    for src, dst in rules:
        text += f"`{src}` ➡️ `{dst}`\n"

    await message.reply(text)

@Client.on_message(filters.command("status") & filters.private)
async def status(client, message):
    if user_bot.is_running():
        await message.reply("✅ User Client: **ONLINE**")
    else:
        await message.reply("❌ User Client: **OFFLINE**")
