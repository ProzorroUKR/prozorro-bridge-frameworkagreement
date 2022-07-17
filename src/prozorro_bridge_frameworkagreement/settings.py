import os
from prozorro_crawler.settings import logger, PUBLIC_API_HOST


LOGGER = logger

API_HOST = os.environ.get("API_HOST", PUBLIC_API_HOST)
API_TOKEN = os.environ.get("API_TOKEN", "fa_bot")
API_TOKEN_POST_AGREEMENTS = os.environ.get("API_TOKEN_POST_AGREEMENTS", "agreements")
API_TOKEN_GET_CREDENTIALS = os.environ.get("API_TOKEN_GET_CREDENTIALS", "contracting")

ERROR_INTERVAL = int(os.environ.get("ERROR_INTERVAL", 10))

JOURNAL_PREFIX = os.environ.get("JOURNAL_PREFIX", "JOURNAL_")
