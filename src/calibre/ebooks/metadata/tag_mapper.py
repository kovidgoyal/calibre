#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

import regex
REGEX_FLAGS = regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.IGNORECASE | regex.UNICODE


def matcher(rule):
    mt = rule['match_type']
    if mt == 'one_of':
        tags = {icu_lower(x.strip()) for x in rule['query'].split(',')}
        return lambda x: x in tags

    if mt == 'not_one_of':
        tags = {icu_lower(x.strip()) for x in rule['query'].split(',')}
        return lambda x: x not in tags

    if mt == 'matches':
        pat = regex.compile(rule['query'], flags=REGEX_FLAGS)
        return lambda x: pat.match(x) is not None

    if mt == 'not_matches':
        pat = regex.compile(rule['query'], flags=REGEX_FLAGS)
        return lambda x: pat.match(x) is None

    return lambda x: False


def apply_rules(tag, rules):
    for rule, matches in rules:
        ltag = icu_lower(tag)
        if matches(ltag):
            ac = rule['action']
            if ac == 'remove':
                return None
            if ac == 'keep':
                return tag
            if ac == 'replace':
                tag = regex.sub(rule['query'], rule['replace'], flags=REGEX_FLAGS)
    return tag


def map_tags(tags, rules=()):
    if not tags:
        return []
    if not rules:
        return list(tags)
    rules = [(r, matcher(r)) for r in rules]
    return [x for x in (apply_rules(t, rules) for t in tags) if x]
