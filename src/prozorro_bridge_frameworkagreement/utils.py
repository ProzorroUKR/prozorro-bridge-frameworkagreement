from prozorro_crawler.settings import API_VERSION, CRAWLER_USER_AGENT

from prozorro_bridge_frameworkagreement.settings import API_HOST, API_TOKEN, JOURNAL_PREFIX

BASE_URL = f"{API_HOST}/api/{API_VERSION}"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_TOKEN}",
    "User-Agent": CRAWLER_USER_AGENT,
}


def journal_context(record: dict = None, params: dict = None) -> dict:
    if record is None:
        record = {}
    if params is None:
        params = {}
    for k, v in params.items():
        record[JOURNAL_PREFIX + k] = v
    return record


def check_tender(tender: dict) -> bool:
    if (
        tender.get("procurementMethodType", "") == "closeFrameworkAgreementUA"
        and tender.get("status", "") in ("complete", "active.awarded")
    ):
        return True
    elif (
        tender.get("procurementMethodType", "") == "closeFrameworkAgreementSelectionUA"
        and tender.get("status", "") == "draft.pending"
        and (
            tender.get("lots", None) is None
            or any(lot["status"] == "active" for lot in tender["lots"])
        )
    ):
        return True
    return False
