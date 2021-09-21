from prozorro_bridge_frameworkagreement.settings import LOGGER


def journal_context(record: dict = None, params: dict = None) -> dict:
    if record is None:
        record = {}
    if params is None:
        params = {}
    for k, v in params.items():
        record["JOURNAL_" + k] = v
    return record


def check_tender(tender: dict) -> bool:
    if "agreements" not in tender:
        LOGGER.warn(
            "No agreements found in tender {}".format(tender["id"]),
            extra=journal_context({"MESSAGE_ID": "missing_agreements"}, params={"TENDER_ID": tender["id"]})
        )
        return False
