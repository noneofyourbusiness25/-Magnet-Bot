import os
import motor.motor_asyncio
from typing import Dict, List

class Database:
    def __init__(self):
        self.uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.environ.get("MONGO_DB_NAME", "telegram_bot_db")
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]
        self.settings = self.db.settings

    async def get_settings(self, user_id: int) -> dict:
        """Fetch user settings, or return default settings."""
        settings = await self.settings.find_one({"user_id": user_id})
        if not settings:
            default_settings = {
                "user_id": user_id,
                "target_channel": None,
                "source_channel": None,
                "upload_mode": "Document", # or "Video"
                "thumbnail": None, # File ID of the thumbnail
                "prefix": "",
                "suffix": "",
                "blacklisted_words": [],
                "toggle_metadata": True,
                "video_rules": [], # [{'pattern': '.*', 'action': 'replace', 'replacement': 'My Video Title'}]
                "audio_rules": [],
                "sub_rules": []
            }
            await self.settings.insert_one(default_settings.copy())
            return default_settings
        return settings

    async def update_setting(self, user_id: int, key: str, value: any):
        """Update a specific setting."""
        await self.settings.update_one(
            {"user_id": user_id},
            {"$set": {key: value}},
            upsert=True
        )

    async def add_list_item(self, user_id: int, key: str, item: any):
        """Add an item to a list setting (e.g., blacklisted_words)."""
        await self.settings.update_one(
            {"user_id": user_id},
            {"$addToSet": {key: item}},
            upsert=True
        )

    async def remove_list_item(self, user_id: int, key: str, item: any):
        """Remove an item from a list setting."""
        await self.settings.update_one(
            {"user_id": user_id},
            {"$pull": {key: item}}
        )

db = Database()
