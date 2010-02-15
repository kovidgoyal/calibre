#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from datetime import datetime

from dateutil.parser import parse
from dateutil.tz import tzlocal, tzutc

_utc_tz = tzutc()
_local_tz = tzlocal()

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
    dt = parse(date_string, default=default)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_utc_tz if assume_utc else _local_tz)
    dt = dt.astimezone(_utc_tz if as_utc else _local_tz)
    return dt

def isoformat(date_time, assume_utc=False, as_utc=True):
    if not hasattr(date_time, 'tzinfo'):
        return unicode(date_time.isoformat())
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=_utc_tz if assume_utc else
                _local_tz)
    date_time = date_time.astimezone(_utc_tz if as_utc else _local_tz)
    return unicode(date_time.isoformat())

def now():
    return datetime.now().replace(tzinfo=_local_tz)

def utcnow():
    return datetime.utcnow().replace(tzinfo=_utc_tz)

def utcfromtimestamp(stamp):
    return datetime.utcfromtimestamp(stamp).replace(tzinfo=_utc_tz)
