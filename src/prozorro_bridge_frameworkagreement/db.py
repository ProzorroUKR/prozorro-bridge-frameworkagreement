from motor.motor_asyncio import AsyncIOMotorClient

from prozorro_bridge_frameworkagreement.settings import (
    MONGODB_AGREEMENTS_COLLECTION,
    MONGODB_SELECTIVE_COLLECTION,
    MONGODB_DATABASE,
    MONGODB_URL,
)


class Db:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGODB_URL)
        self.db = getattr(self.client, MONGODB_DATABASE)
        self.agreements_collection = getattr(self.db, MONGODB_AGREEMENTS_COLLECTION)
        self.selective_collection = getattr(self.db, MONGODB_SELECTIVE_COLLECTION)

    async def has_agreements_tender(self, tender_id: str) -> bool:
        value = await self.agreements_collection.find_one({"_id": tender_id})
        return value is not None

    async def cache_agreements_tender(self, tender_id: str, dateModified: str) -> None:
        await self.agreements_collection.insert_one(
            {"_id": tender_id, "dateModified": dateModified}
        )

    async def has_selective_tender(self, tender_id: str) -> bool:
        value = await self.selective_collection.find_one({"_id": tender_id})
        return value is not None

    async def cache_selective_tender(self, tender_id: str, dateModified: str) -> None:
        await self.selective_collection.insert_one(
            {"_id": tender_id, "dateModified": dateModified}
        )
