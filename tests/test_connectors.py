import os
import unittest
from unittest import mock

import connectors


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        for k in ("RAILWAY_API_TOKEN", "RESEND_API_KEY", "BIMA_GITHUB_TOKEN",
                  "BIMA_GITHUB_ALLOWED_REPOS", "BIMA_GITHUB_APP_ID",
                  "BIMA_GITHUB_INSTALLATION_ID", "BIMA_GITHUB_APP_PRIVATE_KEY"):
            os.environ.pop(k, None)

    def states(self):
        return {c["id"]: c["state"] for c in connectors.connector_status()}

    def test_default_states(self):
        s = self.states()
        self.assertEqual(s["railway"], "not_configured")
        self.assertEqual(s["sheets"], "soon")

    def test_configured_via_env(self):
        os.environ["RAILWAY_API_TOKEN"] = "x"
        os.environ["BIMA_GITHUB_TOKEN"] = "x"
        os.environ["BIMA_GITHUB_ALLOWED_REPOS"] = "o/r"
        s = self.states()
        self.assertEqual(s["railway"], "configured")
        self.assertEqual(s["github"], "configured")

    def test_status_never_contains_secret(self):
        os.environ["RESEND_API_KEY"] = "re_SECRET123"
        self.assertNotIn("SECRET123", str(connectors.connector_status()))

    def test_unconfigured_test_does_not_call_network(self):
        with mock.patch.object(connectors, "_json_request") as req:
            r = connectors.test_connector("resend")
        self.assertFalse(r["ok"]); req.assert_not_called()

    def test_resend_ok_and_error_message_has_no_secret(self):
        os.environ["RESEND_API_KEY"] = "re_SECRET123"
        with mock.patch.object(connectors, "_json_request", return_value={}):
            self.assertTrue(connectors.test_connector("resend")["ok"])
        with mock.patch.object(connectors, "_json_request", side_effect=RuntimeError("HTTP 401 dari api.resend.com")):
            r = connectors.test_connector("resend")
        self.assertFalse(r["ok"]); self.assertNotIn("SECRET123", r["detail"])

    def test_unknown_connector(self):
        with self.assertRaises(KeyError):
            connectors.test_connector("nope")


if __name__ == "__main__":
    unittest.main()
