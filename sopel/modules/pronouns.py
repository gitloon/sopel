"""
pronouns.py - Sopel Pronouns Plugin
Copyright © 2016, Elsie Powell
Licensed under the Eiffel Forum License 2.

https://sopel.chat
"""
from __future__ import generator_stop

import logging

import requests

from sopel import plugin
from sopel.config import types


LOGGER = logging.getLogger(__name__)


class PronounsSection(types.StaticSection):
    fetch_complete_list = types.BooleanAttribute('fetch_complete_list', default=True)
    """Whether to attempt fetching the complete list pronoun.is uses, at bot startup."""


def configure(settings):
    """
    | name | example | purpose |
    | ---- | ------- | ------- |
    | fetch_complete_list | True | Whether to attempt fetching the complete pronoun list from pronoun.is at startup. |
    """
    settings.define_section('pronouns', PronounsSection)
    settings.pronouns.configure_setting(
        'fetch_complete_list',
        'Fetch the current pronoun.is list at startup?')


def setup(bot):
    bot.config.define_section('pronouns', PronounsSection)

    # Copied from pronoun.is, leaving a *lot* out.
    # If ambiguous, the earlier one will be used.
    # This basic set is hard-coded to guarantee that the ten most(ish) common sets
    # will work, even if fetching the current pronoun.is set from GitHub fails.
    bot.memory['pronoun_sets'] = {
        'ze/hir': 'ze/hir/hir/hirs/hirself',
        'ze/zir': 'ze/zir/zir/zirs/zirself',
        'they/.../themselves': 'they/them/their/theirs/themselves',
        'they/.../themself': 'they/them/their/theirs/themself',
        'she/her': 'she/her/her/hers/herself',
        'he/him': 'he/him/his/his/himself',
        'xey/xem': 'xey/xem/xyr/xyrs/xemself',
        'sie/hir': 'sie/hir/hir/hirs/hirself',
        'it/it': 'it/it/its/its/itself',
        'ey/em': 'ey/em/eir/eirs/eirself',
    }

    if not bot.config.pronouns.fetch_complete_list:
        return

    # and now try to get the current one
    # who needs an API that might never exist?
    # (https://github.com/witch-house/pronoun.is/pull/96)
    try:
        r = requests.get(
            'https://github.com/witch-house/pronoun.is/raw/master/resources/pronouns.tab')
        r.raise_for_status()
    except requests.exceptions.RequestException:
        # don't do anything, just log the failure and use the hard-coded set
        LOGGER.exception("Couldn't fetch full pronouns list; using default set.")
        return

    fetched_sets = {}
    try:
        for line in r.text.splitlines():
            split_set = line.split('\t')
            short = '{}/.../{}'.format(split_set[0], split_set[-1])
            fetched_sets[short] = '/'.join(split_set)
    except Exception:
        # don't care what failed, honestly, since we aren't trying to fix it
        LOGGER.exception("Couldn't parse fetched pronouns; using default set.")
        return

    bot.memory['pronoun_sets'] = fetched_sets


@plugin.command('pronouns')
@plugin.example('.pronouns Embolalia')
def pronouns(bot, trigger):
    """Show the pronouns for a given user, defaulting to the current user if left blank."""
    if not trigger.group(3):
        pronouns = bot.db.get_nick_value(trigger.nick, 'pronouns')
        if pronouns:
            say_pronouns(bot, trigger.nick, pronouns)
        else:
            bot.reply("I don't know your pronouns! You can set them with "
                      "{}setpronouns".format(bot.config.core.help_prefix))
    else:
        pronouns = bot.db.get_nick_value(trigger.group(3), 'pronouns')
        if pronouns:
            say_pronouns(bot, trigger.group(3), pronouns)
        elif trigger.group(3) == bot.nick:
            # You can stuff an entry into the database manually for your bot's
            # gender, but like… it's a bot.
            bot.say(
                "I am a bot. Beep boop. My pronouns are it/it/its/its/itself. "
                "See https://pronoun.is/it for examples."
            )
        else:
            bot.reply("I don't know {}'s pronouns. They can set them with "
                      "{}setpronouns".format(trigger.group(3),
                                             bot.config.core.help_prefix))


def say_pronouns(bot, nick, pronouns):
    for short, set_ in bot.memory['pronoun_sets'].items():
        if pronouns == set_:
            break
        short = pronouns

    bot.say("{}'s pronouns are {}. See https://pronoun.is/{} for "
            "examples.".format(nick, pronouns, short))


@plugin.command('setpronouns')
@plugin.example('.setpronouns fae/faer/faer/faers/faerself')
@plugin.example('.setpronouns they/them/theirs')
@plugin.example('.setpronouns they/them')
def set_pronouns(bot, trigger):
    """Set your pronouns."""
    pronouns = trigger.group(2)
    if not pronouns:
        bot.reply('What pronouns do you use?')
        return

    disambig = ''
    split_request = pronouns.split("/")
    if len(split_request) < 5:
        matching = []
        for known_set in bot.memory['pronoun_sets'].values():
            split_set = known_set.split("/")
            if known_set.startswith(pronouns + "/") or (
                len(split_request) == 3
                and (
                    (
                        # "they/.../themself"
                        split_request[1] == "..."
                        and split_request[0] == split_set[0]
                        and split_request[2] == split_set[4]
                    )
                    or (
                        # "they/them/theirs"
                        split_request[:2] == split_set[:2]
                        and split_request[2] == split_set[3]
                    )
                )
            ):
                matching.append(known_set)

        if not matching:
            bot.reply(
                "I'm sorry, I don't know those pronouns. "
                "You can give me a set I don't know by formatting it "
                "subject/object/possessive-determiner/possessive-pronoun/"
                "reflexive, as in: they/them/their/theirs/themselves"
            )
            return

        pronouns = matching.pop(0)
        if matching:
            disambig = " Or, if you meant one of these, please tell me: {}".format(
                ", ".join(matching[1:])
            )

    bot.db.set_nick_value(trigger.nick, 'pronouns', pronouns)
    bot.reply(
        "Thanks for telling me! I'll remember you use {}.{}".format(pronouns, disambig)
    )
