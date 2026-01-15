# mcp/auth.py

import requests
import time
from threading import Lock

TOKEN_URL = "https://wellness.bhaktivedantahospital.com/appointmentApi/apptapi/token"
API_KEY = "mpzqo-yAQB_5IygHeqwrDFoH_r3VQu6ZXV66kMb9pG4"

_token_cache = {
    "access_token": None,
    "expires_at": 0
}


_lock = Lock()

def _parse_expires_in(expires_in: str) -> int:
    """
    Converts expires_in like '1h', '30m' to seconds.
    Default fallback: 3600 seconds
    """
    if isinstance(expires_in, str):
        expires_in = expires_in.lower().strip()
        if expires_in.endswith("h"):
            return int(expires_in[:-1]) * 3600
        if expires_in.endswith("m"):
            return int(expires_in[:-1]) * 60

    # fallback
    return 3600

def get_access_token() -> str:
    """
    Returns a valid token.
    Automatically refreshes if expired.
    """
    with _lock:
        now = time.time()

        # Token still valid (keep 60s buffer)
        if (
            _token_cache["access_token"]
            and now < _token_cache["expires_at"] - 60
        ):
            return _token_cache["access_token"]

        # Fetch new token
        response = requests.post(
            TOKEN_URL,
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()

        token = data["access_token"]
        expires_in_raw = data.get("expires_in", "1h")
        expires_in_seconds = _parse_expires_in(expires_in_raw)

        _token_cache["access_token"] = token
        _token_cache["expires_at"] = now + expires_in_seconds

        return token
