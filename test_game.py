"""
Unit and Integration Tests for Wordchain Game Engine with Economy & Power-ups.
"""
import unittest
import dictionary
from game import Player, WordchainGame, GameState, GameManager
from stats import stats_manager, get_title


class TestWordchainAdvanced(unittest.TestCase):
    def setUp(self):
        self.p1 = Player(user_id=901, first_name="Alice")
        self.p2 = Player(user_id=902, first_name="Bob")
        self.game = WordchainGame(chat_id=-100999, host=self.p1)
        # Reset test user stats
        pdata = stats_manager.get_player_data(901, "Alice")
        pdata["coins"] = 100
        pdata["inventory"] = {"shield": 0, "time_boost": 0, "hint": 0, "swap": 0}

    def test_economy_and_shop(self):
        # Buy shield (30 coins)
        success, msg = stats_manager.buy_item(901, "shield", "Alice")
        self.assertTrue(success)
        self.assertEqual(stats_manager.get_inventory_count(901, "shield"), 1)

        # Profile card check
        profile = stats_manager.get_profile_card(901, "Alice")
        self.assertIn("Alice", profile)
        self.assertIn("Coins", profile)

        # Leaderboard check
        lb = stats_manager.get_leaderboard_text()
        self.assertIn("WORDCHAIN GLOBAL LEADERBOARD", lb)

    def test_powerups_in_game(self):
        self.game.add_player(self.p2)
        self.game.start_game()
        self.game.target_letter = "Z"

        cur = self.game.get_current_player()

        # Buy hint & swap for current player
        stats_manager.get_player_data(cur.user_id, cur.name)["coins"] += 100
        stats_manager.buy_item(cur.user_id, "swap", cur.name)
        stats_manager.buy_item(cur.user_id, "hint", cur.name)

        # Use swap
        swap_success, swap_msg = self.game.use_swap(cur.user_id)
        self.assertTrue(swap_success)
        self.assertIn("swapped", swap_msg.lower())
        self.assertNotEqual(self.game.target_letter, "Z")

        # Use hint
        hint_success, hint_msg = self.game.use_hint(cur.user_id)
        self.assertTrue(hint_success)
        self.assertIn("Hint", hint_msg)

    def test_shield_protection(self):
        self.game.add_player(self.p2)
        self.game.start_game()
        self.game.target_letter = "E"

        cur = self.game.get_current_player()
        stats_manager.get_player_data(cur.user_id, cur.name)["coins"] += 100
        stats_manager.buy_item(cur.user_id, "shield", cur.name)

        # Wrong word - shield should protect
        valid, msg, elim = self.game.process_word(cur.user_id, "invalidxxx")
        self.assertFalse(valid)
        self.assertIn("Shield Activated", msg)
        self.assertEqual(cur.attempts_left, 3)  # Attempts not reduced!
        self.assertFalse(elim)

    def test_winner_coin_reward(self):
        # Initial coins
        init_coins = stats_manager.get_player_data(901, "Alice")["coins"]
        all_p = [(901, "Alice"), (902, "Bob")]
        stats_manager.record_match_finish(winner_id=901, all_players=all_p)

        new_coins = stats_manager.get_player_data(901, "Alice")["coins"]
        self.assertEqual(new_coins, init_coins + 30)  # +30 coins for winner!


if __name__ == "__main__":
    unittest.main()
