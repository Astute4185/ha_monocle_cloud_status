from __future__ import annotations
from homeassistant.const import Platform

DEFAULT_NAME = "Monocle"
DOMAIN = "ha_monocle_cloud_status"
DATA_COORDINATOR = "coordinator"

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

SOCKET_BASE_URL = "https://monocle0.edde.world"
LOGIN_URL = "https://monocle0.edde.world/auth/login"
ORIGIN = "https://themonocleapp.catchpower.com.au"
SAVE_OVERRIDE_URL = "https://monocle0.edde.world/data/saveOverride"
REMOVE_OVERRIDE_URL = "https://monocle0.edde.world/data/removeOverride"

