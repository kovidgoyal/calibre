#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from datetime import datetime

from dateutil.tz import tzlocal, tzutc, tzoffset

from calibre.constants import plugins
speedup, err = plugins['speedup']
if not speedup:
    raise RuntimeError(err)


class SafeLocalTimeZone(tzlocal):

    def _isdst(self, dt):
        # This method in tzlocal raises ValueError if dt is out of range (in
        # older versions of dateutil)
        # In such cases, just assume that dt is not DST.
        try:
            return super(SafeLocalTimeZone, self)._isdst(dt)
        except Exception:
            pass
        return False

    def _naive_is_dst(self, dt):
        # This method in tzlocal raises ValueError if dt is out of range (in
        # newer versions of dateutil)
        # In such cases, just assume that dt is not DST.
        try:
            return super(SafeLocalTimeZone, self)._naive_is_dst(dt)
        except Exception:
            pass
        return False


utc_tz = tzutc()
local_tz = SafeLocalTimeZone()
del tzutc, tzlocal
UNDEFINED_DATE = datetime(101,1,1, tzinfo=utc_tz)


def parse_iso8601(date_string, assume_utc=False, as_utc=True):
    if not date_string:
        return UNDEFINED_DATE
    dt, aware, tzseconds = speedup.parse_iso8601(date_string)
    tz = utc_tz if assume_utc else local_tz
    if aware:  # timezone was specified
        if tzseconds == 0:
            tz = utc_tz
        else:
            sign = '-' if tzseconds < 0 else '+'
            description = "%s%02d:%02d" % (sign, abs(tzseconds) // 3600, (abs(tzseconds) % 3600) // 60)
            tz = tzoffset(description, tzseconds)
    dt = dt.replace(tzinfo=tz)
    if as_utc and tz is utc_tz:
        return dt
    return dt.astimezone(utc_tz if as_utc else local_tz)


if __name__ == '__main__':
    import sys
    print(parse_iso8601(sys.argv[-1]))
