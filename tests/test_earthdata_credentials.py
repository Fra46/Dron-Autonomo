import os
import tempfile
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
    def test_load_dotenv_if_present(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("EARTHDATA_TOKEN=from-dotenv\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                loaded = earthdata_credentials.load_dotenv_if_present([Path(tmp_dir)])

            self.assertEqual(loaded.get("EARTHDATA_TOKEN"), "from-dotenv")

    def test_resolve_credentials_falls_back_to_keyring(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {}, clear=True):
                credentials = earthdata_credentials.resolve_earthdata_credentials(
                    search_roots=[Path(tmp_dir)],
                    keyring_module=DummyKeyring("from-keyring"),
                )

            self.assertEqual(credentials.get("EARTHDATA_TOKEN"), "from-keyring")


if __name__ == "__main__":
    unittest.main()
