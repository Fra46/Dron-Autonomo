"""
shared_token_credentials.py — Resuelve el token compartido de AgroDrone
desde el keyring seguro del sistema operativo.

Mismo patrón que earthdata_credentials.py: nunca lee el token de un
archivo de texto plano ni de un argumento de línea de comandos en claro,
solo del almacén de credenciales del OS (Windows Credential Manager,
macOS Keychain, o el backend disponible en Linux).
"""

import os
from typing import Dict, Optional

SERVICE_NAME = "agrodrone"
USERNAME = "shared_token"


def resolve_shared_token(
    keyring_module: Optional[object] = None,
) -> Dict[str, str]:
    """Resuelve el token compartido de AgroDrone desde el keyring del OS."""
    credentials: Dict[str, str] = {}

    keyring = keyring_module
    if keyring is None:
        try:
            import keyring  # type: ignore
        except Exception:
            keyring = None

    if keyring is not None:
        try:
            token = keyring.get_password(SERVICE_NAME, USERNAME)
        except Exception:
            token = None
        if token:
            credentials["AGRODRONE_SHARED_TOKEN"] = token
            os.environ.setdefault("AGRODRONE_SHARED_TOKEN", token)

    return credentials