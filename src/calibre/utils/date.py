#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from datetime import MAXYEAR, MINYEAR, datetime, timedelta
from datetime import time as dtime
from functools import partial

from calibre import strftime
from calibre.constants import ismacos, iswindows, preferred_encoding
from calibre.utils.iso8601 import UNDEFINED_DATE, local_tz, utc_tz
from calibre.utils.localization import lcdata
from polyglot.builtins import native_string_type

_utc_tz = utc_tz
_local_tz = local_tz

# When parsing ambiguous dates that could be either dd-MM Or MM-dd use the
# user's locale preferences
if iswindows:
    import ctypes
    LOCALE_SSHORTDATE, LOCALE_USER_DEFAULT = 0x1f, 0
    buf = ctypes.create_string_buffer(b'\0', 255)
    try:
        ctypes.windll.kernel32.GetLocaleInfoA(LOCALE_USER_DEFAULT, LOCALE_SSHORTDATE, buf, 255)
        parse_date_day_first = buf.value.index(b'd') < buf.value.index(b'M')
    except Exception:
        parse_date_day_first = False
    del ctypes, LOCALE_SSHORTDATE, buf, LOCALE_USER_DEFAULT
elif ismacos:
    try:
        from calibre_extensions.usbobserver import date_format
        date_fmt = date_format()
        parse_date_day_first = date_fmt.index('d') < date_fmt.index('M')
    except Exception:
        parse_date_day_first = False
else:
    try:
        def first_index(raw, queries):
            for q in queries:
                try:
                    return raw.index(native_string_type(q))
                except ValueError:
                    pass
            return -1

        import locale
        raw = locale.nl_langinfo(locale.D_FMT)
        parse_date_day_first = first_index(raw, ('%d', '%a', '%A')) < first_index(raw, ('%m', '%b', '%B'))
        del raw, first_index
    except Exception:
        parse_date_day_first = False

DEFAULT_DATE = datetime(2000,1,1, tzinfo=utc_tz)
EPOCH = datetime(1970, 1, 1, tzinfo=_utc_tz)


def is_date_undefined(qt_or_dt):
    d = qt_or_dt
    if d is None:
        return True
    if hasattr(d, 'toString'):
        if hasattr(d, 'date'):
            d = d.date()
        try:
            d = datetime(d.year(), d.month(), d.day(), tzinfo=utc_tz)
        except ValueError:
            return True  # Undefined QDate
    return d.year < UNDEFINED_DATE.year or (
            d.year == UNDEFINED_DATE.year and
            d.month == UNDEFINED_DATE.month and
            d.day == UNDEFINED_DATE.day)


_iso_pat = None


def iso_pat():
    global _iso_pat
    if _iso_pat is None:
        _iso_pat = re.compile(r'\d{4}[/.-]\d{1,2}[/.-]\d{1,2}')
    return _iso_pat


def parse_date(date_string, assume_utc=False, as_utc=True, default=None):
    '''
    Parse a date/time string into a timezone aware datetime object. The timezone
    is always either UTC or the local timezone.

    :param assume_utc: If True and date_string does not specify a timezone,
    assume UTC, otherwise assume local timezone.

    :param as_utc: If True, return a UTC datetime

    :param default: Missing fields are filled in from default. If None, the
    current month and year are used.
    '''
    from dateutil.parser import parse
    if not date_string:
        return UNDEFINED_DATE
    if isinstance(date_string, bytes):
        date_string = date_string.decode(preferred_encoding, 'replace')
    if default is None:
        func = utcnow if assume_utc else now
        default = func().replace(day=15, hour=0, minute=0, second=0, microsecond=0,
                tzinfo=_utc_tz if assume_utc else _local_tz)
    if iso_pat().match(date_string) is not None:
        dt = parse(date_string, default=default)
    else:
        dt = parse(date_string, default=default, dayfirst=parse_date_day_first)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_utc_tz if assume_utc else _local_tz)
    return dt.astimezone(_utc_tz if as_utc else _local_tz)


def fix_only_date(val):
    n = val + timedelta(days=1)
    if n.month > val.month:
        val = val.replace(day=val.day-1)
    if val.day == 1:
        val = val.replace(day=2)
    return val


def parse_only_date(raw, assume_utc=True, as_utc=True):
    '''
    Parse a date string that contains no time information in a manner that
    guarantees that the month and year are always correct in all timezones, and
    the day is at most one day wrong.
    '''
    f = utcnow if assume_utc else now
    default = f().replace(hour=0, minute=0, second=0, microsecond=0,
            day=15)
    return fix_only_date(parse_date(raw, default=default, assume_utc=assume_utc, as_utc=as_utc))


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


def safeyear(x):
    return min(max(MINYEAR, x), MAXYEAR)


def qt_to_dt(qdate_or_qdatetime, as_utc=True):
    from qt.core import QDateTime, Qt
    o = qdate_or_qdatetime
    if o is None or is_date_undefined(qdate_or_qdatetime):
        return UNDEFINED_DATE
    if hasattr(o, 'toUTC'):  # QDateTime
        def c(o: QDateTime, tz=utc_tz):
            d, t = o.date(), o.time()
            try:
                return datetime(safeyear(d.year()), d.month(), d.day(), t.hour(), t.minute(), t.second(), t.msec()*1000, tz)
            except ValueError:
                return datetime(safeyear(d.year()), d.month(), 1, t.hour(), t.minute(), t.second(), t.msec()*1000, tz)

        # DST causes differences in how python and Qt convert automatically from local to UTC, so convert explicitly ourselves
        # QDateTime::toUTC() and datetime.astimezone(utc_tz) give
        # different results for datetimes in the local_tz when DST is involved. Sigh.
        spec = o.timeSpec()
        if spec == Qt.TimeSpec.LocalTime:
            ans = c(o, local_tz)
        elif spec == Qt.TimeSpec.UTC:
            ans = c(o, utc_tz)
        else:
            ans = c(o.toUTC(), utc_tz)
        return ans.astimezone(utc_tz if as_utc else local_tz)

    try:
        dt = datetime(safeyear(o.year()), o.month(), o.day()).replace(tzinfo=_local_tz)
    except ValueError:
        dt = datetime(safeyear(o.year()), o.month(), 1).replace(tzinfo=_local_tz)
    return dt.astimezone(_utc_tz if as_utc else _local_tz)


def qt_from_dt(d: datetime, assume_utc=False):
    from qt.core import QDate, QDateTime, QTime
    if is_date_undefined(d):
        from calibre.gui2 import UNDEFINED_QDATETIME
        return UNDEFINED_QDATETIME
    if d.tzinfo is None:
        d = d.replace(tzinfo=utc_tz if assume_utc else local_tz)
    d = d.astimezone(local_tz)
    # not setting a time zone means this QDateTime has timeSpec() ==
    # LocalTime which is what we want for display/editing.
    ans = QDateTime(QDate(d.year, d.month, d.day), QTime(d.hour, d.minute, d.second, int(d.microsecond / 1000)))
    return ans


def fromtimestamp(ctime, as_utc=True):
    return datetime.fromtimestamp(ctime, _utc_tz if as_utc else _local_tz)


def fromordinal(day, as_utc=True):
    return datetime.fromordinal(day).replace(
            tzinfo=_utc_tz if as_utc else _local_tz)


def isoformat(date_time, assume_utc=False, as_utc=True, sep='T'):
    if not hasattr(date_time, 'tzinfo'):
        return str(date_time.isoformat())
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=_utc_tz if assume_utc else
                _local_tz)
    date_time = date_time.astimezone(_utc_tz if as_utc else _local_tz)
    # native_string_type(sep) because isoformat barfs with unicode sep on python 2.x
    return str(date_time.isoformat(native_string_type(sep)))


def internal_iso_format_string():
    return 'yyyy-MM-ddThh:mm:ss'


def w3cdtf(date_time, assume_utc=False):
    if hasattr(date_time, 'tzinfo'):
        if date_time.tzinfo is None:
            date_time = date_time.replace(tzinfo=_utc_tz if assume_utc else
                    _local_tz)
        date_time = date_time.astimezone(_utc_tz if as_utc else _local_tz)
    return str(date_time.strftime('%Y-%m-%dT%H:%M:%SZ'))


def as_local_time(date_time, assume_utc=True):
    if not hasattr(date_time, 'tzinfo'):
        return date_time
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=_utc_tz if assume_utc else
                _local_tz)
    return date_time.astimezone(_local_tz)


def dt_as_local(dt):
    if dt.tzinfo is local_tz:
        return dt
    return dt.astimezone(local_tz)


def as_utc(date_time, assume_utc=True):
    if not hasattr(date_time, 'tzinfo'):
        return date_time
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=_utc_tz if assume_utc else
                _local_tz)
    return date_time.astimezone(_utc_tz)


def now():
    return datetime.now(_local_tz)


def utcnow():
    return datetime.now(_utc_tz)


def utcfromtimestamp(stamp):
    try:
        return datetime.fromtimestamp(stamp, _utc_tz)
    except Exception:
        # Raised if stamp is out of range for the platforms gmtime function
        # For example, this happens with negative values on windows
        try:
            return EPOCH + timedelta(seconds=stamp)
        except Exception:
            # datetime can only represent years between 1 and 9999
            import traceback
            traceback.print_exc()
    return utcnow()


def timestampfromdt(dt, assume_utc=True):
    return (as_utc(dt, assume_utc=assume_utc) - EPOCH).total_seconds()


# Format date functions {{{

def fd_format_hour(dt, ampm, hr):
    try:
        h = int(strftime('%I' if ampm else '%H', t=dt.timetuple()).strip())
    except Exception:
        h = dt.hour
        if ampm:
            h %= 12
    if len(hr) == 1:
        return f'{h}'
    return f'{h:02}'


def fd_format_minute(dt, ampm, min):
    l = len(min)
    if l == 1:
        return f'{dt.minute}'
    return f'{dt.minute:02}'


def fd_format_second(dt, ampm, sec):
    l = len(sec)
    if l == 1:
        return f'{dt.second}'
    return f'{dt.second:02}'


def fd_format_ampm(dt, ampm, ap):
    res = strftime('%p', t=dt.timetuple())
    if ap in ('aP', 'Ap'):
        return res
    return res.upper() if ap in ('A', 'AP') else res.lower()


def fd_format_day(dt, ampm, dy):
    l = len(dy)
    if l == 1:
        return f'{dt.day}'
    if l == 2:
        return f'{dt.day:02}'
    return lcdata['abday' if l == 3 else 'day'][(dt.weekday() + 1) % 7]


def fd_format_month(dt, ampm, mo):
    l = len(mo)
    if l == 1:
        return f'{dt.month}'
    if l == 2:
        return f'{dt.month:02}'
    return lcdata['abmon' if l == 3 else 'mon'][dt.month - 1]


def fd_format_year(dt, ampm, yr):
    if len(yr) == 2:
        return f'{dt.year % 100:02}'
    return f'{dt.year:04}'


fd_function_index = {
        'd': fd_format_day,
        'M': fd_format_month,
        'y': fd_format_year,
        'h': fd_format_hour,
        'm': fd_format_minute,
        's': fd_format_second,
        'a': fd_format_ampm,
        'A': fd_format_ampm,
    }


def fd_repl_func(dt, ampm, mo):
    s = mo.group(0)
    if not s:
        return ''
    return fd_function_index[s[0]](dt, ampm, s)


def format_date(dt, format, assume_utc=False, as_utc=False):
    ''' Return a date formatted as a string using a subset of Qt's formatting codes '''
    format = format or 'dd MMM yyyy'

    if not isinstance(dt, datetime):
        dt = datetime.combine(dt, dtime())

    if hasattr(dt, 'tzinfo'):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_utc_tz if assume_utc else _local_tz)
        dt = dt.astimezone(_utc_tz if as_utc else _local_tz)

    if format == 'iso':
        return isoformat(dt, assume_utc=assume_utc, as_utc=as_utc)

    if dt == UNDEFINED_DATE:
        return ''

    repl_func = partial(fd_repl_func, dt, 'ap' in format.lower())
    return re.sub(
        r'(s{1,2})|(m{1,2})|(h{1,2})|(ap)|(AP)|(aP)|(Ap)|(d{1,4}|M{1,4}|(?:yyyy|yy))',
        repl_func, format)

# }}}


# Clean date functions {{{

def cd_has_hour(tt, dt):
    tt['hour'] = dt.hour
    return ''


def cd_has_minute(tt, dt):
    tt['min'] = dt.minute
    return ''


def cd_has_second(tt, dt):
    tt['sec'] = dt.second
    return ''


def cd_has_day(tt, dt):
    tt['day'] = dt.day
    return ''


def cd_has_month(tt, dt):
    tt['mon'] = dt.month
    return ''


def cd_has_year(tt, dt):
    tt['year'] = dt.year
    return ''


cd_function_index = {
        'd': cd_has_day,
        'M': cd_has_month,
        'y': cd_has_year,
        'h': cd_has_hour,
        'm': cd_has_minute,
        's': cd_has_second
    }


def cd_repl_func(tt, dt, match_object):
    s = match_object.group(0)
    if not s:
        return ''
    return cd_function_index[s[0]](tt, dt)


def clean_date_for_sort(dt, fmt=None):
    ''' Return dt with fields not in shown in format set to a default '''
    if not fmt:
        fmt = 'yyMd'

    if not isinstance(dt, datetime):
        dt = datetime.combine(dt, dtime())

    if hasattr(dt, 'tzinfo'):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_local_tz)
        dt = as_local_time(dt)

    if fmt == 'iso':
        fmt = 'yyMdhms'

    tt = {'year':UNDEFINED_DATE.year, 'mon':UNDEFINED_DATE.month,
          'day':UNDEFINED_DATE.day, 'hour':UNDEFINED_DATE.hour,
          'min':UNDEFINED_DATE.minute, 'sec':UNDEFINED_DATE.second}

    repl_func = partial(cd_repl_func, tt, dt)
    re.sub(r'(s{1,2})|(m{1,2})|(h{1,2})|(d{1,4}|M{1,4}|(?:yyyy|yy))', repl_func, fmt)
    return dt.replace(year=tt['year'], month=tt['mon'], day=tt['day'], hour=tt['hour'],
                      minute=tt['min'], second=tt['sec'], microsecond=0)
# }}}


def replace_months(datestr, clang):
    # Replace months by english equivalent for parse_date
    frtoen = {
        '[jJ]anvier': 'jan',
        '[fF].vrier': 'feb',
        '[mM]ars': 'mar',
        '[aA]vril': 'apr',
        '[mM]ai': 'may',
        '[jJ]uin': 'jun',
        '[jJ]uillet': 'jul',
        '[aA]o.t': 'aug',
        '[sS]eptembre': 'sep',
        '[Oo]ctobre': 'oct',
        '[nN]ovembre': 'nov',
        '[dD].cembre': 'dec'}
    detoen = {
        '[jJ]anuar': 'jan',
        '[fF]ebruar': 'feb',
        '[mM].rz': 'mar',
        '[aA]pril': 'apr',
        '[mM]ai': 'may',
        '[jJ]uni': 'jun',
        '[jJ]uli': 'jul',
        '[aA]ugust': 'aug',
        '[sS]eptember': 'sep',
        '[Oo]ktober': 'oct',
        '[nN]ovember': 'nov',
        '[dD]ezember': 'dec'}

    if clang == 'fr':
        dictoen = frtoen
    elif clang == 'de':
        dictoen = detoen
    else:
        return datestr

    for k in dictoen:
        tmp = re.sub(k, dictoen[k], datestr)
        if tmp != datestr:
            break
    return tmp
