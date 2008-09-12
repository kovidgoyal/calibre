"""Utility functions and date/time routines.

 Copyright 2002-2006 John J Lee <jjl@pobox.com>

This code is free software; you can redistribute it and/or modify it
under the terms of the BSD or ZPL 2.1 licenses (see the file
COPYING.txt included with the distribution).

"""

import re, string, time, warnings

def deprecation(message):
    warnings.warn(message, DeprecationWarning, stacklevel=3)
def hide_deprecations():
    warnings.filterwarnings('ignore', category=DeprecationWarning)
def reset_deprecations():
    warnings.filterwarnings('default', category=DeprecationWarning)


def isstringlike(x):
    try: x+""
    except: return False
    else: return True

## def caller():
##     try:
##         raise SyntaxError
##     except:
##         import sys
##     return sys.exc_traceback.tb_frame.f_back.f_back.f_code.co_name


from calendar import timegm

# Date/time conversion routines for formats used by the HTTP protocol.

EPOCH = 1970
def my_timegm(tt):
    year, month, mday, hour, min, sec = tt[:6]
    if ((year >= EPOCH) and (1 <= month <= 12) and (1 <= mday <= 31) and
        (0 <= hour <= 24) and (0 <= min <= 59) and (0 <= sec <= 61)):
        return timegm(tt)
    else:
        return None

days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
months_lower = []
for month in months: months_lower.append(month.lower())


def time2isoz(t=None):
    """Return a string representing time in seconds since epoch, t.

    If the function is called without an argument, it will use the current
    time.

    The format of the returned string is like "YYYY-MM-DD hh:mm:ssZ",
    representing Universal Time (UTC, aka GMT).  An example of this format is:

    1994-11-24 08:49:37Z

    """
    if t is None: t = time.time()
    year, mon, mday, hour, min, sec = time.gmtime(t)[:6]
    return "%04d-%02d-%02d %02d:%02d:%02dZ" % (
        year, mon, mday, hour, min, sec)

def time2netscape(t=None):
    """Return a string representing time in seconds since epoch, t.

    If the function is called without an argument, it will use the current
    time.

    The format of the returned string is like this:

    Wed, DD-Mon-YYYY HH:MM:SS GMT

    """
    if t is None: t = time.time()
    year, mon, mday, hour, min, sec, wday = time.gmtime(t)[:7]
    return "%s %02d-%s-%04d %02d:%02d:%02d GMT" % (
        days[wday], mday, months[mon-1], year, hour, min, sec)


UTC_ZONES = {"GMT": None, "UTC": None, "UT": None, "Z": None}

timezone_re = re.compile(r"^([-+])?(\d\d?):?(\d\d)?$")
def offset_from_tz_string(tz):
    offset = None
    if UTC_ZONES.has_key(tz):
        offset = 0
    else:
        m = timezone_re.search(tz)
        if m:
            offset = 3600 * int(m.group(2))
            if m.group(3):
                offset = offset + 60 * int(m.group(3))
            if m.group(1) == '-':
                offset = -offset
    return offset

def _str2time(day, mon, yr, hr, min, sec, tz):
    # translate month name to number
    # month numbers start with 1 (January)
    try:
        mon = months_lower.index(mon.lower())+1
    except ValueError:
        # maybe it's already a number
        try:
            imon = int(mon)
        except ValueError:
            return None
        if 1 <= imon <= 12:
            mon = imon
        else:
            return None

    # make sure clock elements are defined
    if hr is None: hr = 0
    if min is None: min = 0
    if sec is None: sec = 0

    yr = int(yr)
    day = int(day)
    hr = int(hr)
    min = int(min)
    sec = int(sec)

    if yr < 1000:
        # find "obvious" year
        cur_yr = time.localtime(time.time())[0]
        m = cur_yr % 100
        tmp = yr
        yr = yr + cur_yr - m
        m = m - tmp
        if abs(m) > 50:
            if m > 0: yr = yr + 100
            else: yr = yr - 100

    # convert UTC time tuple to seconds since epoch (not timezone-adjusted)
    t = my_timegm((yr, mon, day, hr, min, sec, tz))

    if t is not None:
        # adjust time using timezone string, to get absolute time since epoch
        if tz is None:
            tz = "UTC"
        tz = tz.upper()
        offset = offset_from_tz_string(tz)
        if offset is None:
            return None
        t = t - offset

    return t


strict_re = re.compile(r"^[SMTWF][a-z][a-z], (\d\d) ([JFMASOND][a-z][a-z]) (\d\d\d\d) (\d\d):(\d\d):(\d\d) GMT$")
wkday_re = re.compile(
    r"^(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)[a-z]*,?\s*", re.I)
loose_http_re = re.compile(
    r"""^
    (\d\d?)            # day
       (?:\s+|[-\/])
    (\w+)              # month
        (?:\s+|[-\/])
    (\d+)              # year
    (?:
          (?:\s+|:)    # separator before clock
       (\d\d?):(\d\d)  # hour:min
       (?::(\d\d))?    # optional seconds
    )?                 # optional clock
       \s*
    ([-+]?\d{2,4}|(?![APap][Mm]\b)[A-Za-z]+)? # timezone
       \s*
    (?:\(\w+\))?       # ASCII representation of timezone in parens.
       \s*$""", re.X)
def http2time(text):
    """Returns time in seconds since epoch of time represented by a string.

    Return value is an integer.

    None is returned if the format of str is unrecognized, the time is outside
    the representable range, or the timezone string is not recognized.  If the
    string contains no timezone, UTC is assumed.

    The timezone in the string may be numerical (like "-0800" or "+0100") or a
    string timezone (like "UTC", "GMT", "BST" or "EST").  Currently, only the
    timezone strings equivalent to UTC (zero offset) are known to the function.

    The function loosely parses the following formats:

    Wed, 09 Feb 1994 22:23:32 GMT       -- HTTP format
    Tuesday, 08-Feb-94 14:15:29 GMT     -- old rfc850 HTTP format
    Tuesday, 08-Feb-1994 14:15:29 GMT   -- broken rfc850 HTTP format
    09 Feb 1994 22:23:32 GMT            -- HTTP format (no weekday)
    08-Feb-94 14:15:29 GMT              -- rfc850 format (no weekday)
    08-Feb-1994 14:15:29 GMT            -- broken rfc850 format (no weekday)

    The parser ignores leading and trailing whitespace.  The time may be
    absent.

    If the year is given with only 2 digits, the function will select the
    century that makes the year closest to the current date.

    """
    # fast exit for strictly conforming string
    m = strict_re.search(text)
    if m:
        g = m.groups()
        mon = months_lower.index(g[1].lower()) + 1
        tt = (int(g[2]), mon, int(g[0]),
              int(g[3]), int(g[4]), float(g[5]))
        return my_timegm(tt)

    # No, we need some messy parsing...

    # clean up
    text = text.lstrip()
    text = wkday_re.sub("", text, 1)  # Useless weekday

    # tz is time zone specifier string
    day, mon, yr, hr, min, sec, tz = [None]*7

    # loose regexp parse
    m = loose_http_re.search(text)
    if m is not None:
        day, mon, yr, hr, min, sec, tz = m.groups()
    else:
        return None  # bad format

    return _str2time(day, mon, yr, hr, min, sec, tz)


iso_re = re.compile(
    """^
    (\d{4})              # year
       [-\/]?
    (\d\d?)              # numerical month
       [-\/]?
    (\d\d?)              # day
   (?:
         (?:\s+|[-:Tt])  # separator before clock
      (\d\d?):?(\d\d)    # hour:min
      (?::?(\d\d(?:\.\d*)?))?  # optional seconds (and fractional)
   )?                    # optional clock
      \s*
   ([-+]?\d\d?:?(:?\d\d)?
    |Z|z)?               # timezone  (Z is "zero meridian", i.e. GMT)
      \s*$""", re.X)
def iso2time(text):
    """
    As for http2time, but parses the ISO 8601 formats:

    1994-02-03 14:15:29 -0100    -- ISO 8601 format
    1994-02-03 14:15:29          -- zone is optional
    1994-02-03                   -- only date
    1994-02-03T14:15:29          -- Use T as separator
    19940203T141529Z             -- ISO 8601 compact format
    19940203                     -- only date

    """
    # clean up
    text = text.lstrip()

    # tz is time zone specifier string
    day, mon, yr, hr, min, sec, tz = [None]*7

    # loose regexp parse
    m = iso_re.search(text)
    if m is not None:
        # XXX there's an extra bit of the timezone I'm ignoring here: is
        #   this the right thing to do?
        yr, mon, day, hr, min, sec, tz, _ = m.groups()
    else:
        return None  # bad format

    return _str2time(day, mon, yr, hr, min, sec, tz)
