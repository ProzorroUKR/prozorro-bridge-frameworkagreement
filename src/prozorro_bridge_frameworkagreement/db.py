from motor.motor_asyncio import AsyncIOMotorClient

from prozorro_bridge_frameworkagreement.settings import (
    MONGODB_AGREEMENTS_COLLECTION,
    MONGODB_DATABASE,
    MONGODB_URL,
)


class Db:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGODB_URL)
        self.db = getattr(self.client, MONGODB_DATABASE)
        self.collection = getattr(self.db, MONGODB_AGREEMENTS_COLLECTION)

    async def get(self, key: str) -> dict:
        return await self.collection.find_one({"_id": key})

    async def put(self, key: str, value) -> None:
        await self.collection.update_one(
            {"_id": key},
            {"$set": {"_id": key, "value": value}},
            upsert=True
        )

    async def has(self, key: str) -> bool:
        value = await self.collection.find_one({"_id": key})
        return value is not None

    async def put_item_in_cache_by_agreement(self, item_id: str, dateModified: str = None) -> None:
        # TODO: check here
        if dateModified:
            await self.put(item_id, dateModified)
