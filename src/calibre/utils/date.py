#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from datetime import datetime
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
    return unicode(date_time.isoformat(sep))

def now():
    return datetime.now().replace(tzinfo=_local_tz)

def utcnow():
    return datetime.utcnow().replace(tzinfo=_utc_tz)

def utcfromtimestamp(stamp):
    return datetime.utcfromtimestamp(stamp).replace(tzinfo=_utc_tz)

def format_date(dt, format, assume_utc=False, as_utc=False):
    ''' Return a date formatted as a string using a subset of Qt's formatting codes '''
    if not format:
        format = 'dd MMM yyyy'

    if hasattr(dt, 'tzinfo'):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_utc_tz if assume_utc else
                    _local_tz)
        dt = dt.astimezone(_utc_tz if as_utc else _local_tz)
    strf = partial(strftime, t=dt.timetuple())

    def format_day(mo):
        l = len(mo.group(0))
        if l == 1: return '%d'%dt.day
        if l == 2: return '%02d'%dt.day
        if l == 3: return strf('%a')
        return strf('%A')

    def format_month(mo):
        l = len(mo.group(0))
        if l == 1: return '%d'%dt.month
        if l == 2: return '%02d'%dt.month
        if l == 3: return strf('%b')
        return strf('%B')

    def format_year(mo):
        if len(mo.group(0)) == 2: return '%02d'%(dt.year % 100)
        return '%04d'%dt.year

    format = re.sub('d{1,4}', format_day, format)
    format = re.sub('M{1,4}', format_month, format)
    return re.sub('yyyy|yy', format_year, format)

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

