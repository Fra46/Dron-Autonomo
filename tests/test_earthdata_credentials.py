import os
import unittest
from pathlib import Path
from unittest.mock import patch
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "earthdata_credentials",
    ROOT / "scripts" / "earthdata_credentials.py",
)
earthdata_credentials = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(earthdata_credentials)


class DummyKeyring:
    def __init__(self, password=None):
        self.password = password

    def get_password(self, service, username):
        return self.password


class EarthdataCredentialsTests(unittest.TestCase):
    def test_resolve_credentials_from_keyring(self):
        with patch.dict(os.environ, {}, clear=True):
            credentials = earthdata_credentials.resolve_earthdata_credentials(
                keyring_module=DummyKeyring("from-keyring"),
            )

        self.assertEqual(credentials.get("EARTHDATA_TOKEN"), "from-keyring")


if __name__ == "__main__":
    unittest.main()
