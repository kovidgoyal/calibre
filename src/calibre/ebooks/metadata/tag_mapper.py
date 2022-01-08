#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


from collections import deque


def compile_pat(pat):
    import regex
    REGEX_FLAGS = regex.VERSION1 | regex.WORD | regex.FULLCASE | regex.IGNORECASE | regex.UNICODE
    return regex.compile(pat, flags=REGEX_FLAGS)


def matcher(rule):
    mt = rule['match_type']
    if mt == 'one_of':
        tags = {icu_lower(x.strip()) for x in rule['query'].split(',')}
        return lambda x: x in tags

    if mt == 'not_one_of':
        tags = {icu_lower(x.strip()) for x in rule['query'].split(',')}
        return lambda x: x not in tags

    if mt == 'matches':
        pat = compile_pat(rule['query'])
        return lambda x: pat.match(x) is not None

    if mt == 'not_matches':
        pat = compile_pat(rule['query'])
        return lambda x: pat.match(x) is None

    if mt == 'has':
        s = icu_lower(rule['query'])
        return lambda x: s in x

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
                        tag = compile_pat(rule['query']).sub(rule['replace'], tag)
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
                if ac == 'capitalize':
                    ans.append(tag.capitalize())
                    break
                if ac == 'titlecase':
                    from calibre.utils.titlecase import titlecase
                    ans.append(titlecase(tag))
                    break
                if ac == 'lower':
                    ans.append(icu_lower(tag))
                    break
                if ac == 'upper':
                    ans.append(icu_upper(tag))
                    break
                if ac == 'split':
                    stags = list(filter(None, (x.strip() for x in tag.split(rule['replace']))))
                    if stags:
                        if stags[0] == tag:
                            ans.append(tag)
                        else:
                            tags.extendleft(reversed(stags))
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
    return uniq(list(filter(None, ans)))


def find_tests():
    import unittest

    class TestTagMapper(unittest.TestCase):

        def test_tag_mapper(self):

            def rule(action, query, replace=None, match_type='one_of'):
                ans = {'action':action, 'query': query, 'match_type':match_type}
                if replace is not None:
                    ans['replace'] = replace
                return ans

            def run(rules, tags, expected):
                if isinstance(rules, dict):
                    rules = [rules]
                if isinstance(tags, str):
                    tags = [x.strip() for x in tags.split(',')]
                if isinstance(expected, str):
                    expected = [x.strip() for x in expected.split(',')]
                ans = map_tags(tags, rules)
                self.assertEqual(ans, expected)

            run(rule('capitalize', 't1,t2'), 't1,x1', 'T1,x1')
            run(rule('titlecase', 'some tag'), 'some tag,x1', 'Some Tag,x1')
            run(rule('upper', 'ta,t2'), 'ta,x1', 'TA,x1')
            run(rule('lower', 'ta,x1'), 'TA,X1', 'ta,x1')
            run(rule('replace', 't1', 't2'), 't1,x1', 't2,x1')
            run(rule('replace', '(.)1', r'\g<1>2', 'matches'), 't1,x1', 't2,x2')
            run(rule('replace', '(.)1', r'\g<1>2,3', 'matches'), 't1,x1', 't2,3,x2')
            run(rule('replace', 't1', 't2, t3'), 't1,x1', 't2,t3,x1')
            run([rule('replace', 't1', 't2,t3'), rule('remove', 't2')], 't1,x1', 't3,x1')
            run(rule('replace', 't1', 't1'), 't1,x1', 't1,x1')
            run([rule('replace', 't1', 't2'), rule('replace', 't2', 't1')], 't1,t2', 't1,t2')
            run(rule('replace', 'a', 'A'), 'a,b', 'A,b')
            run(rule('replace', 'a,b', 'A,B'), 'a,b', 'A,B')
            run(rule('replace', 'L', 'T', 'has'), 'L', 'T')
            run(rule('split', '/', '/', 'has'), 'a/b/c,d', 'a,b,c,d')
            run(rule('split', '/', '/', 'has'), '/,d', 'd')
            run(rule('split', '/', '/', 'has'), '/a/', 'a')
            run(rule('split', 'a,b', '/'), 'a,b', 'a,b')
            run(rule('split', 'a b', ' ', 'has'), 'a b', 'a,b')
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestTagMapper)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli
    run_cli(find_tests())
