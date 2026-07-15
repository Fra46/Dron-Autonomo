import os
from pathlib import Path
from typing import Dict, Iterable, Optional


def load_dotenv_if_present(search_roots: Optional[Iterable[Path]] = None) -> Dict[str, str]:
    """Load dotenv-like values from common project roots into the current environment."""
    roots = list(search_roots or [Path(__file__).resolve().parent, Path(__file__).resolve().parents[1]])
    loaded: Dict[str, str] = {}

    for root in roots:
        env_path = root / ".env"
        if not env_path.exists():
            continue

        try:
            with env_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if not value:
                        continue

                    aliases = {
                        "EARTHDATA_USERNAME": "EARTHDATA_USERNAME",
                        "EARTHACCESS_USERNAME": "EARTHDATA_USERNAME",
                        "NASA_USERNAME": "EARTHDATA_USERNAME",
                        "EARTHDATA_PASSWORD": "EARTHDATA_PASSWORD",
                        "EARTHACCESS_PASSWORD": "EARTHDATA_PASSWORD",
                        "NASA_PASSWORD": "EARTHDATA_PASSWORD",
                        "EARTHDATA_TOKEN": "EARTHDATA_TOKEN",
                        "EARTHACCESS_TOKEN": "EARTHDATA_TOKEN",
                        "NASA_TOKEN": "EARTHDATA_TOKEN",
                    }

                    target = aliases.get(key)
                    if target:
                        loaded[target] = value
                        os.environ.setdefault(target, value)
        except Exception as exc:
            print(f"⚠️ No pude leer {env_path}: {exc}")

    return loaded


def resolve_earthdata_credentials(
    search_roots: Optional[Iterable[Path]] = None,
    keyring_module: Optional[object] = None,
) -> Dict[str, str]:
    """Resolve NASA credentials from environment, .env, or a secure OS keyring."""
    credentials: Dict[str, str] = {}

    load_dotenv_if_present(search_roots)

    env = os.environ
    if env.get("EARTHDATA_USERNAME"):
        credentials["EARTHDATA_USERNAME"] = env["EARTHDATA_USERNAME"]
    if env.get("EARTHDATA_PASSWORD"):
        credentials["EARTHDATA_PASSWORD"] = env["EARTHDATA_PASSWORD"]
    if env.get("EARTHDATA_TOKEN"):
        credentials["EARTHDATA_TOKEN"] = env["EARTHDATA_TOKEN"]

    if not credentials.get("EARTHDATA_TOKEN"):
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
