#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2016, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from css_parser import parseStyle

from calibre.constants import iswindows
from calibre.ebooks.oeb.base import OEB_STYLES, OEB_DOCS
from calibre.ebooks.oeb.polish.cascade import iterrules, resolve_styles, DEFAULTS
from calibre.ebooks.oeb.polish.css import remove_property_value
from calibre.ebooks.oeb.polish.embed import find_matching_font
from calibre.ebooks.oeb.polish.container import ContainerBase, href_to_name
from calibre.ebooks.oeb.polish.stats import StatsCollector, font_keys, normalize_font_properties, prepare_font_rule
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.utils.logging import Log, Stream
from polyglot.builtins import iteritems, unicode_type


class VirtualContainer(ContainerBase):

    tweak_mode = True

    def __init__(self, files):
        s = Stream()
        self.log_stream = s.stream
        log = Log()
        log.outputs = [s]
        self.opf_version_parsed = (2, 0, 0)
        ContainerBase.__init__(self, log=log)
        self.mime_map = {k:self.guess_type(k) for k in files}
        self.files = files

    def has_name(self, name):
        return name in self.mime_map

    def href_to_name(self, href, base=None):
        return href_to_name(href, ('C:\\root' if iswindows else '/root'), base)

    def parsed(self, name):
        if name not in self.parsed_cache:
            mt = self.mime_map[name]
            if mt in OEB_STYLES:
                self.parsed_cache[name] = self.parse_css(self.files[name], name)
            elif mt in OEB_DOCS:
                self.parsed_cache[name] = self.parse_xhtml(self.files[name], name)
            else:
                self.parsed_cache[name] = self.files[name]
        return self.parsed_cache[name]

    @property
    def spine_names(self):
        for name in sorted(self.mime_map):
            if self.mime_map[name] in OEB_DOCS:
                yield name, True


class CascadeTest(BaseTest):

    def test_iterrules(self):
        def get_rules(files, name='x/one.css', l=1, rule_type=None):
            c = VirtualContainer(files)
            rules = tuple(iterrules(c, name, rule_type=rule_type))
            self.assertEqual(len(rules), l)
            return rules, c
        get_rules({'x/one.css':'@import "../two.css";', 'two.css':'body { color: red; }'})
        get_rules({'x/one.css':'@import "../two.css" screen;', 'two.css':'body { color: red; }'})
        get_rules({'x/one.css':'@import "../two.css" xyz;', 'two.css':'body { color: red; }'}, l=0)
        get_rules({'x/one.css':'@import "../two.css";', 'two.css':'body { color: red; }'}, l=0, rule_type='FONT_FACE_RULE')
        get_rules({'x/one.css':'@import "../two.css";', 'two.css':'body { color: red; }'}, rule_type='STYLE_RULE')
        get_rules({'x/one.css':'@media screen { body { color: red; } }'})
        get_rules({'x/one.css':'@media xyz { body { color: red; } }'}, l=0)
        c = get_rules({'x/one.css':'@import "../two.css";', 'two.css':'@import "x/one.css"; body { color: red; }'})[1]
        self.assertIn('Recursive import', c.log_stream.getvalue())

    def test_resolve_styles(self):

        def test_property(select, resolve_property, selector, name, val=None):
            elem = next(select(selector))
            ans = resolve_property(elem, name)
            if val is None:
                val = unicode_type(DEFAULTS[name])
            self.assertEqual(val, ans.cssText)

        def test_pseudo_property(select, resolve_pseudo_property, selector, prop, name, val=None, abort_on_missing=False):
            elem = next(select(selector))
            ans = resolve_pseudo_property(elem, prop, name, abort_on_missing=abort_on_missing)
            if abort_on_missing:
                if val is None:
                    self.assertTrue(ans is None)
                    return
            if val is None:
                val = unicode_type(DEFAULTS[name])
            self.assertEqual(val, ans.cssText)

        def get_maps(html, styles=None, pseudo=False):
            html = '<html><head><link href="styles.css"></head><body>{}</body></html>'.format(html)
            c = VirtualContainer({'index.html':html, 'styles.css':styles or 'body { color: red; font-family: "Kovid Goyal", sans-serif }'})
            resolve_property, resolve_pseudo_property, select = resolve_styles(c, 'index.html')
            if pseudo:
                tp = partial(test_pseudo_property, select, resolve_pseudo_property)
            else:
                tp = partial(test_property, select, resolve_property)
            return tp

        t = get_maps('<p style="margin:11pt"><b>x</b>xx</p>')
        t('body', 'color', 'red')
        t('p', 'color', 'red')
        t('b', 'font-weight', 'bold')
        t('p', 'margin-top', '11pt')
        t('b', 'margin-top')
        t('body', 'display', 'block')
        t('b', 'display', 'inline')
        t('body', 'font-family', ('"Kovid Goyal"', 'sans-serif'))
        for e in ('body', 'p', 'b'):
            for prop in 'background-color text-indent'.split():
                t(e, prop)

        t = get_maps('<p>xxx</p><style>p {color: blue}</style>', 'p {color: red}')
        t('p', 'color', 'blue')
        t = get_maps('<p style="color: blue">xxx</p>', 'p {color: red}')
        t('p', 'color', 'blue')
        t = get_maps('<p style="color: blue">xxx</p>', 'p {color: red !important}')
        t('p', 'color', 'red')
        t = get_maps('<p id="p">xxx</p>', '#p { color: blue } p {color: red}')
        t('p', 'color', 'blue')
        t = get_maps('<p>xxx</p>', 'p {color: red; color: blue}')
        t('p', 'color', 'blue')
        t = get_maps('<p>xxx</p><style>p {color: blue}</style>', 'p {color: red; margin:11pt}')
        t('p', 'margin-top', '11pt')
        t = get_maps('<p></p>', 'p:before { content: "xxx" }', True)
        t('p', 'before', 'content', '"xxx"')
        t = get_maps('<p></p>', 'body p:before { content: "xxx" } p:before { content: "yyy" }', True)
        t('p', 'before', 'content', '"xxx"')
        t = get_maps('<p></p>', "p:before { content: 'xxx' } p:first-letter { font-weight: bold }", True)
        t('p', 'before', 'content', '"xxx"')
        t('p', 'first-letter', 'font-weight', 'bold')
        t = get_maps('<p></p>', 'p { font-weight: bold; margin: 11pt } p:before { content: xxx }', True)
        t('p', 'before', 'content', 'xxx')
        t('p', 'before', 'margin-top', '0')
        t('p', 'before', 'font-weight', 'bold')
        t('p', 'first-letter', 'content')
        t('p', 'first-letter', 'content', abort_on_missing=True)

    def test_font_stats(self):
        embeds = '@font-face { font-family: X; src: url(X.otf) }\n@font-face { font-family: X; src: url(XB.otf); font-weight: bold }'

        def get_stats(html, *fonts):
            styles = []
            html = '<html><head><link href="styles.css"></head><body>{}</body></html>'.format(html)
            files = {'index.html':html, 'X.otf':b'xxx', 'XB.otf': b'xbxb'}
            for font in fonts:
                styles.append('@font-face {')
                for k, v in iteritems(font):
                    if k == 'src':
                        files[v] = b'xxx'
                        v = 'url(%s)' % v
                    styles.append('%s : %s;' % (k, v))
                styles.append('}\n')
            html = '<html><head><link href="styles.css"></head><body>{}</body></html>'.format(html)
            files['styles.css'] = embeds + '\n'.join(styles)
            c = VirtualContainer(files)
            return StatsCollector(c, do_embed=True)

        def font(family, weight=None, style=None):
            f = {}
            if weight is not None:
                f['font-weight'] = weight
            if style is not None:
                f['font-style'] = style
            f = normalize_font_properties(f)
            f['font-family'] = [family]
            return f

        def font_rule(src, *args, **kw):
            ans = font(*args, **kw)
            ans['font-family'] = list(map(icu_lower, ans['font-family']))
            prepare_font_rule(ans)
            ans['src'] = src
            return ans

        def fkey(*args, **kw):
            f = font(*args, **kw)
            f['font-family'] = icu_lower(f['font-family'][0])
            return frozenset((k, v) for k, v in iteritems(f) if k in font_keys)

        def fu(text, *args, **kw):
            key = fkey(*args, **kw)
            val = font(*args, **kw)
            val['text'] = set(text)
            val['font-family'] = val['font-family'][0]
            return key, val

        s = get_stats('<p style="font-family: X">abc<b>d\nef</b><i>ghi</i></p><p style="font-family: U">u</p>')
        # The normal font must include ghi as it will be used to simulate
        # italic by most rendering engines when the italic font is missing
        self.assertEqual(s.font_stats, {'XB.otf':set('def'), 'X.otf':set('abcghi')})
        self.assertEqual(s.font_spec_map, {'index.html':set('XU')})
        self.assertEqual(s.all_font_rules, {'X.otf':font_rule('X.otf', 'X'), 'XB.otf':font_rule('XB.otf', 'X', 'bold')})
        self.assertEqual(set(s.font_rule_map), {'index.html'})
        self.assertEqual(s.font_rule_map['index.html'], [font_rule('X.otf', 'X'), font_rule('XB.otf', 'X', 'bold')])
        self.assertEqual(set(s.font_usage_map), {'index.html'})
        self.assertEqual(s.font_usage_map['index.html'], dict([fu('abc', 'X'), fu('def', 'X', weight='bold'), fu('ghi', 'X', style='italic'), fu('u', 'U')]))

        s = get_stats('<p style="font-family: X; text-transform:uppercase">abc</p><b style="font-family: X; font-variant: small-caps">d\nef</b>')
        self.assertEqual(s.font_stats, {'XB.otf':set('defDEF'), 'X.otf':set('ABC')})

    def test_remove_property_value(self):
        style = parseStyle('background-image: url(b.png); background: black url(a.png) fixed')
        for prop in style.getProperties(all=True):
            remove_property_value(prop, lambda val:'png' in val.cssText)
        self.assertEqual('background: black fixed', style.cssText)

    def test_fallback_font_matching(self):
        def cf(id, weight='normal', style='normal', stretch='normal'):
            return {'id':id, 'font-weight':weight, 'font-style':style, 'font-stretch':stretch}
        fonts = [cf(1, '500', 'oblique', 'condensed'), cf(2, '300', 'italic', 'normal')]
        self.assertEqual(find_matching_font(fonts)['id'], 2)
        fonts = [cf(1, '500', 'oblique', 'normal'), cf(2, '300', 'italic', 'normal')]
        self.assertEqual(find_matching_font(fonts)['id'], 1)
        fonts = [cf(1, '500', 'oblique', 'normal'), cf(2, '200', 'oblique', 'normal')]
        self.assertEqual(find_matching_font(fonts)['id'], 1)
        fonts = [cf(1, '600', 'oblique', 'normal'), cf(2, '100', 'oblique', 'normal')]
        self.assertEqual(find_matching_font(fonts)['id'], 2)
        fonts = [cf(1, '600', 'oblique', 'normal'), cf(2, '100', 'oblique', 'normal')]
        self.assertEqual(find_matching_font(fonts, '500')['id'], 2)
        fonts = [cf(1, '600', 'oblique', 'normal'), cf(2, '100', 'oblique', 'normal')]
        self.assertEqual(find_matching_font(fonts, '600')['id'], 1)
