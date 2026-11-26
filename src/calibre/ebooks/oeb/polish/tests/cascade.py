#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import TYPE_CHECKING, TypedDict

from kgcss import RuleType, parse_style

from calibre.constants import iswindows
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.cascade import DEFAULTS, iterrules, resolve_styles
from calibre.ebooks.oeb.polish.container import ContainerBase, href_to_name
from calibre.ebooks.oeb.polish.embed import find_matching_font
from calibre.ebooks.oeb.polish.replace import remove_links_in_declaration
from calibre.ebooks.oeb.polish.stats import StatsCollector, font_keys, normalize_font_properties, prepare_font_rule
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.utils.icu import lower as icu_lower
from calibre.utils.logging import Log, Stream

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from kgcss import Rule, Select
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.cascade import Values
    from calibre.ebooks.oeb.polish.container import ParsedObject

FontSpec = TypedDict(
    'FontSpec',
    {
        'font-weight': str,
        'font-style': str,
        'font-stretch': str,
        'font-family': str | list[str],
        'src': str,
        'text': set[str],
    },
    total=False,
)


class VirtualContainer(ContainerBase):
    tweak_mode = True

    def __init__(self, files: dict[str, str | bytes]) -> None:
        s = Stream()
        self.log_stream = s.stream
        log = Log()
        log.outputs = [s]
        self.opf_version_parsed = (2, 0, 0)
        ContainerBase.__init__(self, log=log)
        self.mime_map = {k: self.guess_type(k) for k in files}
        self.files = files

    def has_name(self, name: str) -> bool:
        return name in self.mime_map

    def href_to_name(self, href: str, base: str | None = None) -> str | None:
        return href_to_name(href, ('C:\\root' if iswindows else '/root'), base)

    def parsed_object(self, name: str) -> ParsedObject:
        if name not in self.parsed_cache:
            mt = self.mime_map[name]
            f = self.files[name]
            if mt in OEB_STYLES:
                self.parsed_cache[name] = self.parse_stylesheet(f, name)
            elif mt in OEB_DOCS:
                self.parsed_cache[name] = self.parse_xhtml(f, name)
            else:
                self.parsed_cache[name] = f if isinstance(f, bytes) else f.encode('utf-8')
        return self.parsed_cache[name]

    @property
    def spine_names(self) -> Iterator[tuple[str, bool]]:
        for name in sorted(self.mime_map):
            if self.mime_map[name] in OEB_DOCS:
                yield name, True


class CascadeTest(BaseTest):
    def test_iterrules(self) -> None:
        def get_rules(
            files: dict[str, str | bytes], name: str = 'x/one.css', l: int = 1, rule_type: RuleType | None = None
        ) -> tuple[tuple[tuple[Rule, str, int], ...], VirtualContainer]:
            c = VirtualContainer(files)
            rules = tuple(iterrules(c, name, rule_type=rule_type))
            self.assertEqual(len(rules), l)
            return rules, c

        get_rules({'x/one.css': '@import "../two.css";', 'two.css': 'body { color: red; }'})
        get_rules({'x/one.css': '@import "../two.css" screen;', 'two.css': 'body { color: red; }'})
        get_rules({'x/one.css': '@import "../two.css" xyz;', 'two.css': 'body { color: red; }'}, l=0)
        get_rules({'x/one.css': '@import "../two.css";', 'two.css': 'body { color: red; }'}, l=0, rule_type=RuleType.FONT_FACE)
        get_rules({'x/one.css': '@import "../two.css";', 'two.css': 'body { color: red; }'}, rule_type=RuleType.STYLE)
        get_rules({'x/one.css': '@media screen { body { color: red; } }'})
        get_rules({'x/one.css': '@media xyz { body { color: red; } }'}, l=0)
        c = get_rules({'x/one.css': '@import "../two.css";', 'two.css': '@import "x/one.css"; body { color: red; }'})[1]
        self.assertIn('Recursive import', c.log_stream.getvalue())

    def test_resolve_styles(self) -> None:

        def test_property(
            select: Select[_Element],
            resolve_property: Callable[[_Element, str], Values | None],
            selector: str,
            name: str,
            val: str | tuple[str, ...] | None = None,
        ) -> None:
            elem = next(select(selector))
            ans = resolve_property(elem, name)
            assert ans is not None  # all properties used in this test have defaults
            if val is None:
                val = str(DEFAULTS[name])
            self.assertEqual(val, ans.css_text)

        def test_pseudo_property(
            select: Select[_Element],
            resolve_pseudo_property: Callable[..., Values | None],
            selector: str,
            prop: str,
            name: str,
            val: str | None = None,
            abort_on_missing: bool = False,
        ) -> None:
            elem = next(select(selector))
            ans = resolve_pseudo_property(elem, prop, name, abort_on_missing=abort_on_missing)
            if abort_on_missing:
                if val is None:
                    self.assertTrue(ans is None)
                    return
            if val is None:
                val = str(DEFAULTS[name])
            assert ans is not None  # only None when abort_on_missing is True, handled above
            self.assertEqual(val, ans.css_text)

        def get_maps(html: str, styles: str | None = None, pseudo: bool = False) -> partial[None]:
            html = f'<html><head><link href="styles.css"></head><body>{html}</body></html>'
            c = VirtualContainer({
                'index.html': html,
                'styles.css': styles or 'body { color: red; font-family: "Kovid Goyal", sans-serif }',
            })
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

        t = get_maps('<p>x<b>y</b><i>z</i></p>', 'p { font-family: Times   New Roman, serif } b { font-family: inherit } i { font-family: "inherit" }')
        t('p', 'font-family', ('"Times New Roman"', 'serif'))
        # The CSS-wide keywords are not turned into family names
        t('b', 'font-family', 'inherit')
        t('i', 'font-family', '"inherit"')
        # An invalid font shorthand is ignored, it does not reset the font
        t = get_maps('<p>x</p>', 'p { font-family: X; font-weight: bold; font: some_font }')
        t('p', 'font-family', 'X')
        t('p', 'font-weight', 'bold')
        t = get_maps('<p>x</p>', 'p { font-family: X; font: 12px Y }')
        t('p', 'font-family', 'Y')

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

    def test_font_stats(self) -> None:
        embeds = '@font-face { font-family: X; src: url(X.otf) }\n@font-face { font-family: X; src: url(XB.otf); font-weight: bold }'

        def get_stats(html: str, *fonts: dict[str, str]) -> StatsCollector:
            styles: list[str] = []
            html = f'<html><head><link href="styles.css"></head><body>{html}</body></html>'
            files: dict[str, str | bytes] = {'index.html': html, 'X.otf': b'xxx', 'XB.otf': b'xbxb'}
            for font in fonts:
                styles.append('@font-face {')
                for k, v in font.items():
                    if k == 'src':
                        files[v] = b'xxx'
                        v = f'url({v})'
                    styles.append(f'{k} : {v};')
                styles.append('}\n')
            files['styles.css'] = embeds + '\n'.join(styles)
            c = VirtualContainer(files)
            return StatsCollector(c, do_embed=True)

        def font(family: str, weight: str | None = None, style: str | None = None) -> FontSpec:
            f: FontSpec = {}
            if weight is not None:
                f['font-weight'] = weight
            if style is not None:
                f['font-style'] = style
            f = normalize_font_properties(f)
            f['font-family'] = [family]
            return f

        def font_rule(src: str, *args: str, **kw: str) -> Mapping[str, object]:
            ans = font(*args, **kw)
            ans['font-family'] = list(map(icu_lower, ans['font-family']))
            prepare_font_rule(ans)
            ans['src'] = src
            return ans

        def fkey(*args: str, **kw: str) -> frozenset[tuple[str, object]]:
            f = font(*args, **kw)
            f['font-family'] = icu_lower(f['font-family'][0])
            return frozenset((k, v) for k, v in f.items() if k in font_keys)

        def fu(text: str, *args: str, **kw: str) -> tuple[frozenset[tuple[str, object]], FontSpec]:
            key = fkey(*args, **kw)
            val = font(*args, **kw)
            val['text'] = set(text)
            val['font-family'] = val['font-family'][0]
            return key, val

        s = get_stats('<p style="font-family: X">abc<b>d\nef</b><i>ghi</i></p><p style="font-family: U">u</p>')
        # The normal font must include ghi as it will be used to simulate
        # italic by most rendering engines when the italic font is missing
        self.assertEqual(s.font_stats, {'XB.otf': set('def'), 'X.otf': set('abcghi')})
        self.assertEqual(s.font_spec_map, {'index.html': set('XU')})
        self.assertEqual(s.all_font_rules, {'X.otf': font_rule('X.otf', 'X'), 'XB.otf': font_rule('XB.otf', 'X', 'bold')})
        self.assertEqual(set(s.font_rule_map), {'index.html'})
        self.assertEqual(s.font_rule_map['index.html'], [font_rule('X.otf', 'X'), font_rule('XB.otf', 'X', 'bold')])
        self.assertEqual(set(s.font_usage_map), {'index.html'})
        self.assertEqual(
            s.font_usage_map['index.html'],
            dict([fu('abc', 'X'), fu('def', 'X', weight='bold'), fu('ghi', 'X', style='italic'), fu('u', 'U')]),
        )

        s = get_stats('<p style="font-family: X; text-transform:uppercase">abc</p><b style="font-family: X; font-variant: small-caps">d\nef</b>')
        self.assertEqual(s.font_stats, {'XB.otf': set('defDEF'), 'X.otf': set('ABC')})
        # Rules in @supports and the like are used, values with var() are
        # not known, so the inherited font is used
        s = get_stats('<style>@supports (display: grid) { p { font-family: X } } i { font-family: var(--f, X) }</style><p>ab<i>c</i></p>')
        self.assertEqual(s.font_stats, {'X.otf': set('abc'), 'XB.otf': set()})
        # The content of ::before and ::after is counted
        s = get_stats('<style>p::before { content: "xy" } p::after { content: "z" counter(x) \'w\' }</style><p style="font-family: X">a</p>')
        self.assertEqual(s.font_stats, {'X.otf': set('xyazw'), 'XB.otf': set()})
        s = get_stats('<style>.fl::first-line { font-family: X }</style><p class="fl">abc<b>def</b></p>')
        # Technically def should not be needed in X but that is hard to achieve
        self.assertEqual(s.font_stats, {'XB.otf': set('def'), 'X.otf': set('abcdef')})

    def test_remove_links_in_declaration(self) -> None:
        style = parse_style('background-image: url(b.png); background: black url(a.png) fixed; list-style-image: url(c.gif)')
        self.assertTrue(remove_links_in_declaration(lambda href: href, style, lambda name, href, frag: 'png' in href))
        self.assertEqual('background: black fixed; list-style-image: url(c.gif)', style.to_css(single_line=True))
        self.assertFalse(remove_links_in_declaration(lambda href: href, style, lambda name, href, frag: 'png' in href))

    def test_fallback_font_matching(self) -> None:
        def cf(id: int, weight: str = 'normal', style: str = 'normal', stretch: str = 'normal') -> dict[str, int | str]:
            return {'id': id, 'font-weight': weight, 'font-style': style, 'font-stretch': stretch}

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
