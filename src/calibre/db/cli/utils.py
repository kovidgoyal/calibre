#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import unicodedata

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


def args_to_action(args: tuple[str, ...], actions: tuple[str, ...], *, default_action: str | None = None) -> tuple[str, tuple[str, ...]]:
    if not args:
        if default_action:
            args = (default_action,)
        else:
            raise SystemExit(_('Error: You must specify an action, one of: {}').format(', '.join(actions)))
    action, args = args[0], args[1:]
    if action not in actions:
        raise SystemExit(_('Error: Action {0} not recognized, must be one of: {1}').format(action, ', '.join(actions)))
    return action, args


def check_options_exclusion(action: str, *options_rules: tuple[str, bool] | tuple[str, bool, str]):
    for rule in options_rules:
        if len(rule) == 3:
            option, invalid, msg = rule
        else:
            option, invalid = rule
            msg = None
        if invalid:
            if msg:
                raise SystemExit(_('Error: The option {0} cannot be used with {1}, {2}').format(option, action, msg))
            raise SystemExit(_('Error: The option {0} cannot be used with {1}').format(option, action))
