#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

# Boolean columns in the Kobo database can contain either the strings
# 'true'/'false' or the integers 1/0. Newer firmware mixes both forms in the
# same column, so always accept either form when reading.


def is_true_value(x: object) -> bool:
    if isinstance(x, str):
        return x.lower() in ('true', '1')
    return bool(x)


def is_false_value(x: object) -> bool:
    if isinstance(x, str):
        return x.lower() in ('false', '0')
    return not x


def bool_match(column: str, value: bool) -> str:
    """Return an SQL condition that is true when the boolean column has the specified value"""
    return f"{column} IN ('true', 1)" if value else f"{column} IN ('false', 0)"
