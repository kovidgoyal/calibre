#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest, numbers
from polyglot.builtins import map

from calibre.ebooks.epub.cfi.parse import parser, cfi_sort_key, decode_cfi
from polyglot.builtins import iteritems, unicode_type


class Tests(unittest.TestCase):

    def test_sorting(self):
        null_offsets = (0, (0, 0), 0)
        for path, key in [
                ('/1/2/3', ((1, 2, 3), null_offsets)),
                ('/1[id]:34[yyyy]', ((1,), (0, (0, 0), 34))),
                ('/1@1:2', ((1,), (0, (2, 1), 0))),
                ('/1~1.2', ((1,), (1.2, (0, 0), 0))),
        ]:
            self.assertEqual(cfi_sort_key(path), key)

    def test_parsing(self):
        p = parser()

        def step(x):
            if isinstance(x, numbers.Integral):
                return {'num': x}
            return {'num':x[0], 'id':x[1]}

        def s(*args):
            return {'steps':list(map(step, args))}

        def r(*args):
            idx = args.index('!')
            ans = s(*args[:idx])
            ans['redirect'] = s(*args[idx+1:])
            return ans

        def o(*args):
            ans = s(1)
            step = ans['steps'][-1]
            typ, val = args[:2]
            step[{'@':'spatial_offset', '~':'temporal_offset', ':':'text_offset'}[typ]] = val
            if len(args) == 4:
                typ, val = args[2:]
                step[{'@':'spatial_offset', '~':'temporal_offset'}[typ]] = val
            return ans

        def a(before=None, after=None, **params):
            ans = o(':', 3)
            step = ans['steps'][-1]
            ta = {}
            if before is not None:
                ta['before'] = before
            if after is not None:
                ta['after'] = after
            if params:
                ta['params'] = {unicode_type(k):(v,) if isinstance(v, unicode_type) else v for k, v in iteritems(params)}
            if ta:
                step['text_assertion'] = ta
            return ans

        for raw, path, leftover in [
            # Test parsing of steps
            ('/2', s(2), ''),
            ('/2/3/4', s(2, 3, 4), ''),
            ('/1/2[some^,^^id]/3', s(1, (2, 'some,^id'), 3), ''),
            ('/1/2!/3/4', r(1, 2, '!', 3, 4), ''),
            ('/1/2[id]!/3/4', r(1, (2, 'id'), '!', 3, 4), ''),
            ('/1!/2[id]/3/4', r(1, '!', (2, 'id'), 3, 4), ''),

            # Test parsing of offsets
            ('/1~0', o('~', 0), ''),
            ('/1~7', o('~', 7), ''),
            ('/1~43.1', o('~', 43.1), ''),
            ('/1~0.01', o('~', 0.01), ''),
            ('/1~1.301', o('~', 1.301), ''),
            ('/1@23:34.1', o('@', (23, 34.1)), ''),
            ('/1~3@3.1:2.3', o('~', 3.0, '@', (3.1, 2.3)), ''),
            ('/1:0', o(':', 0), ''),
            ('/1:3', o(':', 3), ''),

            # Test parsing of text assertions
            ('/1:3[aa^,b]', a('aa,b'), ''),
            ('/1:3[aa^,b,c1]', a('aa,b', 'c1'), ''),
            ('/1:3[,aa^,b]', a(after='aa,b'), ''),
            ('/1:3[;s=a]', a(s='a'), ''),
            ('/1:3[a;s=a]', a('a', s='a'), ''),
            ('/1:3[a;s=a^,b,c^;d;x=y]', a('a', s=('a,b', 'c;d'), x='y'), ''),

        ]:
            self.assertEqual(p.parse_path(raw), (path, leftover))

    def test_cfi_decode(self):
        from calibre.ebooks.oeb.polish.parsing import parse
        root = parse('''
<html>
<head></head>
<body id="body01">
        <p>…</p>
        <p>…</p>
        <p>…</p>
        <p>…</p>
        <p id="para05">xxx<em>yyy</em>0123456789</p>
        <p>…</p>
        <p>…</p>
        <img id="svgimg" src="foo.svg" alt="…"/>
        <p>…</p>
        <p><span>hello</span><span>goodbye</span>text here<em>adieu</em>text there</p>
    </body>
</html>
''', line_numbers=True, linenumber_attribute='data-lnum')
        body = root[-1]

        def test(cfi, expected):
            self.assertIs(decode_cfi(root, cfi), expected)

        for cfi in '/4 /4[body01] /900[body01] /2[body01]'.split():
            test(cfi, body)

        for i in range(len(body)):
            test('/4/{}'.format((i + 1)*2), body[i])

        p = body[4]
        test('/4/999[para05]', p)
        test('/4/999[para05]/2', p[0])


def find_tests():
    return unittest.TestLoader().loadTestsFromTestCase(Tests)


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(find_tests())
