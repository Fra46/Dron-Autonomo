import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectSetupTests(unittest.TestCase):
    def test_setup_script_is_declared(self) -> None:
        package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("setup", package_json["scripts"])

    def test_backend_launcher_exists(self) -> None:
        self.assertTrue((ROOT / "scripts" / "start_backend.py").exists())


if __name__ == "__main__":
    unittest.main()
