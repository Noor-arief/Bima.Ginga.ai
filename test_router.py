import unittest
from router import route_message

class RouterRegressionTests(unittest.TestCase):
    def test_action_wins_over_domain_and_status_words(self):
        route = route_message("Meme Coin lagi aktif. Cek repo BIMA dan perbaiki bug routing sampai test pass.")
        self.assertEqual(route.kind, "execution")

    def test_plain_status_stays_informational(self):
        route = route_message("Status Meme Coin sekarang gimana?")
        self.assertEqual(route.kind, "status")

    def test_normal_chat_stays_chat(self):
        self.assertEqual(route_message("Halo BIMA").kind, "chat")

if __name__ == "__main__":
    unittest.main()
