# coding=utf-8
"""Tools for getting and displaying the time."""
from __future__ import unicode_literals, absolute_import, print_function, division

import datetime

import pytz


def validate_timezone(zone):
    """Return an IETF timezone from the given IETF zone or common abbreviation.

    :param string zone: in a strict or a human-friendly format
    :return: the valid IETF timezone properly formatted
    :raise ValueError: when ``zone`` is not a valid timezone

    Prior to checking timezones, two transformations are made to make the zone
    names more human-friendly:

    1. the string is split on ``', '``, the pieces reversed, and then joined
       with ``/`` (*"New York, America"* becomes *"America/New York"*)
    2. Remaining spaces are replaced with ``_``
    3. Finally, strings longer than 4 characters are made title-case,
       and those 4 characters and shorter are made upper-case.

    This means ``new york, america`` becomes ``America/New_York``, and ``utc``
    becomes ``UTC``.

    This is the expected case-insensitivity behavior in the majority of cases.
    For example, ``edt`` and ``america/new_york`` will both return
    ``America/New_York``.

    If the zone is not valid, ``ValueError`` will be raised.
    """
    if zone is None:
        return None

    zone = '/'.join(reversed(zone.split(', '))).replace(' ', '_')
    if len(zone) <= 4:
        zone = zone.upper()
    else:
        zone = zone.title()
    if zone in pytz.all_timezones:
        return zone
    else:
        raise ValueError("Invalid time zone.")


def validate_format(tformat):
    """Returns the format, if valid, else None"""
    try:
        time = datetime.datetime.utcnow()
        time.strftime(tformat)
    except Exception:  # TODO: Be specific
        raise ValueError('Invalid time format')
    return tformat


def get_timezone(db=None, config=None, zone=None, nick=None, channel=None):
    """Find, and return, the approriate timezone

    Time zone is pulled in the following priority:

    1. ``zone``, if it is valid
    2. The timezone for the channel or nick ``zone`` in ``db`` if one is set
       and valid.
    3. The timezone for the nick ``nick`` in ``db``, if one is set and valid.
    4. The timezone for the channel ``channel`` in ``db``, if one is set and
       valid.
    5. The default timezone in ``config``, if one is set and valid.

    If ``db`` is not given, or given but not set up, steps 2 and 3 will be
    skipped. If ``config`` is not given, step 4 will be skipped. If no step
    yeilds a valid timezone, ``None`` is returned.

    Valid timezones are those present in the IANA Time Zone Database.

    .. seealso::

       The :func:`validate_timezone` function handles the validation and
       formatting of the timezone.

    """
    def _check(zone):
        try:
            return validate_timezone(zone)
        except ValueError:
            return None

    tz = None

    if zone:
        tz = _check(zone)
        if not tz:
            tz = _check(
                db.get_nick_or_channel_value(zone, 'timezone'))
    if not tz and nick:
        tz = _check(db.get_nick_value(nick, 'timezone'))
    if not tz and channel:
        tz = _check(db.get_channel_value(channel, 'timezone'))
    if not tz and config and config.core.default_timezone:
        tz = _check(config.core.default_timezone)
    return tz


def format_time(db=None, config=None, zone=None, nick=None, channel=None,
                time=None):
    """Return a formatted string of the given time in the given zone.

    ``time``, if given, should be a naive ``datetime.datetime`` object and will
    be treated as being in the UTC timezone. If it is not given, the current
    time will be used. If ``zone`` is given it must be present in the IANA Time
    Zone Database; ``get_timezone`` can be helpful for this. If ``zone`` is not
    given, UTC will be assumed.

    The format for the string is chosen in the following order:

    1. The format for the nick ``nick`` in ``db``, if one is set and valid.
    2. The format for the channel ``channel`` in ``db``, if one is set and
       valid.
    3. The default format in ``config``, if one is set and valid.
    4. ISO-8601

    If ``db`` is not given or is not set up, steps 1 and 2 are skipped. If
    config is not given, step 3 will be skipped.
    """
    tformat = None
    if db:
        if nick:
            tformat = db.get_nick_value(nick, 'time_format')
        if not tformat and channel:
            tformat = db.get_channel_value(channel, 'time_format')
    if not tformat and config and config.core.default_time_format:
        tformat = config.core.default_time_format
    if not tformat:
        tformat = '%Y-%m-%d - %T%Z'

    if not time:
        time = datetime.datetime.utcnow()

    if not zone:
        return time.strftime(tformat)
    else:
        if not time.tzinfo:
            utc = pytz.timezone('UTC')
            time = utc.localize(time)
        zone = pytz.timezone(zone)
        return time.astimezone(zone).strftime(tformat)


def seconds_to_human(secs):
    """Return a human readable string that is more readable than the built-in
    str(timedelta).

    Inspiration for function structure from:
    https://gist.github.com/Highstaker/280a09591df4a5fb1363b0bbaf858f0d

    Example outputs are::

        2 years, 1 month ago
        in 4 hours, 45 minutes
        in 8 days, 5 hours
        1 year ago

    """
    if isinstance(secs, datetime.timedelta):
        secs = secs.total_seconds()

    future = False
    if secs < 0:
        future = True

    secs = int(secs)
    secs = abs(secs)

    years = secs // 31536000
    months = (secs - years * 31536000) // 2635200
    days = (secs - years * 31536000 - months * 2635200) // 86400
    hours = (secs - years * 31536000 - months * 2635200 - days * 86400) // 3600
    minutes = (secs - years * 31536000 - months * 2635200 - days * 86400 - hours * 3600) // 60
    seconds = secs - years * 31536000 - months * 2635200 - days * 86400 - hours * 3600 - minutes * 60

    years_text = "year{}".format("s" if years != 1 else "")
    months_text = "month{}".format("s" if months != 1 else "")
    days_text = "day{}".format("s" if days != 1 else "")
    hours_text = "hour{}".format("s" if hours != 1 else "")
    minutes_text = "minute{}".format("s" if minutes != 1 else "")
    seconds_text = "second{}".format("s" if seconds != 1 else "")

    result = ", ".join(filter(lambda x: bool(x), [
        "{0} {1}".format(years, years_text) if years else "",
        "{0} {1}".format(months, months_text) if months else "",
        "{0} {1}".format(days, days_text) if days else "",
        "{0} {1}".format(hours, hours_text) if hours else "",
        "{0} {1}".format(minutes, minutes_text) if minutes else "",
        "{0} {1}".format(seconds, seconds_text) if seconds else ""
    ]))
    # Granularity
    result = ", ".join(result.split(", ")[:2])
    if future is False:
        result += " ago"
    else:
        result = "in " + result
    return result
