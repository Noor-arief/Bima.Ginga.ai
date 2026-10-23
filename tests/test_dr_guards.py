import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException

# Prevent imports of the persistent task store from creating /data on CI runners.
os.environ.setdefault("BIMAGINGA_DATA_DIR", tempfile.mkdtemp(prefix="bimaginga-dr-tests-"))
import app


class DisasterRecoveryGuards(unittest.TestCase):
    def test_owner_auth_fails_closed_without_key(self):
        with patch.dict(os.environ, {"BIMAGINGA_OWNER_KEY": ""}):
            with self.assertRaises(HTTPException) as context:
                app.require_owner(None)
            self.assertEqual(context.exception.status_code, 503)

    def test_owner_auth_rejects_wrong_key_and_accepts_exact_match(self):
        with patch.dict(os.environ, {"BIMAGINGA_OWNER_KEY": "fixture-not-a-real-secret"}):
            with self.assertRaises(HTTPException) as context:
                app.require_owner("incorrect")
            self.assertEqual(context.exception.status_code, 401)
            self.assertIsNone(app.require_owner("fixture-not-a-real-secret"))

    def test_standby_blocks_runtime_and_leaves_task_state_untouched(self):
        with patch.dict(os.environ, {"BIMA_DR_STANDBY": "true"}):
            self.assertTrue(app.dr_standby())
            self.assertFalse(app.health()["execution_enabled"])
            with patch.object(app, "recover_interrupted", side_effect=AssertionError("should never modify tasks")):
                with patch.object(app, "list_tasks", side_effect=AssertionError("should never resume tasks")):
                    self.assertIsNone(app.startup())
            with self.assertRaises(HTTPException) as context:
                app.require_active_runtime()
            self.assertEqual(context.exception.status_code, 503)
            with self.assertRaises(HTTPException):
                app.conversations()

    def test_active_runtime_remains_compatible(self):
        with patch.dict(os.environ, {"BIMA_DR_STANDBY": "false"}):
            self.assertFalse(app.dr_standby())
            self.assertEqual(app.health()["status"], "ok")
            self.assertIsNone(app.require_active_runtime())


if __name__ == "__main__":
    unittest.main()
