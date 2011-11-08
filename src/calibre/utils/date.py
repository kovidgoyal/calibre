#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from datetime import datetime, time
from functools import partial

from dateutil.parser import parse
from dateutil.tz import tzlocal, tzutc

from calibre import strftime

class SafeLocalTimeZone(tzlocal):
    '''
    Assume DST was not in effect for historical dates, if DST
    data for the local timezone is not present in the operating system.
    '''

    def _isdst(self, dt):
        try:
            return tzlocal._isdst(self, dt)
        except ValueError:
            pass
        return False

def compute_locale_info_for_parse_date():
    try:
        dt = datetime.strptime('1/5/2000', "%x")
    except:
        try:
            dt = datetime.strptime('1/5/01', '%x')
        except:
            return False
    if dt.month == 5:
        return True
    return False

parse_date_day_first = compute_locale_info_for_parse_date()
utc_tz = _utc_tz = tzutc()
local_tz = _local_tz = SafeLocalTimeZone()

UNDEFINED_DATE = datetime(101,1,1, tzinfo=utc_tz)
DEFAULT_DATE = datetime(2000,1,1, tzinfo=utc_tz)

def is_date_undefined(qt_or_dt):
    d = qt_or_dt
    if d is None:
        return True
    if hasattr(d, 'toString'):
        d = datetime(d.year(), d.month(), d.day(), tzinfo=utc_tz)
    return d.year < UNDEFINED_DATE.year or (
            d.year == UNDEFINED_DATE.year and
            d.month == UNDEFINED_DATE.month and
            d.day == UNDEFINED_DATE.day)

def parse_date(date_string, assume_utc=False, as_utc=True, default=None):
    '''
    Parse a date/time string into a timezone aware datetime object. The timezone
    is always either UTC or the local timezone.

    :param assume_utc: If True and date_string does not specify a timezone,
    assume UTC, otherwise assume local timezone.

    :param as_utc: If True, return a UTC datetime

    :param default: Missing fields are filled in from default. If None, the
    current date is used.
    '''
    if not date_string:
        return UNDEFINED_DATE
    if default is None:
        func = datetime.utcnow if assume_utc else datetime.now
        default = func().replace(hour=0, minute=0, second=0, microsecond=0,
                tzinfo=_utc_tz if assume_utc else _local_tz)
    dt = parse(date_string, default=default, dayfirst=parse_date_day_first)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_utc_tz if assume_utc else _local_tz)
    return dt.astimezone(_utc_tz if as_utc else _local_tz)

def strptime(val, fmt, assume_utc=False, as_utc=True):
    dt = datetime.strptime(val, fmt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_utc_tz if assume_utc else _local_tz)
    return dt.astimezone(_utc_tz if as_utc else _local_tz)

def dt_factory(time_t, assume_utc=False, as_utc=True):
    dt = datetime(*(time_t[0:6]))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_utc_tz if assume_utc else _local_tz)
    return dt.astimezone(_utc_tz if as_utc else _local_tz)

def qt_to_dt(qdate_or_qdatetime, as_utc=True):
    from PyQt4.Qt import Qt
    o = qdate_or_qdatetime
    if hasattr(o, 'toUTC'):
        # QDateTime
        o = unicode(o.toUTC().toString(Qt.ISODate))
        return parse_date(o, assume_utc=True, as_utc=as_utc)
    dt = datetime(o.year(), o.month(), o.day()).replace(tzinfo=_local_tz)
    return dt.astimezone(_utc_tz if as_utc else _local_tz)

def fromtimestamp(ctime, as_utc=True):
    dt = datetime.utcfromtimestamp(ctime).replace(tzinfo=_utc_tz)
    if not as_utc:
        dt = dt.astimezone(_local_tz)
    return dt

def fromordinal(day, as_utc=True):
    return datetime.fromordinal(day).replace(
            tzinfo=_utc_tz if as_utc else _local_tz)

def isoformat(date_time, assume_utc=False, as_utc=True, sep='T'):
    if not hasattr(date_time, 'tzinfo'):
        return unicode(date_time.isoformat())
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=_utc_tz if assume_utc else
                _local_tz)
    date_time = date_time.astimezone(_utc_tz if as_utc else _local_tz)
    # str(sep) because isoformat barfs with unicode sep on python 2.x
    return unicode(date_time.isoformat(str(sep)))

def as_local_time(date_time, assume_utc=True):
    if not hasattr(date_time, 'tzinfo'):
        return date_time
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=_utc_tz if assume_utc else
                _local_tz)
    return date_time.astimezone(_local_tz)

def as_utc(date_time, assume_utc=True):
    if not hasattr(date_time, 'tzinfo'):
        return date_time
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=_utc_tz if assume_utc else
                _local_tz)
    return date_time.astimezone(_utc_tz)

def now():
    return datetime.now().replace(tzinfo=_local_tz)

def utcnow():
    return datetime.utcnow().replace(tzinfo=_utc_tz)

def utcfromtimestamp(stamp):
    try:
        return datetime.utcfromtimestamp(stamp).replace(tzinfo=_utc_tz)
    except ValueError:
        # Raised if stamp if out of range for the platforms gmtime function
        # We print the error for debugging, but otherwise ignore it
        import traceback
        traceback.print_exc()
        return utcnow()

def format_date(dt, format, assume_utc=False, as_utc=False):
    ''' Return a date formatted as a string using a subset of Qt's formatting codes '''
    if not format:
        format = 'dd MMM yyyy'

    if not isinstance(dt, datetime):
        dt = datetime.combine(dt, time())

    if hasattr(dt, 'tzinfo'):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_utc_tz if assume_utc else
                    _local_tz)
        dt = dt.astimezone(_utc_tz if as_utc else _local_tz)

    if format == 'iso':
        return isoformat(dt, assume_utc=assume_utc, as_utc=as_utc)

    ampm = 'ap' in format.lower()

    if dt == UNDEFINED_DATE:
        return ''

    strf = partial(strftime, t=dt.timetuple())

    def format_hour(hr):
        l = len(hr)
        h = dt.hour
        if ampm:
            h = h%12
        if l == 1: return '%d'%h
        return '%02d'%h

    def format_minute(min):
        l = len(min)
        if l == 1: return '%d'%dt.minute
        return '%02d'%dt.minute

    def format_second(min):
        l = len(min)
        if l == 1: return '%d'%dt.second
        return '%02d'%dt.second

    def format_ampm(ap):
        res = strf('%p')
        if ap == 'AP':
            return res
        return res.lower()

    def format_day(dy):
        l = len(dy)
        if l == 1: return '%d'%dt.day
        if l == 2: return '%02d'%dt.day
        if l == 3: return strf('%a')
        return strf('%A')

    def format_month(mo):
        l = len(mo)
        if l == 1: return '%d'%dt.month
        if l == 2: return '%02d'%dt.month
        if l == 3: return strf('%b')
        return strf('%B')

    def format_year(yr):
        if len(yr) == 2: return '%02d'%(dt.year % 100)
        return '%04d'%dt.year

    function_index = {
            'd': format_day,
            'M': format_month,
            'y': format_year,
            'h': format_hour,
            'm': format_minute,
            's': format_second,
            'a': format_ampm,
            'A': format_ampm,
        }
    def repl_func(mo):
        s = mo.group(0)
        if s is None:
            return ''
        return function_index[s[0]](s)

    return re.sub(
        '(s{1,2})|(m{1,2})|(h{1,2})|(ap)|(AP)|(d{1,4}|M{1,4}|(?:yyyy|yy))',
        repl_func, format)

def clean_date_for_sort(dt, format):
    ''' Return a date formatted as a string using a subset of Qt's formatting codes '''
    if not format:
        format = 'yyMd'

    if not isinstance(dt, datetime):
        dt = datetime.combine(dt, time())

    if hasattr(dt, 'tzinfo'):
        if dt.tzinfo is not None:
            dt = as_utc(dt)

    if format == 'iso':
        format = 'yyMdhms'

    tt = {'year':UNDEFINED_DATE.year, 'mon':UNDEFINED_DATE.month,
          'day':UNDEFINED_DATE.day, 'hour':UNDEFINED_DATE.hour,
          'min':UNDEFINED_DATE.minute, 'sec':UNDEFINED_DATE.second}

    def has_hour(tt, hr):
        tt['hour'] = dt.hour
        return ''

    def has_minute(tt, min):
        tt['min'] = dt.minute
        return ''

    def has_second(tt, min):
        tt['sec'] = dt.second
        return ''

    def has_day(tt, dy):
        tt['day'] = dt.day
        return ''

    def has_month(tt, mo):
        tt['mon'] = dt.month
        return ''

    def has_year(tt, yr):
        tt['year'] = dt.year
        return ''

    function_index = {
            'd': has_day,
            'M': has_month,
            'y': has_year,
            'h': has_hour,
            'm': has_minute,
            's': has_second
        }
    def repl_func(mo):
        s = mo.group(0)
        if s is None:
            return ''
        return function_index[s[0]](tt, s)

    re.sub(
        '(s{1,2})|(m{1,2})|(h{1,2})|(d{1,4}|M{1,4}|(?:yyyy|yy))',
        repl_func, format)

    return datetime(tt['year'], tt['mon'], tt['day'], tt['hour'], tt['min'], tt['sec'])

def replace_months(datestr, clang):
    # Replace months by english equivalent for parse_date
    frtoen = {
        u'[jJ]anvier': u'jan',
        u'[fF].vrier': u'feb',
        u'[mM]ars': u'mar',
        u'[aA]vril': u'apr',
        u'[mM]ai': u'may',
        u'[jJ]uin': u'jun',
        u'[jJ]uillet': u'jul',
        u'[aA]o.t': u'aug',
        u'[sS]eptembre': u'sep',
        u'[Oo]ctobre': u'oct',
        u'[nN]ovembre': u'nov',
        u'[dD].cembre': u'dec' }
    detoen = {
        u'[jJ]anuar': u'jan',
        u'[fF]ebruar': u'feb',
        u'[mM].rz': u'mar',
        u'[aA]pril': u'apr',
        u'[mM]ai': u'may',
        u'[jJ]uni': u'jun',
        u'[jJ]uli': u'jul',
        u'[aA]ugust': u'aug',
        u'[sS]eptember': u'sep',
        u'[Oo]ktober': u'oct',
        u'[nN]ovember': u'nov',
        u'[dD]ezember': u'dec' }

    if clang == 'fr':
        dictoen = frtoen
    elif clang == 'de':
        dictoen = detoen
    else:
        return datestr

    for k in dictoen.iterkeys():
        tmp = re.sub(k, dictoen[k], datestr)
        if tmp != datestr: break
    return tmp

