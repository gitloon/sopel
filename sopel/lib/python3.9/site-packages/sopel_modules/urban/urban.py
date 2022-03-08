# coding=utf-8
# Copyright 2018 Rusty Bower
# Licensed under the Eiffel Forum License 2
import requests

from sopel.module import commands, example
from sopel.tools import get_sendable_message  # added in Sopel 6.6.2


def display(bot, term, data, num=1):
    try:
        definition = data['list'][num - 1]['definition']
    except IndexError:
        bot.reply("Requested definition does not exist. Try a lower number.")
        return

    # This guesswork nonsense can be replaced with `bot.say()`'s `trailing`
    # parameter when dropping support for Sopel <7.1
    msg, excess = get_sendable_message(
        '[urban] {term} - {definition}'.format(term=term, definition=definition),
        400,
    )
    if excess:
        msg += ' […]'

    bot.say(msg)


def get_definition(bot, term):
    data = None
    try:
        data = requests.get('https://api.urbandictionary.com/v0/define?term={term}'.format(term=term)).json()
        return data
    except Exception:
        raise


@commands('ud', 'urban')
@example('.urban fronking', '[urban] fronking - If [your name] is [Hunter] you are a [fronker].')
def urban(bot, trigger):
    if not trigger.group(2):
        term = num = None
    else:
        term, _, num = trigger.group(2).partition('/')

    if num:
        try:
            num = int(num)
        except ValueError:
            bot.reply("'{}' is not a valid definition number.".format(num))
            return

        if num < 1 or num > 10:
            bot.reply("Try a definition number in the range 1-10.")
            return

        term = term.strip()
    else:
        num = 1

    # Get data from API
    data = get_definition(bot, term)
    # Have the bot print the data
    if data:
        if 'list' in data.keys() and len(data['list']) > 0:
            display(bot, term, data, num)
        else:
            # No result; display error
            bot.reply("Sorry, no results.")


if __name__ == "__main__":
    from sopel.test_tools import run_example_tests
    run_example_tests(__file__)
