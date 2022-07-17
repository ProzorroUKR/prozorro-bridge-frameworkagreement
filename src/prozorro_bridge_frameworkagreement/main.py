from aiohttp import ClientSession
import asyncio
from prozorro_crawler.main import main

from prozorro_bridge_frameworkagreement.bridge import process_tender


API_OPT_FIELDS = (
    "status",
    "procurementMethodType",
    "lots",
    "agreements",
    "procuringEntity",
    "mode",
)

async def data_handler(session: ClientSession, items: list) -> None:
    process_items_tasks = []
    for item in items:
        coroutine = process_tender(session, item)
        process_items_tasks.append(coroutine)
    await asyncio.gather(*process_items_tasks)


if __name__ == "__main__":
    main(data_handler, opt_fields=API_OPT_FIELDS)
