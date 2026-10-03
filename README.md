# 🎮 Wordchain Advanced Telegram Game Bot

A premium, highly engaging multiplayer **Wordchain** game bot for Telegram group chats with a complete **In-Game Economy, Power-Ups Shop, Player Gamer Cards & Global Leaderboard**.

---

## 🕹️ Game Overview

Players take turns submitting valid English words where each new word starts with the **last letter** of the previous word.

**Example:**
`TIGER` ➔ `RABBIT` ➔ `TREE` ➔ `ELEPHANT` ➔ `TENT`...

---

## 🌟 Advanced & Unique Features

### 1. 🪙 In-Game Economy & Big Word Bonus
- 🎁 **50 Welcome Coins** for every player!
- 💰 **+5 Coins** for every valid word played.
- 🔥 **+15 Coins (Big Word Bonus)** for playing words with 7+ letters (e.g. `BEAUTIFUL`, `ELEPHANT`).
- 🏆 **+50 Coins** awarded to the match winner!

### 2. 🎒 Power-Ups Shop (`/shop`, `/buy`)
Players can spend coins to buy in-game perks:
- 🛡️ **Shield** (30 🪙): Automatically protects against 1 wrong word or typo (doesn't consume an attempt!).
- ⏱️ **Time Boost** (20 🪙): Adds +10 extra seconds to your turn timer (`/timeboost`).
- 💡 **Word Hint** (25 🪙): Reveals a valid word suggestion for the current target letter (`/hint`).
- 🔄 **Letter Swap** (35 🪙): Swaps tough target letters (e.g. X, Q, Z) for an easy one (`/swap`).

### 3. 👤 Player Profile & Gamer Cards (`/profile` or `/me`)
Displays:
- 🎖️ **Player Titles**: *Word Novice ➔ Vocabulary Knight ➔ Word Master ➔ Lexicon Champion ➔ Word Legend*
- 🪙 Wallet Coins balance
- 🏆 Total Wins & Matches Played
- 📈 Win Rate (%)
- 🔥 Current & Best Winning Streaks
- 🔤 Longest Word Ever Played
- 🎒 Inventory counts for Shields, Boosts, Hints, and Swaps

### 4. 🏆 Global Leaderboard (`/leaderboard` or `/top`)
- Shows the Top 10 Ranked players globally sorted by Wins & Points with medals (🥇, 🥈, 🥉).

### 5. 👑 Winner Auto-Pin & Replace
- When a player wins, the celebratory card is automatically pinned in the group chat.
- When a new match concludes, the previous winner pin is automatically unpinned and replaced with the new champion!

---

## 📋 Commands Reference

| Command | Description |
|---|---|
| `/wordchain` | Opens a new Wordchain lobby (2-min timer or `/startgame`) |
| `/join` | Joins an open Wordchain lobby |
| `/startgame` | Starts match immediately without waiting |
| `/cancelwordchain` | Cancels the active match or lobby |
| `/profile` / `/me` | Shows your Gamer Card, Titles, Coins & Inventory |
| `/leaderboard` / `/top`| Displays the Global Top 10 leaderboard |
| `/shop` | Shows power-ups catalogue and prices |
| `/buy <item>` | Buy power-ups (`/buy shield`, `/buy hint`, `/buy swap`, `/buy time_boost`) |
| `/hint` | (During match) Use 1 Hint from inventory |
| `/swap` | (During match) Swap target letter to an easy one |
| `/timeboost` | (During match) Add +10 seconds to your active timer |

---

## 🧪 Testing

```bash
python test_game.py
python test_bot_flow.py
```
