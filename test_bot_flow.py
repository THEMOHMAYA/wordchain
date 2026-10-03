"""
End-to-End Async Simulator for Wordchain Game & Auto-Start.
"""
import asyncio
import sys
import unittest

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import dictionary
from game import Player, WordchainGame, GameState, GameManager


class AsyncMockBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id: int, text: str, **kwargs):
        self.sent_messages.append({"chat_id": chat_id, "text": text})


class AsyncMockApp:
    def __init__(self):
        self.bot = AsyncMockBot()


class TestAsyncFlow(unittest.IsolatedAsyncioTestCase):
    async def test_auto_start_flow(self):
        app = AsyncMockApp()
        p1 = Player(user_id=1, first_name="PlayerOne")
        p2 = Player(user_id=2, first_name="PlayerTwo")
        game = WordchainGame(chat_id=123, host=p1)
        game.add_player(p2)

        # Simulate quick auto-start flow
        async def mock_lobby():
            await asyncio.sleep(0.01)
            # Simulate auto-start calling start_game_flow
            game.cancel_lobby_timer()
            success, msg = game.start_game()
            self.assertTrue(success)

            turn_order = "🎮 Game starting! Turn order:\n" + "\n".join([f"{i+1}. {p.name}" for i, p in enumerate(game.players)])
            await app.bot.send_message(chat_id=123, text=turn_order)

            # First turn prompt
            cur = game.get_current_player()
            prompt = f"✍️ {cur.name}, your turn! Send any valid English word to start. 20 seconds on the clock."
            await app.bot.send_message(chat_id=123, text=prompt)

        task = asyncio.create_task(mock_lobby())
        game.lobby_timer_task = task
        await task

        # Check messages sent
        self.assertEqual(len(app.bot.sent_messages), 2)
        self.assertIn("Game starting!", app.bot.sent_messages[0]["text"])
        self.assertIn("your turn!", app.bot.sent_messages[1]["text"])

        # Player 1 plays word
        cur_p = game.get_current_player()
        valid, reply, elim = game.process_word(cur_p.user_id, "Apple")
        self.assertTrue(valid)
        self.assertEqual(game.target_letter, "E")

        # Player 2 plays word
        next_p = game.get_current_player()
        valid2, reply2, elim2 = game.process_word(next_p.user_id, "Elephant")
        self.assertTrue(valid2)
        self.assertEqual(game.target_letter, "T")


if __name__ == "__main__":
    unittest.main()
