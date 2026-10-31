#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

import re
from datetime import MAXYEAR, MINYEAR, datetime, timedelta
from datetime import time as dtime
from functools import partial
from typing import TYPE_CHECKING, overload

from calibre import strftime
from calibre.constants import ismacos, iswindows, preferred_encoding
from calibre.utils.iso8601 import UNDEFINED_DATE, local_tz, utc_tz
from calibre.utils.localization import lcdata

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date, tzinfo

    from qt.core import QDate, QDateTime

# When parsing ambiguous dates that could be either dd-MM Or MM-dd use the
# user's locale preferences
if iswindows:
    import ctypes

    LOCALE_SSHORTDATE, LOCALE_USER_DEFAULT = 0x1F, 0
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
        assert date_fmt is not None
        parse_date_day_first = date_fmt.index('d') < date_fmt.index('M')
    except Exception:
        parse_date_day_first = False
else:
    try:

        def first_index(raw: str, queries: Iterable[str]) -> int:
            for q in queries:
                try:
                    return raw.index(str(q))
                except ValueError:
                    pass
            return -1

        import locale

        raw = locale.nl_langinfo(locale.D_FMT)
        parse_date_day_first = first_index(raw, ('%d', '%a', '%A')) < first_index(raw, ('%m', '%b', '%B'))
        del raw, first_index
    except Exception:
        parse_date_day_first = False

DEFAULT_DATE = datetime(2000, 1, 1, tzinfo=utc_tz)
EPOCH = datetime(1970, 1, 1, tzinfo=utc_tz)


def is_date_undefined(qt_or_dt: date | QDate | QDateTime | None) -> bool:
    d = qt_or_dt
    if d is None:
        return True
    if hasattr(d, 'toString'):
        if hasattr(d, 'date'):
            d = d.date()  # ty: ignore[call-non-callable]
        try:
            d = datetime(d.year(), d.month(), d.day(), tzinfo=utc_tz)  # ty: ignore[call-non-callable]
        except ValueError:
            return True  # Undefined QDate
    return d.year < UNDEFINED_DATE.year or (d.year == UNDEFINED_DATE.year and d.month == UNDEFINED_DATE.month and d.day == UNDEFINED_DATE.day)


_iso_pat = None


def iso_pat() -> re.Pattern[str]:
    global _iso_pat
    if _iso_pat is None:
        _iso_pat = re.compile(r'\d{4}[/.-]\d{1,2}[/.-]\d{1,2}')
    return _iso_pat


def parse_date(date_string: str | bytes | None, assume_utc: bool = False, as_utc: bool = True, default: datetime | None = None) -> datetime:
    """
    Parse a date/time string into a timezone aware datetime object. The timezone
    is always either UTC or the local timezone.

    :param assume_utc: If True and date_string does not specify a timezone,
    assume UTC, otherwise assume local timezone.

    :param as_utc: If True, return a UTC datetime

    :param default: Missing fields are filled in from default. If None, the
    current month and year are used.
    """
    from dateutil.parser import parse

    if not date_string:
        return UNDEFINED_DATE
    if isinstance(date_string, bytes):
        date_string = date_string.decode(preferred_encoding, 'replace')
    if default is None:
        func = utcnow if assume_utc else now
        default = func().replace(day=15, hour=0, minute=0, second=0, microsecond=0, tzinfo=utc_tz if assume_utc else local_tz)
    if iso_pat().match(date_string) is not None:
        dt = parse(date_string, default=default)
    else:
        dt = parse(date_string, default=default, dayfirst=parse_date_day_first)
    return fix_tzinfo(dt, assume_utc=assume_utc, as_utc=as_utc)


def fix_only_date(val: datetime) -> datetime:
    n = val + timedelta(days=1)
    if n.month > val.month:
        val = val.replace(day=val.day - 1)
    if val.day == 1:
        val = val.replace(day=2)
    return val


@overload
def fix_tzinfo(dt: datetime, assume_utc: bool = False, as_utc: bool = True) -> datetime: ...
@overload
def fix_tzinfo[T](dt: T, assume_utc: bool = False, as_utc: bool = True) -> T: ...
def fix_tzinfo(dt: datetime, assume_utc: bool = False, as_utc: bool = True) -> datetime:
    if not hasattr(dt, 'tzinfo'):
        # not a datetime (str, None, date, ...), return unchanged
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc_tz if assume_utc else local_tz)
    return dt.astimezone(utc_tz if as_utc else local_tz)


def parse_only_date(raw: str | bytes | None, assume_utc: bool = True, as_utc: bool = True) -> datetime:
    """
    Parse a date string that contains no time information in a manner that
    guarantees that the month and year are always correct in all timezones, and
    the day is at most one day wrong.
    """
    f = utcnow if assume_utc else now
    default = f().replace(hour=0, minute=0, second=0, microsecond=0, day=15)
    return fix_only_date(parse_date(raw, default=default, assume_utc=assume_utc, as_utc=as_utc))


def strptime(val: str, fmt: str, assume_utc: bool = False, as_utc: bool = True) -> datetime:
    dt = datetime.strptime(val, fmt)  # ruff: ignore[call-datetime-strptime-without-zone]
    return fix_tzinfo(dt, assume_utc=assume_utc, as_utc=as_utc)


def dt_factory(time_t: tuple[int, int, int, int, int, int, *tuple[int, ...]], assume_utc: bool = False, as_utc: bool = True) -> datetime:
    dt = datetime(*(time_t[0:6]))  # ruff: ignore[call-datetime-without-tzinfo]
    return fix_tzinfo(dt, assume_utc=assume_utc, as_utc=as_utc)


def safeyear(x: int) -> int:
    return min(max(MINYEAR, x), MAXYEAR)


def qt_to_dt(qdate_or_qdatetime: QDate | QDateTime | None, as_utc: bool = True) -> datetime:
    from qt.core import QDateTime, Qt  # ruff: ignore[unused-import]

    o = qdate_or_qdatetime
    if o is None or is_date_undefined(qdate_or_qdatetime):
        return UNDEFINED_DATE
    if hasattr(o, 'toUTC'):  # QDateTime

        def c(o: QDateTime, tz: tzinfo = utc_tz) -> datetime:
            d, t = o.date(), o.time()
            try:
                return datetime(safeyear(d.year()), d.month(), d.day(), t.hour(), t.minute(), t.second(), t.msec() * 1000, tz)
            except ValueError:
                return datetime(safeyear(d.year()), d.month(), 1, t.hour(), t.minute(), t.second(), t.msec() * 1000, tz)

        # DST causes differences in how python and Qt convert automatically from local to UTC, so convert explicitly ourselves
        # QDateTime::toUTC() and datetime.astimezone(utc_tz) give
        # different results for datetimes in the local_tz when DST is involved. Sigh.
        spec = o.timeSpec()  # ty: ignore[unresolved-attribute]
        if spec == Qt.TimeSpec.LocalTime:
            ans = c(o, local_tz)  # ty: ignore[invalid-argument-type]
        elif spec == Qt.TimeSpec.UTC:
            ans = c(o, utc_tz)  # ty: ignore[invalid-argument-type]
        else:
            ans = c(o.toUTC(), utc_tz)  # ty: ignore[call-non-callable]
        return fix_tzinfo(ans, assume_utc=False, as_utc=as_utc)

    try:
        dt = datetime(safeyear(o.year()), o.month(), o.day(), tzinfo=local_tz)
    except ValueError:
        dt = datetime(safeyear(o.year()), o.month(), 1, tzinfo=local_tz)
    return fix_tzinfo(dt, assume_utc=False, as_utc=as_utc)


def qt_from_dt(d: datetime, assume_utc: bool = False) -> QDateTime:
    from qt.core import QDate, QDateTime, QTime

    if is_date_undefined(d):
        from calibre.gui2 import UNDEFINED_QDATETIME

        return UNDEFINED_QDATETIME
    d = fix_tzinfo(d, assume_utc=assume_utc, as_utc=False)
    # not setting a time zone means this QDateTime has timeSpec() ==
    # LocalTime which is what we want for display/editing.
    ans = QDateTime(QDate(d.year, d.month, d.day), QTime(d.hour, d.minute, d.second, int(d.microsecond / 1000)))
    return ans


def fromtimestamp(ctime: float, as_utc: bool = True) -> datetime:
    return datetime.fromtimestamp(ctime, utc_tz if as_utc else local_tz)


def fromordinal(day: int, as_utc: bool = True) -> datetime:
    return datetime.fromordinal(day).replace(tzinfo=utc_tz if as_utc else local_tz)


def isoformat(date_time: date, assume_utc: bool = False, as_utc: bool = True, sep: str = 'T') -> str:
    if not hasattr(date_time, 'tzinfo'):
        return date_time.isoformat()
    date_time = fix_tzinfo(date_time, assume_utc=assume_utc, as_utc=as_utc)
    return date_time.isoformat(sep)  # ty: ignore[too-many-positional-arguments]


def internal_iso_format_string() -> str:
    return 'yyyy-MM-ddThh:mm:ss'


def w3cdtf(date_time: datetime, assume_utc: bool = False) -> str:
    date_time = fix_tzinfo(date_time, assume_utc=assume_utc, as_utc=True)
    return str(date_time.strftime('%Y-%m-%dT%H:%M:%SZ'))


def as_local_time[T](date_time: T, assume_utc: bool = True) -> T:
    return fix_tzinfo(date_time, assume_utc=assume_utc, as_utc=False)


def dt_as_local(dt: datetime) -> datetime:
    if dt.tzinfo is local_tz:
        return dt
    return fix_tzinfo(dt, assume_utc=False, as_utc=False)


def as_utc[T](date_time: T, assume_utc: bool = True) -> T:
    return fix_tzinfo(date_time, assume_utc=assume_utc, as_utc=True)


def now() -> datetime:
    return datetime.now(local_tz)


def utcnow() -> datetime:
    return datetime.now(utc_tz)


def utcfromtimestamp(stamp: float) -> datetime:
    try:
        return datetime.fromtimestamp(stamp, utc_tz)
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


def timestampfromdt(dt: datetime, assume_utc: bool = True) -> float:
    return (as_utc(dt, assume_utc=assume_utc) - EPOCH).total_seconds()


# Format date functions {{{


def fd_format_hour(dt: datetime, ampm: bool, hr: str) -> str:
    try:
        h = int(strftime('%I' if ampm else '%H', t=dt.timetuple()).strip())
    except Exception:
        h = dt.hour
        if ampm:
            h %= 12
    if len(hr) == 1:
        return f'{h}'
    return f'{h:02}'


def fd_format_minute(dt: datetime, ampm: bool, min: str) -> str:
    l = len(min)
    if l == 1:
        return f'{dt.minute}'
    return f'{dt.minute:02}'


def fd_format_second(dt: datetime, ampm: bool, sec: str) -> str:
    l = len(sec)
    if l == 1:
        return f'{dt.second}'
    return f'{dt.second:02}'


def fd_format_ampm(dt: datetime, ampm: bool, ap: str) -> str:
    res = strftime('%p', t=dt.timetuple())
    if ap in ('aP', 'Ap'):
        return res
    return res.upper() if ap in ('A', 'AP') else res.lower()


def fd_format_day(dt: datetime, ampm: bool, dy: str) -> str:
    l = len(dy)
    if l == 1:
        return f'{dt.day}'
    if l == 2:
        return f'{dt.day:02}'
    return lcdata['abday' if l == 3 else 'day'][(dt.weekday() + 1) % 7]


def fd_format_month(dt: datetime, ampm: bool, mo: str) -> str:
    l = len(mo)
    if l == 1:
        return f'{dt.month}'
    if l == 2:
        return f'{dt.month:02}'
    return lcdata['abmon' if l == 3 else 'mon'][dt.month - 1]


def fd_format_year(dt: datetime, ampm: bool, yr: str) -> str:
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


def fd_repl_func(dt: datetime, ampm: bool, mo: re.Match[str]) -> str:
    s = mo.group(0)
    if not s:
        return ''
    return fd_function_index[s[0]](dt, ampm, s)


def format_date(dt: date, format: str | None, assume_utc: bool = False, as_utc: bool = False) -> str:
    """Return a date formatted as a string using a subset of Qt's formatting codes"""
    format = format or 'dd MMM yyyy'

    if not isinstance(dt, datetime):
        dt = datetime.combine(dt, dtime())

    dt = fix_tzinfo(dt, assume_utc=assume_utc, as_utc=as_utc)

    if format == 'iso':
        return isoformat(dt, assume_utc=assume_utc, as_utc=as_utc)

    if dt == UNDEFINED_DATE:
        return ''

    repl_func = partial(fd_repl_func, dt, 'ap' in format.lower())
    return re.sub(r'(s{1,2})|(m{1,2})|(h{1,2})|(ap)|(AP)|(aP)|(Ap)|(d{1,4}|M{1,4}|(?:yyyy|yy))', repl_func, format)


# }}}

# Clean date functions {{{


def cd_has_hour(tt: dict[str, int], dt: datetime) -> str:
    tt['hour'] = dt.hour
    return ''


def cd_has_minute(tt: dict[str, int], dt: datetime) -> str:
    tt['min'] = dt.minute
    return ''


def cd_has_second(tt: dict[str, int], dt: datetime) -> str:
    tt['sec'] = dt.second
    return ''


def cd_has_day(tt: dict[str, int], dt: datetime) -> str:
    tt['day'] = dt.day
    return ''


def cd_has_month(tt: dict[str, int], dt: datetime) -> str:
    tt['mon'] = dt.month
    return ''


def cd_has_year(tt: dict[str, int], dt: datetime) -> str:
    tt['year'] = dt.year
    return ''


cd_function_index = {
    'd': cd_has_day,
    'M': cd_has_month,
    'y': cd_has_year,
    'h': cd_has_hour,
    'm': cd_has_minute,
    's': cd_has_second,
}


def cd_repl_func(tt: dict[str, int], dt: datetime, match_object: re.Match[str]) -> str:
    s = match_object.group(0)
    if not s:
        return ''
    return cd_function_index[s[0]](tt, dt)


def clean_date_for_sort(dt: date, fmt: str | None = None) -> datetime:
    """Return dt with fields not in shown in format set to a default"""
    if not fmt:
        fmt = 'yyMd'

    if not isinstance(dt, datetime):
        dt = datetime.combine(dt, dtime())

    dt = fix_tzinfo(dt, assume_utc=False, as_utc=False)

    if fmt == 'iso':
        fmt = 'yyMdhms'

    tt = {
        'year': UNDEFINED_DATE.year,
        'mon': UNDEFINED_DATE.month,
        'day': UNDEFINED_DATE.day,
        'hour': UNDEFINED_DATE.hour,
        'min': UNDEFINED_DATE.minute,
        'sec': UNDEFINED_DATE.second,
    }

    repl_func = partial(cd_repl_func, tt, dt)
    re.sub(r'(s{1,2})|(m{1,2})|(h{1,2})|(d{1,4}|M{1,4}|(?:yyyy|yy))', repl_func, fmt)
    return dt.replace(
        year=tt['year'],
        month=tt['mon'],
        day=tt['day'],
        hour=tt['hour'],
        minute=tt['min'],
        second=tt['sec'],
        microsecond=0,
    )


# }}}


def replace_months(datestr: str, clang: str) -> str:
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
        '[dD].cembre': 'dec',
    }
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
        '[dD]ezember': 'dec',
    }

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
