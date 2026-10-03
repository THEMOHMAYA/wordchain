"""
Dictionary module for Wordchain game.
Loads words from words.txt into an in-memory set for instantaneous O(1) lookups.
"""
import os
import random
from typing import Optional, Set

WORDS_FILE = os.path.join(os.path.dirname(__file__), "words.txt")

# Global in-memory word set
_WORD_SET: Set[str] = set()

# Curated starting words that are fun, common, and easy to chain from
STARTING_WORDS = [
    "apple", "tiger", "orange", "planet", "rocket", "guitar", "dragon",
    "castle", "falcon", "forest", "galaxy", "island", "jungle", "knight",
    "meteor", "nature", "ocean", "pirate", "riddle", "shadow", "temple",
    "unicorn", "valley", "wizard", "zephyr", "anchor", "bridge", "canyon",
    "diamond", "empire", "feather", "glacier", "horizon", "impact", "journey"
]


def load_dictionary() -> Set[str]:
    """Loads all valid English words into memory."""
    global _WORD_SET
    if _WORD_SET:
        return _WORD_SET

    if os.path.exists(WORDS_FILE):
        with open(WORDS_FILE, "r", encoding="utf-8") as f:
            _WORD_SET = {
                line.strip().lower()
                for line in f
                if line.strip() and len(line.strip()) >= 3 and line.strip().isalpha()
            }
    else:
        # Fallback to starting words and common words
        _WORD_SET = set(STARTING_WORDS)

    return _WORD_SET


def is_valid_word(word: str) -> bool:
    """
    Checks whether a given word is a valid English word.
    Must be at least 3 letters and contain only alphabets.
    """
    if not word or not isinstance(word, str):
        return False
    
    clean_word = word.strip().lower()
    if len(clean_word) < 3 or not clean_word.isalpha():
        return False

    words = load_dictionary()
    return clean_word in words


def get_random_starting_word() -> str:
    """Returns a fun, common starting word for the game."""
    return random.choice(STARTING_WORDS)


def get_chain_letters(word: str) -> tuple[str, str]:
    """Returns the (first_letter, last_letter) in lowercase."""
    clean = word.strip().lower()
    return clean[0], clean[-1]


def get_hint_word(target_letter: str, used_words: list[str]) -> Optional[str]:
    """Returns a valid English word starting with target_letter that hasn't been used yet."""
    words = load_dictionary()
    used_set = set(w.lower() for w in used_words)
    target = target_letter.lower()

    candidates = [
        w for w in words
        if w.startswith(target) and w not in used_set and 3 <= len(w) <= 8
    ]
    if candidates:
        return random.choice(candidates).capitalize()
    return None


EASY_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "L", "M", "N", "P", "R", "S", "T", "W"]


def get_easy_random_letter(exclude_letter: Optional[str] = None) -> str:
    """Picks a random easy letter for letter swap power-up."""
    choices = [ltr for ltr in EASY_LETTERS if ltr != (exclude_letter or "").upper()]
    return random.choice(choices if choices else EASY_LETTERS)


# Initialize on import
load_dictionary()
