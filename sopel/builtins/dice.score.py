"""
dice.py - Sopel Dice Plugin (with Weekly High Score Scoreboard)

Original code Copyright 2010-2013, Dimitri "Tyrope" Molenaars, TyRope.nl
Additional modifications & scoreboard integration 2025.
Licensed under the Eiffel Forum License 2.

https://sopel.chat
"""
from __future__ import annotations

import operator
import random
import re
import time
from typing import TYPE_CHECKING, Optional, List, Tuple

from sopel import plugin
from sopel.tools.calculation import eval_equation

if TYPE_CHECKING:
    from sopel.bot import SopelWrapper
    from sopel.trigger import Trigger

MAX_DICE = 1000

# Number of seconds a high score remains valid (7 days)
WEEK_SECONDS = 7 * 24 * 60 * 60

# ---------------------------------------------------------------------------
# Scoreboard persistence helpers
# ---------------------------------------------------------------------------

def setup(bot):  # Sopel calls this if present
    """Initialize database objects for the dice weekly high score table.

    Table schema (SQLite by default):
        dice_highscores(
            channel TEXT NOT NULL,
            nick TEXT NOT NULL,
            score INTEGER NOT NULL,
            set_at INTEGER NOT NULL,  -- epoch seconds
            PRIMARY KEY(channel, nick)
        )
    """
    db = bot.db
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS dice_highscores (
            channel TEXT NOT NULL,
            nick TEXT NOT NULL,
            score INTEGER NOT NULL,
            set_at INTEGER NOT NULL,
            PRIMARY KEY(channel, nick)
        )
        """
    )


def _purge_expired(bot, now: Optional[int] = None) -> None:
    """Remove expired (older than 7 days) highscores."""
    if now is None:
        now = int(time.time())
    threshold = now - WEEK_SECONDS
    bot.db.execute("DELETE FROM dice_highscores WHERE set_at < ?", (threshold,))


def _update_highscore(bot, channel: str, nick: str, score: int, now: Optional[int] = None) -> Optional[int]:
    """Update a user's weekly high score for a channel if improved.

    Returns the previous best score (still valid) or None if none existed.
    """
    if now is None:
        now = int(time.time())
    _purge_expired(bot, now)
    row = bot.db.execute(
        "SELECT score, set_at FROM dice_highscores WHERE channel = ? AND nick = ?",
        (channel, nick),
    ).fetchone()
    prev_score: Optional[int] = None
    if row is not None:
        prev_score_val, set_at = row
        if set_at >= now - WEEK_SECONDS:
            prev_score = prev_score_val
    if prev_score is None or score > prev_score:
        bot.db.execute(
            "REPLACE INTO dice_highscores(channel, nick, score, set_at) VALUES (?,?,?,?)",
            (channel, nick, score, now),
        )
        return prev_score
    return prev_score


def _get_channel_highscores(bot, channel: str, limit: int = 10) -> List[Tuple[str, int, int]]:
    now = int(time.time())
    _purge_expired(bot, now)
    return bot.db.execute(
        """
        SELECT nick, score, set_at FROM dice_highscores
        WHERE channel = ? AND set_at >= ?
        ORDER BY score DESC, set_at ASC
        LIMIT ?
        """,
        (channel, now - WEEK_SECONDS, limit),
    ).fetchall()


def _format_age(seconds: int) -> str:
    days = seconds // 86400
    if days > 0:
        return f"{days}d"
    hours = seconds // 3600
    if hours > 0:
        return f"{hours}h"
    minutes = seconds // 60
    if minutes > 0:
        return f"{minutes}m"
    return f"{seconds}s"

# ---------------------------------------------------------------------------
# Dice implementation from original plugin
# ---------------------------------------------------------------------------

class DicePouch:
    def __init__(self, dice_count: int, dice_type: int) -> None:
        """Initialize dice pouch and roll the dice.

        :param dice_count: the number of dice in the pouch
        :param dice_type: how many faces each die has
        """
        self.num: int = dice_count
        self.type: int = dice_type
        self.dice: dict[int, int] = {}
        self.dropped: dict[int, int] = {}
        self.roll_dice()

    def roll_dice(self) -> None:
        """Roll all the dice in the pouch."""
        self.dice = {}
        self.dropped = {}
        for __ in range(self.num):
            number = random.randint(1, self.type)
            count = self.dice.setdefault(number, 0)
            self.dice[number] = count + 1

    def drop_lowest(self, n: int) -> None:
        """Drop ``n`` lowest dice from the result.

        :param n: the number of dice to drop
        """
        sorted_x = sorted(self.dice.items(), key=operator.itemgetter(0))
        for i, count in sorted_x:
            count = self.dice[i]
            if n == 0:
                break
            elif n < count:
                self.dice[i] = count - n
                self.dropped[i] = n
                break
            else:
                self.dice[i] = 0
                self.dropped[i] = count
                n = n - count
        for i, count in list(self.dropped.items()):
            if self.dice.get(i, 0) == 0 and i in self.dice:
                del self.dice[i]

    def get_simple_string(self) -> str:
        """Return the values of the dice like (2+2+2[+1+1])."""
        dice = self.dice.items()
        faces = ("+".join([str(face)] * times) for face, times in dice)
        dice_str = "+".join(faces)
        dropped_str = ""
        if self.dropped:
            dropped = self.dropped.items()
            dfaces = ("+".join([str(face)] * times) for face, times in dropped)
            dropped_str = "[+%s]" % ("+".join(dfaces),)
        return "(%s%s)" % (dice_str, dropped_str)

    def get_compressed_string(self) -> str:
        """Return the values of the dice like (3x2[+2x1])."""
        dice = self.dice.items()
        faces = ("%dx%d" % (times, face) for face, times in dice)
        dice_str = "+".join(faces)
        dropped_str = ""
        if self.dropped:
            dropped = self.dropped.items()
            dfaces = ("%dx%d" % (times, face) for face, times in dropped)
            dropped_str = "[+%s]" % ("+".join(dfaces),)
        return "(%s%s)" % (dice_str, dropped_str)

    def get_sum(self) -> int:
        """Get the sum of non-dropped dice."""
        result = 0
        for face, times in self.dice.items():
            result += face * times
        return result

    def get_number_of_faces(self) -> int:
        """Returns sum of different faces for dropped and not dropped dice.

        This can be used to estimate whether the result can be shown (in
        compressed form) in a reasonable amount of space.
        """
        return len(self.dice) + len(self.dropped)


class DiceError(Exception):
    """Custom base exception type."""


class InvalidDiceFacesError(DiceError):
    """Custom exception type for invalid number of die faces."""
    def __init__(self, faces: int):
        super().__init__(faces)

    @property
    def faces(self) -> int:
        return self.args[0]


class NegativeDiceCountError(DiceError):
    """Custom exception type for invalid numbers of dice."""
    def __init__(self, count: int):
        super().__init__(count)

    @property
    def count(self) -> int:
        return self.args[0]


class TooManyDiceError(DiceError):
    """Custom exception type for excessive numbers of dice."""
    def __init__(self, requested: int, available: int):
        super().__init__(requested, available)

    @property
    def available(self) -> int:
        return self.args[1]

    @property
    def requested(self) -> int:
        return self.args[0]


class UnableToDropDiceError(DiceError):
    """Custom exception type for failing to drop lowest N dice."""
    def __init__(self, dropped: int, total: int):
        super().__init__(dropped, total)

    @property
    def dropped(self) -> int:
        return self.args[0]

    @property
    def total(self) -> int:
        return self.args[1]


def _get_error_message(exc: DiceError) -> str:
    if isinstance(exc, InvalidDiceFacesError):
        return "I don't have any dice with {} sides.".format(exc.faces)
    if isinstance(exc, NegativeDiceCountError):
        return "I can't roll {} dice.".format(exc.count)
    if isinstance(exc, TooManyDiceError):
        return "I only have {}/{} dice.".format(exc.available, exc.requested)
    if isinstance(exc, UnableToDropDiceError):
        return "I can't drop the lowest {} of {} dice.".format(exc.dropped, exc.total)
    return "Unknown error rolling dice: %r" % exc


def _roll_dice(dice_match: re.Match[str]) -> DicePouch:
    dice_num = int(dice_match.group('dice_num') or 1)
    dice_type = int(dice_match.group('dice_type'))

    # Dice can't have zero or a negative number of sides.
    if dice_type <= 0:
        raise InvalidDiceFacesError(dice_type)
    # Can't roll a negative number of dice.
    if dice_num < 0:
        raise NegativeDiceCountError(dice_num)
    # Upper limit for dice should be at most a million.
    if dice_num > MAX_DICE:
        raise TooManyDiceError(dice_num, MAX_DICE)

    dice = DicePouch(dice_num, dice_type)

    if dice_match.group('drop_lowest'):
        drop = int(dice_match.group('drop_lowest'))
        if drop >= 0:
            dice.drop_lowest(drop)
        else:
            raise UnableToDropDiceError(drop, dice_num)

    return dice


@plugin.command('roll', 'dice', 'd')
@plugin.priority("medium")
@plugin.example(".roll", "No dice to roll.")
@plugin.output_prefix('[dice] ')
def roll(bot: SopelWrapper, trigger: Trigger) -> None:
    """Rolls dice and reports the result.

    The dice roll follows this format: XdY[vZ][+N][#COMMENT]

    X is the number of dice. Y is the number of faces in the dice. Z is the
    number of lowest dice to be dropped from the result. N is the constant to
    be applied to the end result. Comment is for easily noting the purpose.
    """
    dice_regexp = r"""
        (?P<dice_num>-?\d*)
        d
        (?P<dice_type>-?\d+)
        (v(?P<drop_lowest>-?\d+))?
    """

    if not trigger.group(2):
        bot.reply("No dice to roll.")
        return

    arg_str_raw = trigger.group(2).split("#", 1)[0].strip()
    arg_str = arg_str_raw.replace("%", "%%")
    arg_str = re.sub(
        dice_regexp, "%s", arg_str, flags=re.IGNORECASE | re.VERBOSE
    )

    dice_expressions = [
        match
        for match in re.finditer(dice_regexp, arg_str_raw, re.IGNORECASE | re.VERBOSE)
    ]

    if not dice_expressions:
        bot.reply("I couldn't find any valid dice expressions.")
        return

    try:
        dice = [_roll_dice(dice_expr) for dice_expr in dice_expressions]
    except DiceError as err:
        bot.reply(_get_error_message(err))
        return

    def _get_eval_str(dp: DicePouch) -> str:
        return "(%d)" % (dp.get_sum(),)

    def _get_pretty_str(dp: DicePouch) -> str:
        if dp.num <= 10:
            return dp.get_simple_string()
        elif dp.get_number_of_faces() <= 10:
            return dp.get_compressed_string()
        else:
            return "(...)"

    eval_str: str = arg_str % (tuple(map(_get_eval_str, dice)))
    pretty_str: str = arg_str % (tuple(map(_get_pretty_str, dice)))

    try:
        result = eval_equation(eval_str)
    except ValueError:
        bot.reply("You roll %s: %s = very big" % (arg_str_raw, pretty_str))
        return
    except (SyntaxError, eval_equation.Error):
        bot.reply(
            "I don't know how to process that. Are the dice as well as the algorithms correct?"
        )
        return

    try:
        bot.say("%s: %s = %d" % (arg_str_raw, pretty_str, result))
    except ValueError:
        bot.reply("I can't display a number that big. =(")
        return

    # Update weekly channel high score (channels only)
    if trigger.sender.startswith('#'):
        channel = trigger.sender.lower()
        nick = trigger.nick
        prev = _update_highscore(bot, channel, nick, result)
        if prev is None:
            bot.say(f"New weekly high score for {nick}: {result}!")
        elif result > prev:
            bot.say(f"{nick} beats their previous weekly high ({prev}) with {result}!")


@plugin.command('highscore', 'highscores', 'high')
@plugin.example('.highscore', user_help=True)
def highscores(bot: SopelWrapper, trigger: Trigger) -> None:
    """Show the top weekly dice roll scores for this channel."""
    if not trigger.sender.startswith('#'):
        bot.reply('High scores are channel-specific; use this in a channel.')
        return
    scores = _get_channel_highscores(bot, trigger.sender.lower())
    if not scores:
        bot.say('No weekly high scores yet. Roll some dice!')
        return
    now = int(time.time())
    parts = []
    for idx, (nick, score, set_at) in enumerate(scores, start=1):
        age = _format_age(now - set_at)
        parts.append(f"{idx}. {nick} {score} ({age})")
    bot.say('Weekly highs: ' + ' | '.join(parts))


@plugin.command('myhighscore', 'myhigh')
@plugin.example('.myhighscore', user_help=True)
def my_highscore(bot: SopelWrapper, trigger: Trigger) -> None:
    """Show your personal weekly high score in this channel."""
    if not trigger.sender.startswith('#'):
        bot.reply('High scores are channel-specific; use this in a channel.')
        return
    channel = trigger.sender.lower()
    now = int(time.time())
    _purge_expired(bot, now)
    row = bot.db.execute(
        'SELECT score, set_at FROM dice_highscores WHERE channel = ? AND nick = ?',
        (channel, trigger.nick),
    ).fetchone()
    if row is None or row[1] < now - WEEK_SECONDS:
        bot.say(f"{trigger.nick}: you don't have a weekly high score yet. Roll!")
        return
    score, set_at = row
    age = _format_age(now - set_at)
    bot.say(f"{trigger.nick}: your weekly high is {score} ({age} ago)")
