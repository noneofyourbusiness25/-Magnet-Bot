from pyrogram import Client, filters

@Client.on_message(filters.command("help"))
async def help_command(client, message):
    text = """
**Evergreen Controller Help 🌲**

**Authentication:**
`/login` - Log in to your User Account.
`/logout` - Log out and stop the User Client.
`/status` - Check if User Client is running.

**Rules:**
`/add <src_id> <dest_id>` - Add a forwarding rule.
`/del <src_id> <dest_id>` - Remove a forwarding rule.
`/list` - List all forwarding rules.

**Note:** Ensure you invite the User Account to the source/destination channels!
"""
    await message.reply(text)
