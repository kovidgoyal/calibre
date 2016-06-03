#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from datetime import datetime
from decimal import Decimal
import re

from dateutil.tz import tzlocal, tzutc, tzoffset

class SafeLocalTimeZone(tzlocal):

    def _isdst(self, dt):
        # This method in tzlocal raises ValueError if dt is out of range.
        # In such cases, just assume that dt is not DST.
        try:
            tzlocal._isdst(self, dt)
        except Exception:
            pass
        return False

utc_tz = tzutc()
local_tz = SafeLocalTimeZone()

_iso_pat = None

def iso_pat():
    global _iso_pat
    if _iso_pat is None:
        _iso_pat = re.compile(
        # Adapted from http://delete.me.uk/2005/03/iso8601.html
        r"""
        (?P<year>[0-9]{4})
        (
            (
                (-(?P<monthdash>[0-9]{1,2}))
                |
                (?P<month>[0-9]{2})
                (?!$)  # Don't allow YYYYMM
            )
            (
                (
                    (-(?P<daydash>[0-9]{1,2}))
                    |
                    (?P<day>[0-9]{2})
                )
                (
                    (
                        (?P<separator>[ T])
                        (?P<hour>[0-9]{2})
                        (:{0,1}(?P<minute>[0-9]{2})){0,1}
                        (
                            :{0,1}(?P<second>[0-9]{1,2})
                            ([.,](?P<second_fraction>[0-9]+)){0,1}
                        ){0,1}
                        (?P<timezone>
                            Z
                            |
                            (
                                (?P<tz_sign>[-+])
                                (?P<tz_hour>[0-9]{2})
                                :{0,1}
                                (?P<tz_minute>[0-9]{2}){0,1}
                            )
                        ){0,1}
                    ){0,1}
                )
            ){0,1}  # YYYY-MM
        ){0,1}  # YYYY only
        $
        """, re.VERBOSE)
    return _iso_pat

def to_int(d, key, default_to_zero=False, default=None, required=True):
    """Pull a value from the dict and convert to int

    :param default_to_zero: If the value is None or empty, treat it as zero
    :param default: If the value is missing in the dict use this default

    """
    value = d.get(key) or default
    if (value is None or value == '') and default_to_zero:
        return 0
    if value is None:
        if required:
            raise ValueError("Unable to read %s from %s" % (key, d))
    else:
        return int(value)

def parse_timezone(matches, default_timezone=utc_tz):
    """Parses ISO 8601 time zone specs into tzinfo offsets

    """

    if matches["timezone"] == "Z":
        return utc_tz
    # This isn't strictly correct, but it's common to encounter dates without
    # timezones so I'll assume the default (which defaults to UTC).
    # Addresses issue 4.
    if matches["timezone"] is None:
        return default_timezone
    sign = matches["tz_sign"]
    hours = to_int(matches, "tz_hour")
    minutes = to_int(matches, "tz_minute", default_to_zero=True)
    description = "%s%02d:%02d" % (sign, hours, minutes)
    if sign == "-":
        hours = -hours
        minutes = -minutes
    return tzoffset(description, 3600*hours + 60*minutes)

def parse_iso8601(date_string, assume_utc=True, as_utc=True):
    if isinstance(date_string, bytes):
        date_string = date_string.decode('ascii')
    m = iso_pat().match(date_string)
    if m is None:
        raise ValueError('%r is not a valid ISO8601 date' % date_string)
    groups = m.groupdict()
    tz = parse_timezone(groups, default_timezone=utc_tz if assume_utc else local_tz)
    groups["second_fraction"] = int(Decimal("0.%s" % (groups["second_fraction"] or 0)) * Decimal("1000000.0"))
    return datetime(
            year=to_int(groups, "year"),
            month=to_int(groups, "month", default=to_int(groups, "monthdash", required=False, default=1)),
            day=to_int(groups, "day", default=to_int(groups, "daydash", required=False, default=1)),
            hour=to_int(groups, "hour", default_to_zero=True),
            minute=to_int(groups, "minute", default_to_zero=True),
            second=to_int(groups, "second", default_to_zero=True),
            microsecond=groups["second_fraction"],
            tzinfo=tz,
    ).astimezone(utc_tz if as_utc else local_tz)

if __name__ == '__main__':
    import sys
    print(parse_iso8601(sys.argv[-1]))
