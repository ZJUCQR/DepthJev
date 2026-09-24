"""Launch configuration works before dependencies are installed."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depthjev import config


class ConfigTests(unittest.TestCase):
    def exported_settings(self, root, overrides=None):
        env = {key: value for key, value in os.environ.items() if not key.startswith("DEPTHJEV_")}
        env.update(overrides or {})
        program = (
            "import json, os; print(json.dumps({k: v for k, v in os.environ.items() if k.startswith('DEPTHJEV_')}))"
        )
        command = 'set -eu\nCFG=$("$1" -S -m depthjev.config)\neval "$CFG"\n"$1" -S -c "$2"'
        result = subprocess.run(
            ["bash", "-c", command, "config-check", sys.executable, program],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_defaults_load_without_site_packages(self):
        settings = json.loads(config.CONFIG.read_text())
        exported = self.exported_settings(config.REPO)
        for key, value in settings.items():
            if key.endswith(config.PATH_SUFFIXES):
                value = config.REPO / value
            self.assertEqual(exported[f"DEPTHJEV_{key.upper()}"], str(value))

    def test_environment_overrides_keep_their_values(self):
        overrides = {"DEPTHJEV_PORT": "23400", "DEPTHJEV_SERVER_ENV": "custom environment"}
        exported = self.exported_settings(config.REPO, overrides)
        for key, value in overrides.items():
            self.assertEqual(exported[key], value)

    def test_relocated_checkout_and_values_with_shell_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "checkout with spaces and 'quotes'"
            (root / "depthjev").mkdir(parents=True)
            for name in ("__init__.py", "config.py"):
                shutil.copy2(config.REPO / "depthjev" / name, root / "depthjev" / name)
            settings = json.loads(config.CONFIG.read_text())
            settings["jev_model"] = "model $(touch unexpected) `touch unwanted`"
            (root / "config.json").write_text(json.dumps(settings))
            exported = self.exported_settings(root)
            self.assertEqual(exported["DEPTHJEV_SERVER_ENV"], str(root / "envs/depthjev"))
            self.assertEqual(exported["DEPTHJEV_JEV_MODEL"], settings["jev_model"])
            self.assertFalse((root / "unexpected").exists())
            self.assertFalse((root / "unwanted").exists())


if __name__ == "__main__":
    unittest.main()
