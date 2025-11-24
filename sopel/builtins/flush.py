"""
8ball.py - Ask the magic 8ball a question
Copyright 2013, Sander Brand http://brantje.com
Licensed under the Eiffel Forum License 2.
http://sopel.dfbta.net
"""
import sopel
import random
@sopel.module.commands('flush')
def ball(bot, trigger):
    """Flush what needs to be flushed... Usage: .flush <thing>"""
    symbol = trigger.group(2)
    messages = ["/!\/!\ FLUSH '{symbol}' /!\/!\\"]
    answer = random.randint(0,len(messages) - 1)
    bot.say(messages[answer]);
