from copy import deepcopy
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from prozorro_bridge_frameworkagreement.utils import check_tender
from prozorro_bridge_frameworkagreement.bridge import (
    get_tender_credentials,
    get_tender,
    get_tender_agreements,
    fill_agreement,
    post_agreement,
    check_and_patch_agreements,
    patch_tender,
    process_tender,
)


@pytest.fixture
def credentials():
    return {"data": {"owner": "user1", "tender_token": "000000"}}


@pytest.fixture
def error_data():
    return {"error": "No permission"}


@pytest.fixture
def agreement_data():
    return {
        "id": "11111111111111111111111111111111",
        "status": "active",
        "contracts": [
            {"id": "44", "status": "active", "suppliers": [], "unitPrices": []},
            {"id": "44", "status": "cancelled", "suppliers": [], "unitPrices": []},
        ]
    }


@pytest.fixture
def tender_data(agreement_data):
    draft_agreement = deepcopy(agreement_data)
    draft_agreement["status"] = "draft"
    return {
        "id": "33",
        "dateModified": str(datetime.now()),
        "procurementMethodType": "closeFrameworkAgreementUA",
        "status": "active.awarded",
        "mode": "test",
        "procuringEntity": {"contactPoint": {}, "additionalContactPoints": []},
        "agreements": [draft_agreement, deepcopy(agreement_data)],
        "lots": [
            {"id": "lot_1", "status": "active"}
        ],
    }


@pytest.mark.asyncio
async def test_check_tender(tender_data, agreement_data):
    value = check_tender(tender_data)
    assert value is True

    test_data = deepcopy(tender_data)
    test_data["status"] = "active.tendering"
    value = check_tender(test_data)
    assert value is False

    test_data = deepcopy(tender_data)
    test_data["procurementMethodType"] = "closeFrameworkAgreementSelectionUA"
    test_data["status"] = "draft.pending"
    value = check_tender(test_data)
    assert value is True

    test_data.pop("lots")
    value = check_tender(test_data)
    assert value is True

    tender_data["procurementMethodType"] = "belowthreshold"
    value = check_tender(tender_data)
    assert value is False


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_get_tender_credentials(mocked_logger, credentials, error_data):
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=403, text=AsyncMock(return_value=error_data)),
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps(credentials))),
    ])

    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        data = await get_tender_credentials("34", session_mock)

    assert session_mock.get.await_count == 2
    assert data == credentials["data"]
    assert mocked_logger.exception.call_count == 1
    isinstance(mocked_logger.exception.call_args.args[0], ConnectionError)
    assert mocked_sleep.await_count == 1


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_get_tender(mocked_logger, tender_data, error_data):
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=403, text=AsyncMock(return_value=error_data)),
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps({"data": tender_data}))),
    ])

    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        data = await get_tender(tender_data["id"], session_mock)

    assert session_mock.get.await_count == 2
    assert data == tender_data
    assert mocked_logger.exception.call_count == 1
    isinstance(mocked_logger.exception.call_args.args[0], ConnectionError)
    assert mocked_sleep.await_count == 1


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_get_tender_agreements_not_found(mocked_logger, agreement_data, tender_data):
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=404, text=AsyncMock(return_value=json.dumps({"error": "Not found"}))),
    ])

    data = []
    async for i in get_tender_agreements(tender_data, session_mock):
        data.append(i)

    assert session_mock.get.await_count == 1
    assert mocked_logger.info.call_count == 2
    assert data == [agreement_data]


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_get_tender_agreements_found(mocked_logger, agreement_data, tender_data):
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps({"data": agreement_data}))),
    ])
    data = []
    async for i in get_tender_agreements(tender_data, session_mock):
        data.append(i)
    assert session_mock.get.await_count == 1
    assert mocked_logger.info.call_count == 2
    assert data == []

    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=410, text=AsyncMock(return_value=json.dumps({"data": agreement_data}))),
    ])
    data = []
    async for i in get_tender_agreements(tender_data, session_mock):
        data.append(i)
    assert session_mock.get.await_count == 1
    assert mocked_logger.info.call_count == 4
    assert data == []


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_fill_agreement(mocked_logger, agreement_data, credentials, tender_data):
    assert len(agreement_data["contracts"]) == 2
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps(credentials))),
    ])
    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        await fill_agreement(agreement_data, tender_data, session_mock)

    assert session_mock.get.await_count == 1
    assert mocked_logger.info.call_count == 2
    assert mocked_sleep.await_count == 0
    assert agreement_data["procuringEntity"] == tender_data["procuringEntity"]
    assert len(agreement_data["contracts"]) == 1


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_post_agreement_positive(mocked_logger, agreement_data, error_data):
    agreement_data["tender_id"] = "123asd"
    session_mock = AsyncMock()
    session_mock.post = AsyncMock(side_effect=[
        MagicMock(status=500, text=AsyncMock(return_value=json.dumps(error_data))),
        MagicMock(status=201, text=AsyncMock(return_value=json.dumps({"data": agreement_data}))),
    ])
    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        data = await post_agreement(agreement_data, session_mock)
    assert session_mock.post.await_count == 2
    assert mocked_logger.info.call_count == 3
    assert mocked_logger.error.call_count == 0
    assert mocked_logger.warning.call_count == 1
    assert mocked_sleep.await_count == 1
    assert data is True


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_post_agreement_negative(mocked_logger, agreement_data, error_data):
    agreement_data["tender_id"] = "123asd"
    session_mock = AsyncMock()
    session_mock.post = AsyncMock(side_effect=[
        MagicMock(status=422, text=AsyncMock(return_value=json.dumps(error_data))),
    ])
    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        data = await post_agreement(agreement_data, session_mock)
    assert session_mock.post.await_count == 1
    assert mocked_logger.info.call_count == 1
    assert mocked_logger.error.call_count == 1
    assert mocked_logger.warning.call_count == 0
    assert mocked_sleep.await_count == 0
    assert data is False


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_check_and_patch_agreements(mocked_logger, tender_data, agreement_data, error_data):
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=200, json=AsyncMock(return_value={"data": deepcopy(agreement_data)})),
        MagicMock(status=200, json=AsyncMock(return_value={"data": agreement_data})),
    ])
    session_mock.patch = AsyncMock(side_effect=[MagicMock(), MagicMock()])
    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        data = await check_and_patch_agreements(tender_data["agreements"], tender_data["id"], session_mock)
    assert session_mock.get.await_count == 2
    assert session_mock.patch.await_count == 2
    assert mocked_logger.info.call_count == 4
    assert mocked_logger.warning.call_count == 0
    assert mocked_sleep.await_count == 0
    assert data is True


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_check_and_patch_agreements_not_found(mocked_logger, tender_data, error_data):
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=404, text=AsyncMock(return_value=json.dumps(error_data))),
    ])
    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        data = await check_and_patch_agreements(tender_data["agreements"], tender_data["id"], session_mock)
    assert session_mock.get.await_count == 1
    assert session_mock.patch.await_count == 0
    assert mocked_logger.info.call_count == 0
    assert mocked_logger.warning.call_count == 1
    assert mocked_sleep.await_count == 0
    assert data is False


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_patch_tender_unsuccessful_negative(mocked_logger, tender_data, error_data):
    session_mock = AsyncMock()
    session_mock.patch = AsyncMock(side_effect=[
        MagicMock(status=500, text=AsyncMock(return_value=json.dumps(error_data))),
        MagicMock(status=422, text=AsyncMock(return_value=json.dumps(error_data))),
    ])
    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        await patch_tender(tender_data, False, session_mock)

    assert session_mock.patch.await_count == 2
    assert session_mock.patch.await_args.kwargs["json"]["data"]["status"] == "draft.unsuccessful"
    assert mocked_logger.info.call_count == 2
    assert mocked_logger.error.call_count == 1
    assert mocked_logger.warning.call_count == 1
    assert mocked_sleep.await_count == 1


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_patch_tender_unsuccessful_positive(mocked_logger, tender_data, error_data):
    session_mock = AsyncMock()
    session_mock.patch = AsyncMock(side_effect=[
        MagicMock(status=500, text=AsyncMock(return_value=json.dumps(error_data))),
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps({}))),
    ])
    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        await patch_tender(tender_data, False, session_mock)

    assert session_mock.patch.await_count == 2
    assert session_mock.patch.await_args.kwargs["json"]["data"]["status"] == "draft.unsuccessful"
    assert mocked_logger.info.call_count == 3
    assert mocked_logger.error.call_count == 0
    assert mocked_logger.warning.call_count == 1
    assert mocked_sleep.await_count == 1


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_patch_tender_active_positive(mocked_logger, tender_data, error_data):
    session_mock = AsyncMock()
    session_mock.patch = AsyncMock(side_effect=[
        MagicMock(status=500, text=AsyncMock(return_value=json.dumps(error_data))),
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps({}))),
    ])
    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        await patch_tender(tender_data, True, session_mock)

    assert session_mock.patch.await_count == 2
    assert session_mock.patch.await_args.kwargs["json"]["data"]["status"] == "active.enquiries"
    assert mocked_logger.info.call_count == 3
    assert mocked_logger.error.call_count == 0
    assert mocked_logger.warning.call_count == 1
    assert mocked_sleep.await_count == 1


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_process_tender_positive(mocked_logger, tender_data, agreement_data, credentials, error_data):
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps({"data": tender_data}))),
        MagicMock(status=404, text=AsyncMock(return_value=json.dumps(error_data))),
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps(credentials))),
    ])
    session_mock.post = AsyncMock(side_effect=[
        MagicMock(status=201, text=AsyncMock(return_value=json.dumps({"data": agreement_data}))),
    ])

    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        await process_tender(session_mock, tender_data)

    assert session_mock.post.await_count == 1
    assert session_mock.get.await_count == 3
    assert session_mock.patch.await_count == 0
    assert mocked_logger.info.call_count == 6
    assert mocked_logger.error.call_count == 0
    assert mocked_logger.warning.call_count == 0
    assert mocked_sleep.await_count == 0


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_process_tender_skip(mocked_logger, tender_data):
    session_mock = AsyncMock()
    tender_data.pop("agreements")
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps({"data": tender_data}))),
    ])

    await process_tender(session_mock, tender_data)

    assert session_mock.post.await_count == 0
    assert session_mock.get.await_count == 1
    assert session_mock.patch.await_count == 0
    assert mocked_logger.info.call_count == 1
    assert mocked_logger.error.call_count == 0
    assert mocked_logger.warning.call_count == 0


@pytest.mark.asyncio
@patch("prozorro_bridge_frameworkagreement.bridge.LOGGER")
async def test_process_tender_selective_positive(mocked_logger, tender_data, agreement_data, credentials, error_data):
    tender_data["procurementMethodType"] = "closeFrameworkAgreementSelectionUA"
    tender_data["status"] = "draft.pending"
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=[
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps({"data": tender_data}))),
        MagicMock(status=404, text=AsyncMock(return_value=json.dumps(error_data))),
    ])
    session_mock.patch = AsyncMock(side_effect=[
        MagicMock(status=200, text=AsyncMock(return_value=json.dumps({"data": tender_data}))),
    ])

    with patch("prozorro_bridge_frameworkagreement.bridge.asyncio.sleep", AsyncMock()) as mocked_sleep:
        await process_tender(session_mock, tender_data)

    assert session_mock.get.await_count == 2
    assert session_mock.patch.await_count == 1
    assert mocked_logger.info.call_count == 2
    assert mocked_logger.error.call_count == 0
    assert mocked_logger.warning.call_count == 1
    assert mocked_sleep.await_count == 0
