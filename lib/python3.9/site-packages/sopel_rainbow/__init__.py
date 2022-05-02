# coding=utf8
"""sopel-rainbow

A Sopel plugin to make things RAINBOW COLORED.
"""
from __future__ import unicode_literals, absolute_import, division, print_function

import itertools
import random
import unicodedata

from sopel import formatting, module
from sopel.config import types


# Remove when dropping support for Sopel < 7.1
if hasattr(formatting, 'plain'):
    clean = formatting.plain
else:
    clean = lambda t: t


class RainbowSection(types.StaticSection):
    order = types.ListAttribute('order', default=[4, 7, 8, 3, 12, 2, 6])
    """The order of color codes to use.

    Defaults to a standard ROYGBIV rainbow (assuming readers' clients use
    typical IRC color code mappings).
    """
    random_start = types.ValidatedAttribute('random_start', bool, default=False)
    """Whether to randomize the start color."""


def configure(config):
    config.define_section('rainbow', RainbowSection)
    config.rainbow.configure_setting(
        'rainbow',
        'Specify the order of IRC color codes to use in the "rainbow":'
    )
    config.rainbow.configure_setting(
        'random_start',
        'Randomize start position in the rainbow?'
    )


def setup(bot):
    bot.config.define_section('rainbow', RainbowSection)


@module.commands('rainbow')
def rainbow_cmd(bot, trigger):
    """Make text into a rainbow."""
    text = clean(trigger.group(2) or '').strip()

    if not text:
        bot.reply("I can't make a rainbow out of nothing!")
        return module.NOLIMIT

    colors = bot.config.rainbow.order
    color_cycle = itertools.cycle(colors)

    if bot.config.rainbow.random_start:
        for _ in range(len(colors)):
            next(color_cycle)

    bot.say(
        ''.join(
            char if unicodedata.category(char) == 'Zs'
            else formatting.color(char, next(color_cycle))
            for char in text
        )
    )
