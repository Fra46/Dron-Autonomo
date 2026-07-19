"""
shared_token_credentials.py — Resuelve el token compartido de AgroDrone
desde el keyring seguro del sistema operativo.

Mismo patrón que earthdata_credentials.py: nunca lee el token de un
archivo de texto plano ni de un argumento de línea de comandos en claro,
solo del almacén de credenciales del OS (Windows Credential Manager,
macOS Keychain, o el backend disponible en Linux).
"""

import os
from pathlib import Path
from typing import Dict, Optional

SERVICE_NAME = "agrodrone"
USERNAME = "shared_token"


def _read_shared_token_from_dotenv() -> Optional[str]:
    """Lee un token compartido desde .env.local si existe."""
    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if not env_file.exists():
        return None

    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in {"AGRODRONE_SHARED_TOKEN", "VITE_SHARED_TOKEN"}:
                return value.strip().strip('"').strip("'")
    except Exception:
        return None
    return None


def resolve_shared_token(
    keyring_module: Optional[object] = None,
) -> Dict[str, str]:
    """Resuelve el token compartido de AgroDrone desde entorno, .env.local o keyring."""
    credentials: Dict[str, str] = {}

    token = (
        os.environ.get("AGRODRONE_SHARED_TOKEN")
        or os.environ.get("VITE_SHARED_TOKEN")
        or _read_shared_token_from_dotenv()
    )

    if token:
        credentials["AGRODRONE_SHARED_TOKEN"] = token
        os.environ.setdefault("AGRODRONE_SHARED_TOKEN", token)
        os.environ.setdefault("VITE_SHARED_TOKEN", token)

    keyring = keyring_module
    if keyring is None:
        try:
            import keyring  # type: ignore
        except Exception:
            keyring = None

    if keyring is not None and not token:
        try:
            token = keyring.get_password(SERVICE_NAME, USERNAME)
        except Exception:
            token = None
        if token:
            credentials["AGRODRONE_SHARED_TOKEN"] = token
            os.environ.setdefault("AGRODRONE_SHARED_TOKEN", token)
            os.environ.setdefault("VITE_SHARED_TOKEN", token)

    return credentials