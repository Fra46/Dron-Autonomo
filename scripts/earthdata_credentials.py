import os
from typing import Dict, Optional


def resolve_earthdata_credentials(
    keyring_module: Optional[object] = None,
) -> Dict[str, str]:
    """Resolve NASA credentials from a secure OS keyring only."""
    credentials: Dict[str, str] = {}

    keyring = keyring_module
    if keyring is None:
        try:
            import keyring  # type: ignore

            keyring = keyring
        except Exception:
            keyring = None

    if keyring is not None:
        try:
            token = keyring.get_password("earthdata", "token")
        except Exception:
            token = None
        if token:
            credentials["EARTHDATA_TOKEN"] = token
            os.environ.setdefault("EARTHDATA_TOKEN", token)

    return credentials
