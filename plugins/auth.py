from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid
from database import db
from config import Config
from user_client import user_bot
import asyncio

# Conversation states
states = {}

@Client.on_message(filters.command("login") & filters.private)
async def login_start(client, message):
    chat_id = message.chat.id

    if user_bot.is_running():
        await message.reply("User Client is already running! Use /logout to stop it.")
        return

    await message.reply("Please enter your phone number (with country code, e.g., +1234567890):")
    states[chat_id] = {"step": "phone"}

@Client.on_message(filters.text & ~filters.command(["login", "logout"]) & filters.private)
async def auth_handler(client, message):
    chat_id = message.chat.id
    state = states.get(chat_id)

    if not state:
        return

    step = state["step"]
    text = message.text

    if step == "phone":
        phone_number = text
        temp_client = Client(
            "temp_login",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            in_memory=True
        )
        try:
            await temp_client.connect()
        except Exception as e:
            await message.reply(f"Connection failed: {e}")
            del states[chat_id]
            return

        try:
            sent_code = await temp_client.send_code(phone_number)
            states[chat_id] = {
                "step": "code",
                "client": temp_client,
                "phone": phone_number,
                "hash": sent_code.phone_code_hash
            }
            await message.reply("Code sent! Please enter the OTP code (format: 1 2 3 4 5 to avoid Telegram link issues, or just 12345):")
        except Exception as e:
            await temp_client.disconnect()
            await message.reply(f"Failed to send code: {e}")
            del states[chat_id]

    elif step == "code":
        code = text.replace(" ", "")
        temp_client = state["client"]
        phone_hash = state["hash"]
        phone = state["phone"]

        try:
            await temp_client.sign_in(phone, phone_hash, code)
        except SessionPasswordNeeded:
            states[chat_id]["step"] = "password"
            await message.reply("Two-Step Verification is enabled. Please enter your password:")
            return
        except PhoneCodeInvalid:
            await message.reply("Invalid code. Try again.")
            return
        except Exception as e:
            await message.reply(f"Error: {e}")
            await temp_client.disconnect()
            del states[chat_id]
            return

        # Success (No 2FA)
        await finalize_login(client, message, temp_client, chat_id)

    elif step == "password":
        password = text
        temp_client = state["client"]

        try:
            await temp_client.check_password(password)
        except PasswordHashInvalid:
            await message.reply("Invalid password. Try again.")
            return
        except Exception as e:
            await message.reply(f"Error: {e}")
            await temp_client.disconnect()
            del states[chat_id]
            return

        # Success (With 2FA)
        await finalize_login(client, message, temp_client, chat_id)

async def finalize_login(bot, message, user_client, chat_id):
    session_string = await user_client.export_session_string()
    db.save_session(session_string)

    await user_client.disconnect() # Disconnect temp client
    del states[chat_id]

    await message.reply("✅ Login successful! Starting User Client...")
    await user_bot.start()

    if user_bot.is_running():
        await message.reply("User Client is now online and forwarding.")
    else:
        await message.reply("Failed to start User Client.")

@Client.on_message(filters.command("logout") & filters.private)
async def logout(client, message):
    await user_bot.stop()
    db.delete_session()
    await message.reply("Logged out and User Client stopped.")
