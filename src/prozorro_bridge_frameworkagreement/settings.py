import os
from prozorro_crawler.settings import logger, PUBLIC_API_HOST

LOGGER = logger

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://root:example@localhost:27017")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "prozorro-bridge-frameworkagreement")
MONGODB_AGREEMENTS_COLLECTION = os.environ.get("MONGODB_AGREEMENTS_COLLECTION", "agreements")
MONGODB_SELECTIVE_COLLECTION = os.environ.get("MONGODB_SELECTIVE_COLLECTION", "selective")

API_OPT_FIELDS = os.environ.get("API_OPT_FIELDS", "status,lots,procurementMethodType")
API_HOST = os.environ.get("API_HOST", PUBLIC_API_HOST)
API_TOKEN = os.environ.get("API_TOKEN", "fa_bot")
API_TOKEN_POST_AGREEMENTS = os.environ.get("API_TOKEN_POST_AGREEMENTS", "agreements")
API_TOKEN_GET_CREDENTIALS = os.environ.get("API_TOKEN_GET_CREDENTIALS", "contracting")

ERROR_INTERVAL = int(os.environ.get("ERROR_INTERVAL", 10))
