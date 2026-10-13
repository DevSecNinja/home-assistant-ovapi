"""Fixed, deliberately conservative integration limits."""

DOMAIN = "ovapi"
VERSION = "0.1.0"
API_URL = "http://v0.ovapi.nl/tpc"
USER_AGENT = (
    f"home-assistant-ovapi/{VERSION} "
    "(+https://github.com/DevSecNinja/home-assistant-ovapi)"
)
POLL_SECONDS = 120
DISCOVERY_REQUESTS = 2
DISCOVERY_WINDOW_SECONDS = 120
RETENTION_SECONDS = 29 * 60
MAX_BACKOFF_SECONDS = 60 * 60
MAX_STOPS = 10
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_DEPARTURES = 30
CONF_STOP = "stop_id"
CONF_LINES = "lines"
CONF_DESTINATION = "destination"
CONF_WALK = "walking_minutes"
CONF_TRANSPORTS = "transport_types"
CONF_ENTRY_TYPE = "entry_type"
CONF_SOURCES = "source_entry_ids"
MAX_SOURCES = 12
COMBINED_CONTEXT = "combined"
SIGNAL_COMBINED_UPDATE = f"{DOMAIN}_combined_update"
SUPPORTED_TRANSPORTS = ("bus", "tram", "metro")
CARD_INSTALL_URL = (
    "https://my.home-assistant.io/redirect/hacs_repository/"
    "?owner=DevSecNinja&repository=lovelace-ovapi&category=plugin"
)
CARD_DOCS_URL = "https://github.com/DevSecNinja/lovelace-ovapi"
