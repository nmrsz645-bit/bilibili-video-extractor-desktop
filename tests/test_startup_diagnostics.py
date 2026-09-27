"""The frozen desktop entrypoint must reveal the real startup failure."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StartupDiagnosticsTests(unittest.TestCase):
    def test_runtime_failure_writes_original_exception_to_user_log(self):
        with tempfile.TemporaryDirectory() as data_root:
            env = os.environ.copy()
            env["LOCALAPPDATA"] = data_root
            env["PYTHONIOENCODING"] = "utf-8"
            probe = r'''
from pathlib import Path
from unittest.mock import patch
import desktop_app

messages = []
with patch.object(desktop_app, "_show_error", side_effect=messages.append):
    with patch.object(desktop_app, "_check_desktop_runtime", side_effect=OSError("pythonnet loader probe failed")):
        assert desktop_app.run() == 1
log_path = Path(desktop_app.USER_DATA_DIR) / "desktop.log"
assert log_path.is_file(), log_path
log = log_path.read_text(encoding="utf-8")
assert "OSError: pythonnet loader probe failed" in log, log
assert len(messages) == 1, messages
assert str(log_path) in messages[0], messages
assert "4.8.1" not in messages[0], messages
'''
            result = subprocess.run(
                [sys.executable, "-c", probe], cwd=ROOT, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, (result.stdout or "") + (result.stderr or ""))

    def test_runtime_check_keeps_original_error_as_cause(self):
        with tempfile.TemporaryDirectory() as data_root:
            env = os.environ.copy()
            env["LOCALAPPDATA"] = data_root
            env["PYTHONIOENCODING"] = "utf-8"
            probe = r'''
import sys
import types
from unittest.mock import patch
import desktop_app

fake_clr = types.ModuleType("clr")
def fail(_):
    raise OSError("Windows Forms probe failed")
fake_clr.AddReference = fail
with patch.object(sys, "frozen", True, create=True), patch.dict(sys.modules, {"clr": fake_clr}):
    try:
        desktop_app._check_desktop_runtime()
    except RuntimeError as exc:
        assert isinstance(exc.__cause__, OSError), repr(exc.__cause__)
        assert "Windows Forms probe failed" in str(exc.__cause__)
        assert "4.8.1" not in str(exc), str(exc)
    else:
        raise AssertionError("Expected runtime failure")
'''
            result = subprocess.run(
                [sys.executable, "-c", probe], cwd=ROOT, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, (result.stdout or "") + (result.stderr or ""))


if __name__ == "__main__":
    unittest.main()
