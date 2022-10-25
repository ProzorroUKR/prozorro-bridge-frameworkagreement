from aiohttp import ClientSession
import asyncio
import json
from typing import AsyncGenerator

from prozorro_bridge_frameworkagreement.settings import (
    LOGGER,
    ERROR_INTERVAL,
    API_TOKEN,
    API_TOKEN_GET_CREDENTIALS,
    API_TOKEN_POST_AGREEMENTS,
)
from prozorro_bridge_frameworkagreement.utils import (
    journal_context,
    check_tender,
    BASE_URL,
    HEADERS,
)
from prozorro_bridge_frameworkagreement.journal_msg_ids import (
    DATABRIDGE_GET_CREDENTIALS,
    DATABRIDGE_GOT_CREDENTIALS,
    DATABRIDGE_EXCEPTION,
    DATARGIDGE_GOT_AGREEMENT_FOR_SYNC,
    DATABRIDGE_SKIP_AGREEMENT,
    DATABRIDGE_AGREEMENT_CREATING,
    DATABRIDGE_PATCH_TENDER_STATUS,
    DATABRIDGE_RECEIVED_AGREEMENT_DATA,
    DATABRIDGE_PATCH_AGREEMENT_DATA,
    DATABRIDGE_SKIP_TENDER,
    DATABRIDGE_MISSING_AGREEMENTS,
)


async def get_tender_credentials(tender_id: str, session: ClientSession) -> dict:
    HEADERS["Authorization"] = f"Bearer {API_TOKEN_GET_CREDENTIALS}"
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
                return data["data"]
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


async def get_tender_agreements(tender_to_sync: dict, session: ClientSession) -> AsyncGenerator[dict, None]:
    for agreement in tender_to_sync["agreements"]:
        if agreement["status"] != "active":
            LOGGER.info(
                f"Skipping agreement {agreement} with status {agreement['status']}",
                extra=journal_context(
                    params={"TENDER_ID": tender_to_sync["id"]}
                ),
            )
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
            yield agreement
        elif response.status == 410:
            LOGGER.info(
                f"Agreement {agreement['id']} of tender {tender_to_sync['id']} has been archived",
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_SKIP_AGREEMENT},
                    params=({"TENDER_ID": tender_to_sync["id"], "AGREEMENT_ID": agreement["id"]})
                )
            )
            continue
        elif response.status == 200:
            LOGGER.info(
                f"Agreement {agreement['id']} already exist",
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_SKIP_AGREEMENT},
                    params=({"TENDER_ID": tender_to_sync["id"], "AGREEMENT_ID": agreement["id"]})
                )
            )
            continue


async def fill_agreement(agreement: dict, tender: dict, session: ClientSession) -> None:
    credentials_data = await get_tender_credentials(tender["id"], session)
    assert "owner" in credentials_data
    assert "tender_token" in credentials_data
    agreement["agreementType"] = "cfaua"
    agreement["tender_id"] = tender["id"]
    agreement["tender_token"] = credentials_data["tender_token"]
    agreement["owner"] = credentials_data["owner"]
    agreement["procuringEntity"] = tender["procuringEntity"]
    if "mode" in tender:
        agreement["mode"] = tender["mode"]
    agreement["contracts"] = [c for c in agreement["contracts"] if c["status"] == "active"]


async def post_agreement(agreement: dict, session: ClientSession) -> bool:
    HEADERS["Authorization"] = f"Bearer {API_TOKEN_POST_AGREEMENTS}"
    while True:
        LOGGER.info(
            f"Creating agreement {agreement['id']} of tender {agreement['tender_id']}",
            extra=journal_context(
                {"MESSAGE_ID": DATABRIDGE_AGREEMENT_CREATING},
                {"TENDER_ID": agreement['tender_id'], "AGREEMENENT_ID": agreement['id']}
            )
        )
        try:
            response = await session.post(f"{BASE_URL}/agreements", json={"data": agreement}, headers=HEADERS)
        except Exception as e:
            LOGGER.warning(
                f"Error on posting agreement {agreement['id']} of tender {agreement['tender_id']}. "
                f"Response: {str(e)}"
            )
            await asyncio.sleep(ERROR_INTERVAL)
            continue
        if response.status == 201:
            LOGGER.info(f"Agreement {agreement['id']} of tender {agreement['tender_id']} successfully created")
        else:
            data = await response.text()
            if response.status in (403, 422):
                LOGGER.error(
                    f"Stop trying post agreement {agreement['id']} of tender {agreement['tender_id']}. "
                    f"Response: {data}",
                    extra=journal_context(
                        {"MESSAGE_ID": DATABRIDGE_EXCEPTION},
                        params={"TENDER_ID": agreement['tender_id']}
                    )
                )
                return False
            LOGGER.warning(
                f"Agreement {agreement['id']} was not created, retrying. "
                f"Response: {data}"
            )
            await asyncio.sleep(ERROR_INTERVAL)
            continue
        return True


async def check_and_patch_agreements(agreements: list, tender_id: str, session: ClientSession) -> bool:
    HEADERS["Authorization"] = f"Bearer {API_TOKEN}"
    for agreement in agreements:
        response = await session.get(f"{BASE_URL}/agreements/{agreement['id']}", headers=HEADERS)
        if response.status == 404:
            LOGGER.warning(
                f"Agreement {agreement['id']} doesn't exist",
                extra=journal_context(
                    params={"TENDER_ID": tender_id, "AGREEMENT_ID": agreement['id']}
                )
            )
            return False
        LOGGER.info(
            f"Received agreement data {agreement['id']}",
            extra=journal_context(
                {"MESSAGE_ID": DATABRIDGE_RECEIVED_AGREEMENT_DATA},
                params={"TENDER_ID": tender_id, "AGREEMENT_ID": agreement['id']}
            )
        )
        agreement_data = await response.json()
        agreement_data["data"].pop("id")
        agreement_data["data"].pop("documents", None)
        LOGGER.info(
            f"Patch tender agreement {agreement['id']}",
            extra=journal_context(
                {"MESSAGE_ID": DATABRIDGE_PATCH_AGREEMENT_DATA},
                params={"TENDER_ID": tender_id, "AGREEMENT_ID": agreement['id']}
            )
        )
        await session.patch(
            f"{BASE_URL}/tenders/{tender_id}/agreements/{agreement['id']}",
            json=agreement_data,
            headers=HEADERS
        )
    return True


async def patch_tender(tender: dict, agreements_exists: bool, session: ClientSession) -> None:
    HEADERS["Authorization"] = f"Bearer {API_TOKEN}"
    status = "active.enquiries"
    if not agreements_exists:
        status = "draft.unsuccessful"
    while True:
        LOGGER.info(
            f"Switch tender {tender['id']} status to {status}",
            extra=journal_context(
                {"MESSAGE_ID": DATABRIDGE_PATCH_TENDER_STATUS},
                params={"TENDER_ID": tender["id"]}
            )
        )
        try:
            response = await session.patch(
                f"{BASE_URL}/tenders/{tender['id']}",
                json={"data": {"status": status}},
                headers=HEADERS
            )
        except Exception as e:
            LOGGER.warning(
                f"Error on patching tender {tender['id']} to status {status}. "
                f"Response: {str(e)}"
            )
            await asyncio.sleep(ERROR_INTERVAL)
            continue
        data = await response.text()
        if response.status == 200:
            LOGGER.info(
                f"Successfully switched tender {tender['id']} to status {status}",
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_PATCH_TENDER_STATUS},
                    params={"TENDER_ID": tender["id"]}
                )
            )
            return
        elif response.status in (403, 422):
            LOGGER.error(
                f"Stop trying patch tender {tender['id']}. "
                f"Response: {data}",
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_EXCEPTION},
                    params={"TENDER_ID": tender["id"]}
                )
            )
            return
        else:
            LOGGER.warning(
                f"Tender {tender['id']} was not patched, retrying. "
                f"Response: {data}"
            )
            await asyncio.sleep(ERROR_INTERVAL)


async def process_tender(session: ClientSession, tender: dict) -> None:
    if not check_tender(tender):
        LOGGER.debug(
            f"Skipping tender {tender['id']} in status {tender['status']}",
            extra=journal_context(
                {"MESSAGE_ID": DATABRIDGE_SKIP_TENDER},
                params={"TENDER_ID": tender["id"]}
            ),
        )
        return None
    if tender["procurementMethodType"] == "closeFrameworkAgreementUA":
        if "agreements" not in tender:
            LOGGER.info(
                "No agreements found in tender {}".format(tender["id"]),
                extra=journal_context(
                    {"MESSAGE_ID": DATABRIDGE_MISSING_AGREEMENTS},
                    params={"TENDER_ID": tender["id"]}
                )
            )
            return None
        post_results = []
        async for agreement in get_tender_agreements(tender, session):
            await fill_agreement(agreement, tender, session)
            post_result = await post_agreement(agreement, session)
            post_results.append(post_result)
    elif tender["procurementMethodType"] == "closeFrameworkAgreementSelectionUA":
        posted_agreements = await check_and_patch_agreements(tender["agreements"], tender["id"], session)
        await patch_tender(tender, posted_agreements, session)
