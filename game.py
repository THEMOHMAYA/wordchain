"""
Wordchain Game Engine supporting Multiplayer and Solo modes.
"""
import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import config
import dictionary


class GameState(Enum):
    LOBBY = "LOBBY"
    PLAYING = "PLAYING"
    ENDED = "ENDED"


@dataclass
class Player:
    user_id: int
    first_name: str
    username: Optional[str] = None
    score: int = 0
    attempts_left: int = config.MAX_ATTEMPTS
    is_eliminated: bool = False

    @property
    def name(self) -> str:
        return self.first_name or "Player"


class WordchainGame:
    def __init__(self, chat_id: int, host: Player):
        self.chat_id: int = chat_id
        self.host: Player = host
        self.state: GameState = GameState.LOBBY
        self.created_at: float = time.time()

        # Players
        self.players: List[Player] = [host]
        self.player_map: Dict[int, Player] = {host.user_id: host}
        self.all_player_ids: List[int] = [host.user_id]
        self.active_player_index: int = 0
        self.is_solo: bool = False

        # Word chain state
        self.used_words: List[str] = []
        self.current_word: str = ""
        self.target_letter: Optional[str] = None  # None for first turn

        # Timers
        self.turn_timeout_seconds: int = config.TURN_TIMEOUT_SECONDS
        self.timer_task: Optional[asyncio.Task] = None
        self.lobby_timer_task: Optional[asyncio.Task] = None

    # -----------------------------
    # Lobby Management
    # -----------------------------
    def add_player(self, player: Player) -> Tuple[bool, str]:
        """Adds a player to the lobby."""
        if self.state != GameState.LOBBY:
            return False, "Game has already started."

        if player.user_id in self.player_map:
            return False, "You already joined this game."

        if len(self.players) >= config.MAX_PLAYERS:
            return False, f"Lobby is full! (Max {config.MAX_PLAYERS} players)"

        self.players.append(player)
        self.player_map[player.user_id] = player
        if player.user_id not in self.all_player_ids:
            self.all_player_ids.append(player.user_id)
        return True, f"✅ {player.name} joined! Total players: {len(self.players)}"

    def get_active_players(self) -> List[Player]:
        return [p for p in self.players if not p.is_eliminated]

    def can_start(self) -> Tuple[bool, str]:
        if self.state != GameState.LOBBY:
            return False, "Game is not in lobby."
        if len(self.players) < 1:
            return False, "Not enough players in lobby."
        return True, "Ready"

    # -----------------------------
    # Game Progression
    # -----------------------------
    def start_game(self) -> Tuple[bool, str]:
        ready, msg = self.can_start()
        if not ready:
            return False, msg

        self.state = GameState.PLAYING
        self.is_solo = len(self.players) == 1
        random.shuffle(self.players)
        self.active_player_index = 0
        self.target_letter = None  # First player can send any valid English word
        self.used_words = []

        # Reset attempts for each player
        for p in self.players:
            p.attempts_left = config.MAX_ATTEMPTS
            p.score = 0
            p.is_eliminated = False

        return True, "Game starting!"

    def get_current_player(self) -> Optional[Player]:
        active = self.get_active_players()
        if not active:
            return None
        if self.active_player_index >= len(active):
            self.active_player_index = 0
        return active[self.active_player_index]

    def process_word(self, user_id: int, raw_word: str) -> Tuple[bool, str, bool]:
        """
        Validates the word submission from the player.
        Returns (is_valid, message, is_eliminated).
        """
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != user_id:
            return False, "Not your turn", False

        clean = raw_word.strip().lower()

        # Check length & alphabetic & dictionary validity
        if len(clean) < 2 or not clean.isalpha() or not dictionary.is_valid_word(clean):
            return self._handle_wrong_word(current_player, "not a valid English word.")

        # If not first turn, check starting letter
        if self.target_letter is not None:
            expected = self.target_letter.lower()
            if clean[0] != expected:
                return self._handle_wrong_word(
                    current_player,
                    f"word must start with '{self.target_letter}'."
                )

        # Check already used
        if clean in self.used_words:
            return self._handle_wrong_word(
                current_player,
                f"'{clean}' has already been used."
            )

        # Word is valid!
        self.used_words.append(clean)
        self.current_word = clean
        self.target_letter = clean[-1].upper()
        current_player.score += 1
        current_player.attempts_left = config.MAX_ATTEMPTS  # Reset attempts for next turn

        # Record stats (points and longest word)
        from stats import stats_manager
        stats_manager.add_word_stats(user_id, clean, current_player.name)

        # Advance to next player
        self._advance_turn()

        msg = f"✅ Correct! +1 point. Score: {current_player.score}"
        return True, msg, False

    def _handle_wrong_word(self, player: Player, reason: str) -> Tuple[bool, str, bool]:
        from stats import stats_manager
        # Check if player has a Shield equipped in inventory!
        if stats_manager.consume_item(player.user_id, "shield"):
            msg = (
                f"🛡️ <b>Shield Activated!</b> Protected from penalty.\n"
                f"❌ ({reason}) — {player.name}, try again ({player.attempts_left} attempts left) — "
                f"{self.turn_timeout_seconds}s on the clock."
            )
            return False, msg, False

        player.attempts_left -= 1
        if player.attempts_left <= 0:
            player.is_eliminated = True
            self._advance_turn()
            msg = f"❌ {player.name} is out! 3 wrong attempts."
            return False, msg, True
        else:
            msg = (
                f"❌ Wrong! {reason} {player.name}, try again "
                f"({player.attempts_left} attempts left) — {self.turn_timeout_seconds} seconds on the clock."
            )
            return False, msg, False

    def use_hint(self, user_id: int) -> Tuple[bool, str]:
        """Uses a Hint power-up during the player's turn."""
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != user_id:
            return False, "⚠️ You can only use a hint during your active turn!"

        from stats import stats_manager
        if not stats_manager.consume_item(user_id, "hint"):
            return False, "❌ You don't have any 💡 Hints! Buy one in the shop using `/buy hint` (25 🪙)."

        target = self.target_letter or "A"
        hint_word = dictionary.get_hint_word(target, self.used_words)
        if hint_word:
            return True, f"💡 <b>Hint Clue:</b> Try a word like <b>'{hint_word[0]}...{hint_word[-1]}'</b> ({len(hint_word)} letters, e.g. <i>{hint_word}</i>)!"
        return True, f"💡 <b>Hint:</b> Look for common English words starting with <b>'{target}'</b>!"

    def use_swap(self, user_id: int) -> Tuple[bool, str]:
        """Uses a Letter Swap power-up during the player's turn."""
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != user_id:
            return False, "⚠️ You can only swap letters during your active turn!"

        from stats import stats_manager
        if not stats_manager.consume_item(user_id, "swap"):
            return False, "❌ You don't have any 🔄 Swaps! Buy one in the shop using `/buy swap` (35 🪙)."

        old_letter = self.target_letter or "A"
        new_letter = dictionary.get_easy_random_letter(old_letter)
        self.target_letter = new_letter

        return True, f"🔄 <b>Letter Swapped!</b> {current_player.name} swapped <b>'{old_letter}'</b> ➔ <b>'{new_letter}'</b>!\n👉 New required starting letter is <b>'{new_letter}'</b>!"

    def handle_timeout(self, user_id: int) -> Tuple[str, bool]:
        """Called when 20s turn timer expires."""
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != user_id:
            return "", False

        current_player.is_eliminated = True
        self._advance_turn()
        msg = f"❌ {current_player.name} is out! Didn't send a word within {self.turn_timeout_seconds} seconds."
        return msg, True

    def _advance_turn(self):
        active = self.get_active_players()
        if not active:
            return
        self.active_player_index = (self.active_player_index + 1) % len(active)
        next_p = self.get_current_player()
        if next_p:
            next_p.attempts_left = config.MAX_ATTEMPTS

    def check_winner(self) -> Optional[Player]:
        active = self.get_active_players()
        if self.is_solo:
            # Solo mode: game only ends when active players is 0
            if len(active) == 0:
                self.state = GameState.ENDED
            return None

        # Multiplayer mode: 1 player left = Winner!
        if len(active) == 1:
            self.state = GameState.ENDED
            return active[0]
        elif len(active) == 0:
            self.state = GameState.ENDED
            return None
        return None

    def cancel_timer(self):
        if self.timer_task and not self.timer_task.done():
            try:
                current = asyncio.current_task()
                if self.timer_task is not current:
                    self.timer_task.cancel()
            except Exception:
                pass
            self.timer_task = None

    def cancel_lobby_timer(self):
        if self.lobby_timer_task and not self.lobby_timer_task.done():
            try:
                current = asyncio.current_task()
                if self.lobby_timer_task is not current:
                    self.lobby_timer_task.cancel()
            except Exception:
                pass
            self.lobby_timer_task = None

    def end_game(self):
        self.state = GameState.ENDED
        self.cancel_timer()
        self.cancel_lobby_timer()


class GameManager:
    def __init__(self):
        self.games: Dict[int, WordchainGame] = {}

    def get_game(self, chat_id: int) -> Optional[WordchainGame]:
        return self.games.get(chat_id)

    def create_game(self, chat_id: int, host: Player) -> WordchainGame:
        if chat_id in self.games:
            self.games[chat_id].end_game()
        game = WordchainGame(chat_id, host)
        self.games[chat_id] = game
        return game

    def delete_game(self, chat_id: int):
        if chat_id in self.games:
            self.games[chat_id].end_game()
            del self.games[chat_id]
