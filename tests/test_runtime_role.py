import os
import unittest
from unittest.mock import patch

from runtime_role import RuntimeRoleError, assert_runtime_role


class RuntimeRoleTests(unittest.TestCase):
    def test_matching_role_passes(self):
        with patch.dict(os.environ, {"APP_ROLE": "BIMA_INTERNAL_WEB"}, clear=False):
            self.assertEqual(assert_runtime_role("BIMA_INTERNAL_WEB"), "BIMA_INTERNAL_WEB")

    def test_missing_role_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeRoleError):
                assert_runtime_role("BIMA_INTERNAL_WEB")

    def test_wrong_role_fails_closed(self):
        with patch.dict(os.environ, {"APP_ROLE": "BIMA_PUBLIC"}, clear=False):
            with self.assertRaises(RuntimeRoleError):
                assert_runtime_role("BIMA_INTERNAL_WEB")


if __name__ == "__main__":
    unittest.main()
