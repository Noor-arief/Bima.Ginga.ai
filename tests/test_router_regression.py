import unittest

from router import is_continuation, route_message


class RouterRegressionTests(unittest.TestCase):
    def test_career_conversation_is_chat(self):
        self.assertEqual(
            route_message("lanjut karir dah, tapi bikin kemampuan gue bisa teruji lah. gue buat lo hidup kan sekarang").kind,
            "chat",
        )

    def test_bare_lanjut_without_active_task_is_chat(self):
        self.assertEqual(route_message("lanjut").kind, "chat")

    def test_lanjut_with_active_task_is_execution(self):
        self.assertEqual(route_message("lanjut", active_task=True).kind, "execution")
        self.assertTrue(is_continuation("lanjut dong"))
        self.assertTrue(is_continuation("ok lanjut"))

    def test_explicit_repo_fix_beats_domain_topic(self):
        message = "Meme Coin lagi aktif. Cek repo BIMA dan perbaiki bug routing sampai test pass."
        self.assertEqual(route_message(message).kind, "execution")

    def test_status_is_read_only_route(self):
        self.assertEqual(route_message("status project BIMA sekarang gimana?").kind, "status")

    def test_concrete_buat_artifact_is_execution(self):
        self.assertEqual(route_message("buat file regression-test.txt").kind, "execution")


if __name__ == "__main__":
    unittest.main()
