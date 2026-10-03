"""
Persistent player stats & economy management for Wordchain game.
Tracks:
- Wins, Losses, Matches Played, Winning Streaks, Best Streaks
- Coins Economy (Earning, Spending)
- Inventory of Power-ups (Shield, Time Boost, Hint, Letter Swap)
- Longest Word Played
- Pinned Messages per Group Chat
- Global & Group Leaderboards
"""
import json
import os
import random
from typing import Dict, Any, Optional, List, Tuple

STATS_FILE = os.path.join(os.path.dirname(__file__), "stats.json")

# Power-ups shop definition
SHOP_ITEMS = {
    "shield": {
        "name": "🛡️ Shield",
        "desc": "Protects against 1 wrong word (saves an attempt)",
        "cost": 30,
    },
    "time_boost": {
        "name": "⏱️ Time Boost",
        "desc": "Adds +10 seconds to your current turn timer",
        "cost": 20,
    },
    "hint": {
        "name": "💡 Word Hint",
        "desc": "Reveals a valid word starting with the target letter",
        "cost": 25,
    },
    "swap": {
        "name": "🔄 Letter Swap",
        "desc": "Changes the target letter to an easy random letter",
        "cost": 35,
    },
}


def get_title(wins: int) -> str:
    if wins >= 50:
        return "👑 Word Legend"
    elif wins >= 25:
        return "💎 Lexicon Champion"
    elif wins >= 10:
        return "🥇 Word Master"
    elif wins >= 3:
        return "🥈 Vocabulary Knight"
    else:
        return "🥉 Word Novice"


class StatsManager:
    def __init__(self, filepath: str = STATS_FILE):
        self.filepath = filepath
        self._data: Dict[str, Any] = self._load()
        if "players" not in self._data:
            self._data["players"] = {}
        if "pinned_messages" not in self._data:
            self._data["pinned_messages"] = {}

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "players" not in data and isinstance(data, dict):
                        return {"players": data, "pinned_messages": {}}
                    return data
            except Exception:
                return {"players": {}, "pinned_messages": {}}
        return {"players": {}, "pinned_messages": {}}

    def _save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving stats: {e}")

    def get_player_data(self, user_id: int, name: str = "Player") -> Dict[str, Any]:
        uid = str(user_id)
        players = self._data.setdefault("players", {})
        if uid not in players:
            players[uid] = {
                "name": name,
                "total_wins": 0,
                "matches_played": 0,
                "current_streak": 0,
                "best_streak": 0,
                "total_points": 0,
                "coins": 0,
                "inventory": {
                    "shield": 0,
                    "time_boost": 0,
                    "hint": 0,
                    "swap": 0,
                },
                "longest_word": "",
            }
        else:
            # Update latest display name if changed
            if name and name != "Player":
                players[uid]["name"] = name
            if "coins" not in players[uid]:
                players[uid]["coins"] = 0
            if "inventory" not in players[uid]:
                players[uid]["inventory"] = {"shield": 0, "time_boost": 0, "hint": 0, "swap": 0}
            if "matches_played" not in players[uid]:
                players[uid]["matches_played"] = players[uid].get("total_wins", 0)
            if "best_streak" not in players[uid]:
                players[uid]["best_streak"] = players[uid].get("current_streak", 0)
            if "longest_word" not in players[uid]:
                players[uid]["longest_word"] = ""
        return players[uid]

    def add_word_stats(self, user_id: int, word: str, name: str = "Player"):
        """Called on valid word submission. Updates total points & longest word."""
        data = self.get_player_data(user_id, name)
        data["total_points"] += 1

        if len(word) > len(data.get("longest_word", "")):
            data["longest_word"] = word.upper()

        self._save()

    def record_match_finish(self, winner_id: Optional[int], all_players: List[Tuple[int, str]]) -> Dict[str, Any]:
        """Updates matches, streaks, wins, and gives +30 coins to the winner only."""
        winner_data = None
        for uid, name in all_players:
            pdata = self.get_player_data(uid, name)
            pdata["matches_played"] += 1

            if winner_id and uid == winner_id:
                pdata["total_wins"] += 1
                pdata["current_streak"] += 1
                if pdata["current_streak"] > pdata.get("best_streak", 0):
                    pdata["best_streak"] = pdata["current_streak"]
                # Match winner reward: +30 Coins
                pdata["coins"] += 30
                winner_data = pdata
            else:
                pdata["current_streak"] = 0

        self._save()
        return winner_data or {}

    def buy_item(self, user_id: int, item_key: str, name: str = "Player") -> Tuple[bool, str]:
        if item_key not in SHOP_ITEMS:
            return False, f"Invalid item. Available items: `shield`, `time_boost`, `hint`, `swap`."

        item = SHOP_ITEMS[item_key]
        pdata = self.get_player_data(user_id, name)

        if pdata["coins"] < item["cost"]:
            return False, f"Not enough coins! You have **{pdata['coins']} 🪙**, but {item['name']} costs **{item['cost']} 🪙**."

        pdata["coins"] -= item["cost"]
        inv = pdata.setdefault("inventory", {})
        inv[item_key] = inv.get(item_key, 0) + 1
        self._save()

        return True, f"✅ Successfully purchased **{item['name']}**! You now have **{inv[item_key]}** in your inventory. (Balance: {pdata['coins']} 🪙)"

    def consume_item(self, user_id: int, item_key: str) -> bool:
        """Consumes 1 item from user's inventory if available."""
        uid = str(user_id)
        players = self._data.get("players", {})
        if uid in players:
            inv = players[uid].get("inventory", {})
            if inv.get(item_key, 0) > 0:
                inv[item_key] -= 1
                self._save()
                return True
        return False

    def get_inventory_count(self, user_id: int, item_key: str) -> int:
        uid = str(user_id)
        players = self._data.get("players", {})
        if uid in players:
            return players[uid].get("inventory", {}).get(item_key, 0)
        return 0

    def get_profile_card(self, user_id: int, name: str) -> str:
        pdata = self.get_player_data(user_id, name)
        title = get_title(pdata["total_wins"])
        win_rate = (
            f"{(pdata['total_wins'] / pdata['matches_played'] * 100):.1f}%"
            if pdata["matches_played"] > 0
            else "0.0%"
        )
        inv = pdata.get("inventory", {})
        longest = pdata.get("longest_word", "None")

        return (
            f"👤 <b>PLAYER PROFILE — {pdata['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎖️ <b>Title:</b> {title}\n"
            f"🪙 <b>Coins:</b> {pdata['coins']} 🪙\n\n"
            f"🏆 <b>Total Wins:</b> {pdata['total_wins']}\n"
            f"🎯 <b>Matches Played:</b> {pdata['matches_played']}\n"
            f"📈 <b>Win Rate:</b> {win_rate}\n"
            f"🔥 <b>Current Streak:</b> {pdata['current_streak']} (Best: {pdata.get('best_streak', pdata['current_streak'])})\n"
            f"⭐ <b>Lifetime Points:</b> {pdata['total_points']}\n"
            f"🔤 <b>Longest Word:</b> {longest}\n\n"
            f"🎒 <b>Inventory Power-ups:</b>\n"
            f"🛡️ Shields: <b>{inv.get('shield', 0)}</b> | ⏱️ Time Boosts: <b>{inv.get('time_boost', 0)}</b>\n"
            f"💡 Hints: <b>{inv.get('hint', 0)}</b> | 🔄 Swaps: <b>{inv.get('swap', 0)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛒 <i>Use /shop to buy power-ups with coins!</i>"
        )

    def get_leaderboard_text(self) -> str:
        players = list(self._data.get("players", {}).values())
        if not players:
            return "📊 <b>Wordchain Leaderboard</b>\n\nNo matches recorded yet. Start a match with /wordchain!"

        # Sort by total_wins desc, then total_points desc
        players.sort(key=lambda p: (p.get("total_wins", 0), p.get("total_points", 0)), reverse=True)
        top_players = players[:10]

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        lines = []
        for i, p in enumerate(top_players):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            pname = p.get("name", "Player")
            wins = p.get("total_wins", 0)
            pts = p.get("total_points", 0)
            coins = p.get("coins", 0)
            lines.append(f"{medal} <b>{pname}</b> — 🏆 {wins} Wins | ⭐ {pts} Pts | 🪙 {coins}")

        return (
            "🏆 <b>WORDCHAIN GLOBAL LEADERBOARD</b> 🏆\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(lines)
            + "\n━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Play matches to climb the ranks and earn coins!</i>"
        )

    def get_shop_text(self, user_id: int, name: str) -> str:
        pdata = self.get_player_data(user_id, name)
        inv = pdata.get("inventory", {})

        return (
            f"🛒 <b>WORDCHAIN POWER-UP SHOP</b>\n"
            f"Your Wallet: <b>{pdata['coins']} 🪙</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"1. 🛡️ <b>Shield</b> (30 🪙)\n"
            f"   <i>Auto-protects you from 1 wrong word or typo!</i>\n"
            f"   Owned: {inv.get('shield', 0)} | Buy: <code>/buy shield</code>\n\n"
            f"2. ⏱️ <b>Time Boost</b> (20 🪙)\n"
            f"   <i>Adds +10 seconds to your active turn timer!</i>\n"
            f"   Owned: {inv.get('time_boost', 0)} | Buy: <code>/buy time_boost</code>\n\n"
            f"3. 💡 <b>Word Hint</b> (25 🪙)\n"
            f"   <i>Reveals a valid word suggestion when you're stuck!</i>\n"
            f"   Owned: {inv.get('hint', 0)} | Buy: <code>/buy hint</code>\n\n"
            f"4. 🔄 <b>Letter Swap</b> (35 🪙)\n"
            f"   <i>Swaps tough target letters (X, Q, Z) for an easy one!</i>\n"
            f"   Owned: {inv.get('swap', 0)} | Buy: <code>/buy swap</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>How to use during game: Type /hint, /swap, or /timeboost on your turn!</i>"
        )

    def get_last_pinned(self, chat_id: int) -> Optional[int]:
        return self._data.setdefault("pinned_messages", {}).get(str(chat_id))

    def set_last_pinned(self, chat_id: int, message_id: int):
        self._data.setdefault("pinned_messages", {})[str(chat_id)] = message_id
        self._save()


stats_manager = StatsManager()
