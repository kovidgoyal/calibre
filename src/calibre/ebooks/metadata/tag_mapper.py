#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import regex
from collections import deque

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
    ans = []
    tags = deque()
    tags.append(tag)
    maxiter = 20
    while tags and maxiter > 0:
        tag = tags.popleft()
        ltag = icu_lower(tag)
        maxiter -= 1
        for rule, matches in rules:
            if matches(ltag):
                ac = rule['action']
                if ac == 'remove':
                    break
                if ac == 'keep':
                    ans.append(tag)
                    break
                if ac == 'replace':
                    if 'matches' in rule['match_type']:
                        tag = regex.sub(rule['query'], rule['replace'], tag, flags=REGEX_FLAGS)
                    else:
                        tag = rule['replace']
                    if ',' in tag:
                        replacement_tags = []
                        self_added = False
                        for rtag in (x.strip() for x in tag.split(',')):
                            if icu_lower(rtag) == ltag:
                                if not self_added:
                                    ans.append(rtag)
                                    self_added = True
                            else:
                                replacement_tags.append(rtag)
                        tags.extendleft(reversed(replacement_tags))
                    else:
                        if icu_lower(tag) == ltag:
                            # Case change or self replacement
                            ans.append(tag)
                            break
                        tags.appendleft(tag)
                    break
        else:  # no rule matched, default keep
            ans.append(tag)

    ans.extend(tags)
    return ans

def uniq(vals, kmap=icu_lower):
    ''' Remove all duplicates from vals, while preserving order. kmap must be a
    callable that returns a hashable value for every item in vals '''
    vals = vals or ()
    lvals = (kmap(x) for x in vals)
    seen = set()
    seen_add = seen.add
    return list(x for x, k in zip(vals, lvals) if k not in seen and not seen_add(k))


def map_tags(tags, rules=()):
    if not tags:
        return []
    if not rules:
        return list(tags)
    rules = [(r, matcher(r)) for r in rules]
    ans = []
    for t in tags:
        ans.extend(apply_rules(t, rules))
    return uniq(filter(None, ans))

def test():
    rules = [{'action':'replace', 'query':'t1', 'match_type':'one_of', 'replace':'t2'}]
    assert map_tags(['t1', 'x1'], rules) == ['t2', 'x1']
    rules = [{'action':'replace', 'query':'(.)1', 'match_type':'matches', 'replace':r'\g<1>2'}]
    assert map_tags(['t1', 'x1'], rules) == ['t2', 'x2']
    rules = [{'action':'replace', 'query':'t1', 'match_type':'one_of', 'replace':'t2, t3'}]
    assert map_tags(['t1', 'x1'], rules) == ['t2', 't3', 'x1']
    rules = [{'action':'replace', 'query':'(.)1', 'match_type':'matches', 'replace':r'\g<1>2,3'}]
    assert map_tags(['t1', 'x1'], rules) == ['t2', '3', 'x2']
    rules = [
        {'action':'replace', 'query':'t1', 'match_type':'one_of', 'replace':r't2,t3'},
        {'action':'remove', 'query':'t2', 'match_type':'one_of'},
    ]
    assert map_tags(['t1', 'x1'], rules) == ['t3', 'x1']
    rules = [{'action':'replace', 'query':'t1', 'match_type':'one_of', 'replace':'t1'}]
    assert map_tags(['t1', 'x1'], rules) == ['t1', 'x1']
    rules = [
        {'action':'replace', 'query':'t1', 'match_type':'one_of', 'replace':'t2'},
        {'action':'replace', 'query':'t2', 'match_type':'one_of', 'replace':'t1'},
    ]
    assert map_tags(['t1', 't2'], rules) == ['t1', 't2']
    rules = [
        {'action':'replace', 'query':'a', 'match_type':'one_of', 'replace':'A'},
    ]
    assert map_tags(['a', 'b'], rules) == ['A', 'b']
    rules = [
        {'action':'replace', 'query':'a,b', 'match_type':'one_of', 'replace':'A,B'},
    ]
    assert map_tags(['a', 'b'], rules) == ['A', 'B']

if __name__ == '__main__':
    test()
