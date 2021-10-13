def journal_context(record: dict = None, params: dict = None) -> dict:
    if record is None:
        record = {}
    if params is None:
        params = {}
    for k, v in params.items():
        record["JOURNAL_" + k] = v
    return record


def check_tender(tender: dict) -> bool:
    if (
            tender["procurementMethodType"] == "closeFrameworkAgreementUA"
            and tender["status"] in ("complete", "active.awarded")
    ):
        return True
    elif (
            tender["procurementMethodType"] == "closeFrameworkAgreementSelectionUA"
            and tender["status"] == "draft.pending"
            and (
                    tender.get("lots", None) is None
                    or any(lot["status"] == "active" for lot in tender["lots"])
            )
    ):
        return True
    return False
