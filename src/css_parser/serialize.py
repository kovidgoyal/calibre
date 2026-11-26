#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
The css_parser.serialize module, for plugins written for css_parser, see the
css_parser package. kgcss writes CSS in a fixed, normalized form: the
preferences are accepted and ignored.
"""

__all__ = ['CSSSerializer', 'Preferences']


class Preferences:
    "Serializer preferences, which are accepted and ignored"

    def __init__(self, **initials: object) -> None:
        self.__dict__.update(initials)

    def __setattr__(self, name: str, value: object) -> None:
        self.__dict__[name] = value

    def useDefaults(self) -> None:
        pass

    def useMinified(self) -> None:
        pass


class CSSSerializer:
    "The serializer object, css_parser.ser, whose preferences are ignored"

    def __init__(self, prefs: Preferences | None = None) -> None:
        self.prefs = prefs or Preferences()
