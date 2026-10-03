"""
Wordchain Telegram Game Bot.
Replicates the core gameplay of @im_mimibot with advanced unique features:
- Coins Economy & In-Game Shop (/shop, /buy)
- Power-Ups: 🛡️ Shield, ⏱️ Time Boost, 💡 Hint, 🔄 Letter Swap (/hint, /swap, /timeboost)
- Player Profiles & Gamer Cards (/profile, /me)
- Global Leaderboard (/leaderboard, /top)
- Winner Auto-Pin & Replace system
- Length-Based Coin Bonuses (7+ letter big words)
"""
import asyncio
import logging
import sys
from typing import Optional

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from game import GameManager, GameState, Player, WordchainGame
from stats import stats_manager, get_title

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("WordchainBot")

game_manager = GameManager()


# -------------------------------------------------------------
# Turn Prompts and Helpers
# -------------------------------------------------------------
def get_turn_prompt_text(game: WordchainGame) -> str:
    player = game.get_current_player()
    if not player:
        return ""
    if game.target_letter is None:
        return (
            f"✍️ {player.name}, your turn! Send any valid English word to start. "
            f"{game.turn_timeout_seconds} seconds on the clock."
        )
    return (
        f"✍️ {player.name}, your turn! Send a word starting with '{game.target_letter}'. "
        f"{game.turn_timeout_seconds} seconds on the clock."
    )


# -------------------------------------------------------------
# Async Timers
# -------------------------------------------------------------
async def schedule_turn_timer(app: Application, chat_id: int):
    game = game_manager.get_game(chat_id)
    if not game or game.state != GameState.PLAYING:
        return

    game.cancel_timer()
    current_player = game.get_current_player()
    if not current_player:
        return

    async def _timer_worker():
        try:
            await asyncio.sleep(game.turn_timeout_seconds)
            await handle_timeout_event(app, chat_id, current_player.user_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in turn timer: {e}")

    game.timer_task = asyncio.create_task(_timer_worker())


async def handle_timeout_event(app: Application, chat_id: int, user_id: int):
    game = game_manager.get_game(chat_id)
    if not game or game.state != GameState.PLAYING:
        return

    out_msg, is_elim = game.handle_timeout(user_id)
    if not out_msg:
        return

    # Announce timeout elimination
    await app.bot.send_message(chat_id=chat_id, text=out_msg)

    # Check winner / game over
    if game.is_solo:
        if len(game.get_active_players()) == 0:
            player = game.players[0]
            await app.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎮 <b>Solo Game Over!</b>\n\n"
                    f"⭐ Total points: <b>{player.score}</b>\n"
                    f"🔤 Chain length: <b>{len(game.used_words)} words</b>\n\n"
                    f"🔁 Play again? Use /wordchain"
                ),
                parse_mode=ParseMode.HTML,
            )
            game_manager.delete_game(chat_id)
            return

    winner = game.check_winner()
    if winner:
        await announce_winner(app, chat_id, game, winner)
        return
    elif len(game.get_active_players()) == 0:
        await app.bot.send_message(chat_id=chat_id, text="💀 All players are out! Game Over.")
        game_manager.delete_game(chat_id)
        return

    # Send next turn prompt
    next_prompt = get_turn_prompt_text(game)
    await app.bot.send_message(chat_id=chat_id, text=next_prompt)
    await schedule_turn_timer(app, chat_id)


async def schedule_lobby_timer(app: Application, chat_id: int):
    game = game_manager.get_game(chat_id)
    if not game or game.state != GameState.LOBBY:
        return

    async def _lobby_worker():
        try:
            # Wait 60s -> announce 60s left
            await asyncio.sleep(60)
            cur_game = game_manager.get_game(chat_id)
            if cur_game and cur_game.state == GameState.LOBBY:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text="⏰ 60 seconds left! Join using /join"
                )

            # Wait another 30s (total 90s) -> announce 30s left
            await asyncio.sleep(30)
            cur_game = game_manager.get_game(chat_id)
            if cur_game and cur_game.state == GameState.LOBBY:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text="⏰ 30 seconds left! Join using /join"
                )

            # Wait remaining 30s (total 120s) -> Start
            await asyncio.sleep(30)
            cur_game = game_manager.get_game(chat_id)
            if cur_game and cur_game.state == GameState.LOBBY:
                logger.info(f"Auto-starting lobby for chat {chat_id} with {len(cur_game.players)} players.")
                await start_game_flow(app, chat_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in lobby worker: {e}")

    game.lobby_timer_task = asyncio.create_task(_lobby_worker())


async def start_game_flow(app: Application, chat_id: int):
    try:
        game = game_manager.get_game(chat_id)
        if not game or game.state != GameState.LOBBY:
            return

        game.cancel_lobby_timer()
        success, err_msg = game.start_game()
        if not success:
            await app.bot.send_message(chat_id=chat_id, text=f"⚠️ Could not start: {err_msg}")
            return

        # Message 1: Turn Order
        turn_order_lines = [f"{i+1}. {p.name}" for i, p in enumerate(game.players)]
        turn_order_text = "🎮 Game starting! Turn order:\n" + "\n".join(turn_order_lines)
        await app.bot.send_message(chat_id=chat_id, text=turn_order_text)

        # Message 2: First Turn Prompt
        first_prompt = get_turn_prompt_text(game)
        await app.bot.send_message(chat_id=chat_id, text=first_prompt)

        # Launch turn timer
        await schedule_turn_timer(app, chat_id)
    except Exception as e:
        logger.exception(f"Exception in start_game_flow for chat {chat_id}: {e}")


async def announce_winner(app: Application, chat_id: int, game: WordchainGame, winner: Player):
    game.cancel_timer()
    all_p = [(p.user_id, p.name) for p in game.players]
    stats = stats_manager.record_match_finish(winner_id=winner.user_id, all_players=all_p)

    title = get_title(stats.get("total_wins", 1))

    winner_text = (
        f"🏆🎉 <b>{winner.name} wins the wordchain game!</b> 👑\n\n"
        f"🎖️ Title: <b>{title}</b>\n"
        f"⭐ Points gained: <b>{winner.score}</b>\n"
        f"🪙 Match Reward: <b>+30 Coins!</b> (Total: {stats.get('coins', 0)} 🪙)\n"
        f"🥇 Total wins: <b>{stats.get('total_wins', 1)}</b>\n"
        f"🔥 Current streak: <b>{stats.get('current_streak', 1)}</b>\n\n"
        f"🔁 Play again? Use /wordchain"
    )

    # 1. Unpin previous winner message if exists
    old_pin_id = stats_manager.get_last_pinned(chat_id)
    if old_pin_id:
        try:
            await app.bot.unpin_chat_message(chat_id=chat_id, message_id=old_pin_id)
        except Exception:
            pass

    # 2. Send new winner message
    win_msg = await app.bot.send_message(chat_id=chat_id, text=winner_text, parse_mode=ParseMode.HTML)

    # 3. Pin the new winner message
    try:
        await app.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=win_msg.message_id,
            disable_notification=True,
        )
        stats_manager.set_last_pinned(chat_id, win_msg.message_id)
    except Exception as e:
        logger.warning(f"Could not pin winner message in chat {chat_id}: {e}")

    game_manager.delete_game(chat_id)


# -------------------------------------------------------------
# Command Handlers
# -------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    text = (
        "🎮 <b>PLAY WORDCHAIN — ADVANCED EDITION</b>\n\n"
        "Start a game with /wordchain and use /join to enter before the lobby closes.\n\n"
        "<b>📖 How to play:</b>\n"
        "1. Players take turns sending English words starting with the last letter of the previous word.\n"
        "2. ⏱️ <b>20 seconds</b> on the clock per turn.\n"
        "3. ❌ <b>3 wrong attempts</b> and you are eliminated.\n"
        "4. 🏆 The last player remaining wins the match and earns +50 Coins!\n\n"
        "<b>✨ Advanced Features:</b>\n"
        "🪙 <b>Coins & Power-ups</b>: Earn coins for valid words and 7+ letter big words! Use /shop and /buy.\n"
        "💡 <b>In-Game Perks</b>: Use /hint, /swap, or /timeboost during your turn.\n"
        "👤 <b>Player Card</b>: Check /profile for your rank, streak, and stats.\n"
        "🏆 <b>Leaderboard</b>: Check /leaderboard for top global players.\n\n"
        "<b>Commands:</b>\n"
        "/wordchain — Start a lobby\n"
        "/join — Join an open lobby\n"
        "/startgame — Start game immediately\n"
        "/cancelwordchain — Cancel current game\n"
        "/profile — View your player card & coins\n"
        "/leaderboard — View global rankings\n"
        "/shop — Power-ups shop"
    )
    await msg.reply_text(text, parse_mode=ParseMode.HTML)


async def wordchain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if chat.type == "private":
        await msg.reply_text("⚠️ Wordchain is a multiplayer game! Please add me to a group chat to play.")
        return

    existing = game_manager.get_game(chat.id)
    if existing:
        if existing.state == GameState.LOBBY:
            await msg.reply_text("ℹ️ A lobby is already open in this group. Use /join to enter or /startgame to start!")
            return
        elif existing.state == GameState.PLAYING:
            await msg.reply_text("⚠️ A game is currently in progress! Use /cancelwordchain to stop it.")
            return

    host = Player(
        user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    # Ensure stats profile is registered
    stats_manager.get_player_data(user.id, host.name)
    game = game_manager.create_game(chat.id, host)

    lobby_text = (
        f"🎮 Wordchain lobby started by {host.name}!\n\n"
        f"Use /join to enter. Lobby closes in 2 minutes."
    )
    await msg.reply_text(lobby_text)

    # Schedule 60s, 30s warnings and auto-start
    await schedule_lobby_timer(context.application, chat.id)


async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    game = game_manager.get_game(chat.id)
    if not game or game.state != GameState.LOBBY:
        await msg.reply_text("⚠️ No open lobby found! Start one with /wordchain.")
        return

    player = Player(
        user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    stats_manager.get_player_data(user.id, player.name)
    success, reply_msg = game.add_player(player)
    await msg.reply_text(reply_msg)


async def startgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message

    game = game_manager.get_game(chat.id)
    if not game or game.state != GameState.LOBBY:
        await msg.reply_text("⚠️ No open lobby to start. Use /wordchain first!")
        return

    await start_game_flow(context.application, chat.id)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    game = game_manager.get_game(chat.id)
    if not game:
        await msg.reply_text("⚠️ No active Wordchain game or lobby to cancel.")
        return

    game_manager.delete_game(chat.id)
    await msg.reply_text(f"🛑 Wordchain game was cancelled by {user.first_name or 'a player'}.")


# -------------------------------------------------------------
# Economy, Profile, Shop & In-Game Power-Up Commands
# -------------------------------------------------------------
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    card_text = stats_manager.get_profile_card(user.id, user.first_name or "Player")
    await update.effective_message.reply_text(card_text, parse_mode=ParseMode.HTML)


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board_text = stats_manager.get_leaderboard_text()
    await update.effective_message.reply_text(board_text, parse_mode=ParseMode.HTML)


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    shop_text = stats_manager.get_shop_text(user.id, user.first_name or "Player")
    await update.effective_message.reply_text(shop_text, parse_mode=ParseMode.HTML)


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if not args:
        await update.effective_message.reply_text(
            "🛒 Usage: <code>/buy shield</code> | <code>/buy time_boost</code> | <code>/buy hint</code> | <code>/buy swap</code>\n"
            "View prices with /shop.",
            parse_mode=ParseMode.HTML,
        )
        return

    item_key = args[0].strip().lower()
    success, reply_msg = stats_manager.buy_item(user.id, item_key, user.first_name or "Player")
    await update.effective_message.reply_text(reply_msg, parse_mode=ParseMode.MARKDOWN)


async def hint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    game = game_manager.get_game(chat.id)
    if not game or game.state != GameState.PLAYING:
        await msg.reply_text("⚠️ No active game in progress.")
        return

    success, hint_text = game.use_hint(user.id)
    await msg.reply_text(hint_text, parse_mode=ParseMode.HTML)


async def swap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    game = game_manager.get_game(chat.id)
    if not game or game.state != GameState.PLAYING:
        await msg.reply_text("⚠️ No active game in progress.")
        return

    success, swap_text = game.use_swap(user.id)
    await msg.reply_text(swap_text, parse_mode=ParseMode.HTML)


async def timeboost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    game = game_manager.get_game(chat.id)
    if not game or game.state != GameState.PLAYING:
        await msg.reply_text("⚠️ No active game in progress.")
        return

    current_player = game.get_current_player()
    if not current_player or current_player.user_id != user.id:
        await msg.reply_text("⚠️ You can only use a time boost during your active turn!")
        return

    if not stats_manager.consume_item(user.id, "time_boost"):
        await msg.reply_text("❌ You don't have any ⏱️ Time Boosts! Buy one with `/buy time_boost` (20 🪙).")
        return

    # Reset/extend turn timer with +10 extra seconds
    game.cancel_timer()
    await msg.reply_text(f"⏱️ <b>Time Boost Activated!</b> +10 Extra seconds added for {current_player.name}!", parse_mode=ParseMode.HTML)

    async def _boosted_timer():
        try:
            await asyncio.sleep(game.turn_timeout_seconds + 10)
            await handle_timeout_event(context.application, chat.id, current_player.user_id)
        except asyncio.CancelledError:
            pass

    game.timer_task = asyncio.create_task(_boosted_timer())


# -------------------------------------------------------------
# In-Game Word Message Handler
# -------------------------------------------------------------
async def word_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if not msg or not msg.text:
        return

    game = game_manager.get_game(chat.id)
    if not game or game.state != GameState.PLAYING:
        return

    current_player = game.get_current_player()
    if not current_player:
        return

    # Check if message is from the active player
    if user.id != current_player.user_id:
        return

    raw_text = msg.text.strip()
    if raw_text.startswith("/"):
        return

    tokens = raw_text.split()
    if len(tokens) > 1:
        return

    candidate_word = tokens[0]

    # Process word attempt
    is_valid, reply_text, is_elim = game.process_word(user.id, candidate_word)

    if is_valid:
        # Cancel turn timer immediately
        game.cancel_timer()

        # Reply to user's word message (quotes the word)
        await msg.reply_text(reply_text)

        # Check winner (multiplayer)
        winner = game.check_winner()
        if winner:
            await announce_winner(context.application, chat.id, game, winner)
            return

        # Next turn prompt
        next_prompt = get_turn_prompt_text(game)
        await context.bot.send_message(chat_id=chat.id, text=next_prompt)
        await schedule_turn_timer(context.application, chat.id)

    else:
        # Invalid word attempt
        if is_elim:
            game.cancel_timer()
            # Send elimination message
            await context.bot.send_message(chat_id=chat.id, text=reply_text)

            # Check if solo
            if game.is_solo:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        f"🎮 <b>Solo Game Over!</b>\n\n"
                        f"⭐ Total points: <b>{current_player.score}</b>\n"
                        f"🔤 Chain length: <b>{len(game.used_words)} words</b>\n\n"
                        f"🔁 Play again? Use /wordchain"
                    ),
                    parse_mode=ParseMode.HTML,
                )
                game_manager.delete_game(chat.id)
                return

            winner = game.check_winner()
            if winner:
                await announce_winner(context.application, chat.id, game, winner)
                return
            elif len(game.get_active_players()) == 0:
                await context.bot.send_message(chat_id=chat.id, text="💀 All players are out! Game Over.")
                game_manager.delete_game(chat.id)
                return

            # Next turn prompt
            next_prompt = get_turn_prompt_text(game)
            await context.bot.send_message(chat_id=chat.id, text=next_prompt)
            await schedule_turn_timer(context.application, chat.id)
        else:
            # Player has attempts left (or Shield protected)
            await context.bot.send_message(chat_id=chat.id, text=reply_text, parse_mode=ParseMode.HTML)


# -------------------------------------------------------------
# Main Launcher
# -------------------------------------------------------------
def main():
    token = config.BOT_TOKEN
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("ERROR: BOT_TOKEN is not configured in .env file.")
        return

    print("Starting Wordchain Advanced Telegram Bot...")

    application = Application.builder().token(token).build()

    # Commands
    application.add_handler(CommandHandler(["start", "help", "rules"], start_command))
    application.add_handler(CommandHandler("wordchain", wordchain_command))
    application.add_handler(CommandHandler("join", join_command))
    application.add_handler(CommandHandler("startgame", startgame_command))
    application.add_handler(CommandHandler("cancelwordchain", cancel_command))

    # Economy & Stats Commands
    application.add_handler(CommandHandler(["profile", "me", "mystats"], profile_command))
    application.add_handler(CommandHandler(["leaderboard", "top"], leaderboard_command))
    application.add_handler(CommandHandler("shop", shop_command))
    application.add_handler(CommandHandler("buy", buy_command))

    # In-Game Power-up Commands
    application.add_handler(CommandHandler("hint", hint_command))
    application.add_handler(CommandHandler("swap", swap_command))
    application.add_handler(CommandHandler("timeboost", timeboost_command))

    # Word listener for gameplay
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, word_message_handler)
    )

    print("Wordchain Bot is running and ready!")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
