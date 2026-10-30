#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import unicodedata
from collections.abc import Sequence

from calibre.utils.localization import _

eaw = unicodedata.east_asian_width
# Control characters, other than tab and newline, that could be used to inject
# escape sequences into the terminal
CONTROL_CHARS = tuple(x for x in range(32) if x not in (9, 10)) + tuple(range(127, 160))
control_chars_table = dict.fromkeys(CONTROL_CHARS)


def chr_width(x):
    return 1 + eaw(x).startswith('W')


def str_width(x):
    return sum(map(chr_width, x))


def for_terminal(text: str) -> str:
    return text.translate(control_chars_table)


def args_to_action(args: Sequence[str], actions: Sequence[str], *, default_action: str | None = None) -> tuple[str, list[str]]:
    if not args:
        if not default_action:
            raise SystemExit(_('Error: You must specify an action, one of: {}').format(', '.join(actions)))
        args = (default_action,)
    action = args[0]
    if action not in actions:
        raise SystemExit(_('Error: Action {0} not recognized, must be one of: {1}').format(action, ', '.join(actions)))
    return action, list(args[1:])


def check_options_exclusion(action: str, *rules: tuple[str, bool]) -> None:
    for option, invalid in rules:
        if invalid:
            raise SystemExit(_('Error: The option {0} cannot be used with {1}').format(option, action))
