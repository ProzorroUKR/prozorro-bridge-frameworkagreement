from aiohttp import ClientSession
import asyncio
import json

from prozorro_bridge_frameworkagreement.settings import BASE_URL, LOGGER, ERROR_INTERVAL, HEADERS
from prozorro_bridge_frameworkagreement.utils import journal_context, check_tender
from prozorro_bridge_frameworkagreement.db import Db
from prozorro_bridge_frameworkagreement.journal_msg_ids import (
    DATABRIDGE_GET_CREDENTIALS,
    DATABRIDGE_GOT_CREDENTIALS,
    DATABRIDGE_EXCEPTION,
    DATARGIDGE_GOT_AGREEMENT_FOR_SYNC,
    DATABRIDGE_SKIP_AGREEMENT,
    DATABRIDGE_AGREEMENT_CREATING,
)

cache_db = Db()


async def get_tender_credentials(tender_id: str, session: ClientSession) -> dict:
    url = f"{BASE_URL}/tenders/{tender_id}/extract_credentials"
    while True:
        LOGGER.info(
            f"Getting credentials for tender {tender_id}",
            extra=journal_context(
                {"MESSAGE_ID": DATABRIDGE_GET_CREDENTIALS},
                {"TENDER_ID": tender_id}
            ),
        )
        try:
            response = await session.get(url, headers=HEADERS)
            data = await response.text()
            if response.status == 200:
                data = json.loads(data)
                LOGGER.info(
                    f"Got tender {tender_id} credentials",
                    extra=journal_context(
                        {"MESSAGE_ID": DATABRIDGE_GOT_CREDENTIALS},
                        {"TENDER_ID": tender_id}
                    ),
                )
                return data
            raise ConnectionError(f"Failed to get credentials {data}")
        except Exception as e:
            LOGGER.warning(
                f"Can't get tender credentials {tender_id}",
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_EXCEPTION},
                    {"TENDER_ID": tender_id}
                ),
            )
            LOGGER.exception(e)
            await asyncio.sleep(ERROR_INTERVAL)


async def get_tender(tender_id: str, session: ClientSession) -> dict:
    while True:
        try:
            response = await session.get(f"{BASE_URL}/tenders/{tender_id}", headers=HEADERS)
            data = await response.text()
            if response.status != 200:
                raise ConnectionError(f"Error {data}")
            return json.loads(data)["data"]
        except Exception as e:
            LOGGER.warning(
                f"Fail to get tender {tender_id}",
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_EXCEPTION},
                    params={"TENDER_ID": tender_id}
                )
            )
            LOGGER.exception(e)
            await asyncio.sleep(ERROR_INTERVAL)


async def _get_tender_agreements(tender_to_sync: dict, session: ClientSession) -> list:
    # TODO: caching here
    agreements = []

    for agreement in tender_to_sync["agreements"]:
        if agreement["status"] != "active":
            continue

        if cache_db.has(agreement["id"]):
            LOGGER.info(f"Agreement {agreement['id']} exists in local db")
            await cache_db.put_item_in_cache_by_agreement(agreement, agreement["dateModified"])
            continue
        response = await session.get(f"{BASE_URL}/agreements/{agreement['id']}", headers=HEADERS)

        if response.status == 404:
            LOGGER.info(
                f"Sync agreement {agreement['id']} of tender {tender_to_sync['id']}",
                extra=journal_context(
                    {"MESSAGE_ID": DATARGIDGE_GOT_AGREEMENT_FOR_SYNC},
                    {"AGREEMENT_ID": agreement["id"], "TENDER_ID": tender_to_sync["id"]}
                )
            )
            agreements.append(agreement)
        elif response.status == 410:
            LOGGER.info(
                f"Sync agreement {agreement['id']} of tender {tender_to_sync['id']} has been archived",
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_SKIP_AGREEMENT},
                    params=({"TENDER_ID": tender_to_sync["id"], "AGREEMENT_ID": agreement["id"]})
                )
            )
            await cache_db.put_item_in_cache_by_agreement(agreement["id"], agreement["dateModified"])
            continue
        elif response.status == 200:
            await cache_db.put(agreement["id"], True)
            LOGGER.info(
                f"Agreement {agreement['id']} already exist",
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_SKIP_AGREEMENT},
                    params=({"TENDER_ID": tender_to_sync["id"], "AGREEMENT_ID": agreement["id"]})
                )
            )
            await cache_db.put_item_in_cache_by_agreement(agreement["id"], agreement["dateModified"])
            continue

    await cache_db.put_item_in_cache_by_agreement(tender_to_sync["id"], tender_to_sync["dateModified"])
    return agreements


async def get_tender_agreements(tender_to_sync: dict, session: ClientSession) -> list:
    while True:
        try:
            return await _get_tender_agreements(tender_to_sync, session)
        except Exception as e:
            LOGGER.warn(
                "Fail to handle tender agreements",
                extra=journal_context({"MESSAGE_ID": DATABRIDGE_EXCEPTION})
                )
            LOGGER.exception(e)
            await asyncio.sleep(ERROR_INTERVAL)


async def fill_agreement(agreement: dict, tender: dict, session: ClientSession) -> None:
    credentials_data = await get_tender_credentials(tender["id"], session)
    assert "owner" in credentials_data.get("data", {})
    assert "tender_token" in credentials_data.get("data", {})
    agreement["agreementType"] = "cfaua"
    agreement["tender_id"] = tender["id"]
    agreement["tender_token"] = credentials_data["data"]["tender_token"]
    agreement["owner"] = credentials_data["data"]["owner"]
    agreement["procuringEntity"] = tender["procuringEntity"]
    if "mode" in tender:
        agreement["mode"] = tender["mode"]
    agreement["contracts"] = [c for c in agreement["contracts"] if c["status"] == "active"]


async def post_agreement(agreement: dict, session: ClientSession) -> bool:
    while True:
        LOGGER.info(
            f"Creating agreement {agreement['id']} of tender {agreement['tender_id']}",
            extra=journal_context(
                {"MESSAGE_ID": DATABRIDGE_AGREEMENT_CREATING},
                {"TENDER_ID": agreement['tender_id'], "AGREEMENENT_ID": agreement['id']}
            )
        )
        response = await session.post(f"{BASE_URL}/agreements", json={"data": agreement}, headers=HEADERS)
        if response.status == 201:
            LOGGER.info(f"Agreement {agreement['id']} of tender {agreement['tender_id']} successfully created")
        else:
            data = await response.text()
            LOGGER.exception(data)
            if response.status not in (403, 422):
                LOGGER.warning(f"Stop trying post agreement {agreement['id']} of tender {agreement['tender_id']}")
                return False
            LOGGER.warning(f"Agreement {agreement['id']} of tender {agreement['tender_id']} was not created, retrying")
            await asyncio.sleep(ERROR_INTERVAL)
            continue
        return True


async def process_tender(session: ClientSession, tender: dict) -> None:
    if not check_tender(tender):
        return None
    tender_to_sync = await get_tender(tender["id"], session)
    agreements = await get_tender_agreements(tender_to_sync, session)
    for agreement in agreements:
        await fill_agreement(agreement, tender_to_sync, session)
        if await post_agreement(agreement, session):
            await cache_db.put(agreement["id"], True)
