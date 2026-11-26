#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from kgcss import RuleType, StyleRule, condense_shorthands, expand_shorthand, longhands

if TYPE_CHECKING:
    import unittest
    from collections.abc import Iterable, Sequence

    from kgcss import Stylesheet

DEFAULTS = {
    'azimuth': 'center',
    'background-attachment': 'scroll',  # {{{
    'background-color': 'transparent',
    'background-image': 'none',
    'background-position': '0% 0%',
    'background-repeat': 'repeat',
    'border-bottom-color': 'currentColor',
    'border-bottom-style': 'none',
    'border-bottom-width': 'medium',
    'border-collapse': 'separate',
    'border-left-color': 'currentColor',
    'border-left-style': 'none',
    'border-left-width': 'medium',
    'border-right-color': 'currentColor',
    'border-right-style': 'none',
    'border-right-width': 'medium',
    'border-spacing': 0,
    'border-top-color': 'currentColor',
    'border-top-style': 'none',
    'border-top-width': 'medium',
    'bottom': 'auto',
    'caption-side': 'top',
    'clear': 'none',
    'clip': 'auto',
    'color': 'black',
    'content': 'normal',
    'counter-increment': 'none',
    'counter-reset': 'none',
    'cue-after': 'none',
    'cue-before': 'none',
    'cursor': 'auto',
    'direction': 'ltr',
    'display': 'inline',
    'elevation': 'level',
    'empty-cells': 'show',
    'float': 'none',
    'font-family': 'serif',
    'font-size': 'medium',
    'font-stretch': 'normal',
    'font-style': 'normal',
    'font-variant': 'normal',
    'font-weight': 'normal',
    'height': 'auto',
    'left': 'auto',
    'letter-spacing': 'normal',
    'line-height': 'normal',
    'list-style-image': 'none',
    'list-style-position': 'outside',
    'list-style-type': 'disc',
    'margin-bottom': 0,
    'margin-left': 0,
    'margin-right': 0,
    'margin-top': 0,
    'max-height': 'none',
    'max-width': 'none',
    'min-height': 0,
    'min-width': 0,
    'orphans': '2',
    'outline-color': 'invert',
    'outline-style': 'none',
    'outline-width': 'medium',
    'overflow': 'visible',
    'padding-bottom': 0,
    'padding-left': 0,
    'padding-right': 0,
    'padding-top': 0,
    'page-break-after': 'auto',
    'page-break-before': 'auto',
    'page-break-inside': 'auto',
    'pause-after': 0,
    'pause-before': 0,
    'pitch': 'medium',
    'pitch-range': '50',
    'play-during': 'auto',
    'position': 'static',
    'quotes': "'“' '”' '‘' '’'",
    'richness': '50',
    'right': 'auto',
    'speak': 'normal',
    'speak-header': 'once',
    'speak-numeral': 'continuous',
    'speak-punctuation': 'none',
    'speech-rate': 'medium',
    'stress': '50',
    'table-layout': 'auto',
    'text-align': 'auto',
    'text-decoration': 'none',
    'text-indent': 0,
    'text-shadow': 'none',
    'text-transform': 'none',
    'top': 'auto',
    'unicode-bidi': 'normal',
    'vertical-align': 'baseline',
    'visibility': 'visible',
    'voice-family': 'default',
    'volume': 'medium',
    'white-space': 'normal',
    'widows': '2',
    'width': 'auto',
    'word-spacing': 'normal',
    'z-index': 'auto',
}
# }}}

EDGES = ('top', 'right', 'bottom', 'left')
BORDER_PROPS = ('color', 'style', 'width')
# The initial values that expanding a shorthand gives the longhands it does not set
SHORTHAND_INITIAL_VALUES = {k: str(v) for k, v in DEFAULTS.items()}


def normalize_shorthand(name: str, value: str) -> dict[str, str] | None:
    """
    The longhands of the shorthand property name with the specified value:
    those the value sets and the initial values of the rest. None if name is
    not one of the shorthands that calibre expands (margin, padding, border,
    the border edges and parts, list-style and font) or the value is not valid
    for it, in which case the declaration should be left as it is.
    """
    # quirks_mode accepts lengths without units, as browsers do in quirks mode
    return expand_shorthand(name, value, initial=SHORTHAND_INITIAL_VALUES, quirks_mode=True)


def normalize_filter_css(props: Iterable[str]) -> set[str]:
    """The properties and the longhands of those that are shorthands"""
    ans = set(props)
    for prop in tuple(ans):
        ans.update(longhands(prop))
    return ans


def condense_sheet(sheet: Stylesheet) -> None:
    """Replace the longhands of margin, padding and border with shorthands
    where that does not change their meaning, in the style rules of sheet"""
    for rule in sheet.iter_rules(RuleType.STYLE):
        condense_shorthands(rule.style)


def test_normalization(return_tests: bool = False) -> unittest.TestSuite | None:  # {{{
    import unittest

    from kgcss import parse_stylesheet

    class TestNormalization(unittest.TestCase):
        longMessage = True
        maxDiff = None

        def test_font_normalization(self) -> None:
            font_composition = longhands('font')

            def font_dict(expected: dict[str, str]) -> dict[str, str]:
                ans = {k: SHORTHAND_INITIAL_VALUES[k] for k in font_composition}
                ans.update(expected)
                return ans

            for raw, expected in {
                'inherit': dict.fromkeys(font_composition, 'inherit'),
                '1.2pt/1.4 A_Font': {'font-family': 'A_Font', 'font-size': '1.2pt', 'line-height': '1.4'},
                '10% serif': {'font-family': 'serif', 'font-size': '10%'},
                '12px "My Font", serif': {'font-family': '"My Font", serif', 'font-size': '12px'},
                'normal 0.6em/135% arial,sans-serif': {
                    'font-family': 'arial, sans-serif',
                    'font-size': '0.6em',
                    'line-height': '135%',
                    'font-style': 'normal',
                },
                'bold italic large serif': {
                    'font-family': 'serif',
                    'font-weight': 'bold',
                    'font-style': 'italic',
                    'font-size': 'large',
                },
                'bold italic small-caps larger/normal serif': {
                    'font-family': 'serif',
                    'font-weight': 'bold',
                    'font-style': 'italic',
                    'font-size': 'larger',
                    'line-height': 'normal',
                    'font-variant': 'small-caps',
                },
                '2em A B': {'font-family': '"A B"', 'font-size': '2em'},
                # Keywords are case-insensitive (porting.md §6.7)
                'BOLD 12px serif': {'font-family': 'serif', 'font-weight': 'bold', 'font-size': '12px'},
                # default is quoted, as it is not a valid unquoted family name
                '12px x, "default"': {'font-family': 'x, "default"', 'font-size': '12px'},
                # Everything after the size is the family list
                '12px bold serif': {'font-family': '"bold serif"', 'font-size': '12px'},
                # The font shorthand also sets font-stretch (porting.md §6.9)
                'condensed 12pt a': {'font-stretch': 'condensed', 'font-size': '12pt', 'font-family': 'a'},
                # A legacy system font: the initial values
                'caption': {},
            }.items():
                self.assertDictEqual(font_dict(expected), normalize_shorthand('font', raw) or {}, raw)
            # Values that do not match the grammar of the font shorthand (CSS
            # Fonts 4) are not expanded: browsers ignore them
            for raw in ('some_font', 'bad font', '12px inherit', '12px 1.4 serif', 'var(--f)'):
                self.assertIsNone(normalize_shorthand('font', raw), raw)

        def test_border_normalization(self) -> None:
            def border_edge_dict(expected: dict[str, str], edge: str = 'right') -> dict[str, str]:
                ans = {f'border-{edge}-{x}': SHORTHAND_INITIAL_VALUES[f'border-{edge}-{x}'] for x in ('width', 'style', 'color')}
                for x, v in expected.items():
                    ans[f'border-{edge}-{x}'] = v
                return ans

            def border_dict(expected: dict[str, str]) -> dict[str, str]:
                ans: dict[str, str] = {}
                for edge in EDGES:
                    ans.update(border_edge_dict(expected, edge))
                return ans

            for raw, expected in {
                'solid 1px red': {'color': 'red', 'width': '1px', 'style': 'solid'},
                '1px': {'width': '1px'},
                '#aaa': {'color': '#aaa'},
                '2em groove': {'width': '2em', 'style': 'groove'},
                # Numbers without units are lengths, as in quirks mode
                '1 solid': {'width': '1', 'style': 'solid'},
            }.items():
                for edge in EDGES:
                    br = f'border-{edge}'
                    self.assertDictEqual(border_edge_dict(expected, edge), normalize_shorthand(br, raw) or {}, raw)

            for raw, expected in {
                'solid 1px red': {'color': 'red', 'width': '1px', 'style': 'solid'},
                '1px': {'width': '1px'},
                '#aaa': {'color': '#aaa'},
                'thin groove': {'width': 'thin', 'style': 'groove'},
                'inherit': {'color': 'inherit', 'width': 'inherit', 'style': 'inherit'},
            }.items():
                self.assertDictEqual(border_dict(expected), normalize_shorthand('border', raw) or {}, raw)

            for name, val in {
                'color': 'rgb(0, 1, 1)',
                'style': 'double',
                'width': '2px',
            }.items():
                self.assertDictEqual({f'border-{edge}-{name}': val for edge in EDGES}, normalize_shorthand('border-' + name, val) or {})

            # Invalid values are not expanded (porting.md §6.9)
            for name, raw in {
                'border': 'solid dotted',
                'border-top': 'foo',
                'border-color': 'red 1px',
                # A percentage is not a border width
                'border-width': '10%',
            }.items():
                self.assertIsNone(normalize_shorthand(name, raw), f'{name}: {raw}')

        def test_edge_normalization(self) -> None:
            def edge_dict(prefix: str, expected: Sequence[str]) -> dict[str, str]:
                return {f'{prefix}-{edge}': x for edge, x in zip(EDGES, expected)}

            for raw, expected in {
                '2px': ('2px', '2px', '2px', '2px'),
                '1em 2em': ('1em', '2em', '1em', '2em'),
                '1em 2em 3em': ('1em', '2em', '3em', '2em'),
                '1 2 3 4': ('1', '2', '3', '4'),
                'inherit': ('inherit',) * 4,
            }.items():
                for prefix in ('margin', 'padding'):
                    self.assertDictEqual(edge_dict(prefix, expected), normalize_shorthand(prefix, raw) or {}, raw)
            self.assertDictEqual(edge_dict('margin', ('-1em', 'auto', '-1em', 'auto')), normalize_shorthand('margin', '-1em auto') or {})
            # Invalid values are not expanded (porting.md §6.9)
            for name, raw in {
                'margin': '1px 2px 3px 4px 5px',
                'padding': '-1px',
                'padding-x': '1px',
                'color': 'red',
            }.items():
                self.assertIsNone(normalize_shorthand(name, raw), f'{name}: {raw}')

        def test_list_style_normalization(self) -> None:
            def ls_dict(expected: dict[str, str]) -> dict[str, str]:
                ans = {f'list-style-{x}': SHORTHAND_INITIAL_VALUES[f'list-style-{x}'] for x in ('type', 'position', 'image')}
                for k, v in expected.items():
                    ans[f'list-style-{k}'] = v
                return ans

            for raw, expected in {
                'url(http://www.example.com/images/list.png)': {'image': 'url(http://www.example.com/images/list.png)'},
                'inside square': {'position': 'inside', 'type': 'square'},
                'upper-roman url(img) outside': {'position': 'outside', 'type': 'upper-roman', 'image': 'url(img)'},
                'none': {'type': 'none', 'image': 'none'},
            }.items():
                self.assertDictEqual(ls_dict(expected), normalize_shorthand('list-style', raw) or {}, raw)
            self.assertIsNone(normalize_shorthand('list-style', 'none none none'))

        def test_filter_css_normalization(self) -> None:
            ae = self.assertEqual
            # The font shorthand also sets font-stretch
            ae({'font', 'font-style', 'font-variant', 'font-weight', 'font-stretch', 'font-size', 'line-height', 'font-family'}, normalize_filter_css({'font'}))
            for p in ('margin', 'padding'):
                ae({p} | {p + '-' + x for x in EDGES}, normalize_filter_css({p}))
            bvals = {f'border-{edge}-{x}' for edge in EDGES for x in BORDER_PROPS}
            ae(bvals | {'border'}, normalize_filter_css({'border'}))
            for x in BORDER_PROPS:
                sbvals = {f'border-{e}-{x}' for e in EDGES}
                ae(sbvals | {f'border-{x}'}, normalize_filter_css({f'border-{x}'}))
            for e in EDGES:
                sbvals = {f'border-{e}-{x}' for x in BORDER_PROPS}
                ae(sbvals | {f'border-{e}'}, normalize_filter_css({f'border-{e}'}))
            ae(
                {'list-style', 'list-style-image', 'list-style-type', 'list-style-position'},
                normalize_filter_css({'list-style'}),
            )
            ae({'color', 'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left'}, normalize_filter_css(('color', 'margin')))

        def condensed(self, css: str) -> str:
            sheet = parse_stylesheet(css)
            condense_sheet(sheet)
            return sheet.css_text

        def test_edge_condensation(self) -> None:
            for s, v in {
                (1, 1, 3): None,
                (1, 2, 3, 4): '2pt 3pt 4pt 1pt',
                (1, 2, 3, 2): '2pt 3pt 2pt 1pt',
                (1, 2, 1, 3): '2pt 1pt 3pt',
                (1, 2, 1, 2): '2pt 1pt',
                (1, 1, 1, 1): '1pt',
                ('2%', '2%', '2%', '2%'): '2%',
                tuple('0 0 0 0'.split()): '0',
            }.items():
                for prefix in ('margin', 'padding'):
                    css = {f'{prefix}-{x}': str(y) + 'pt' if isinstance(y, int) else y for x, y in zip(('left', 'top', 'right', 'bottom'), s)}
                    decls = '; '.join(f'{k}:{v}' for k, v in css.items())
                    sheet = parse_stylesheet(f'p {{ {decls} }}')
                    condense_sheet(sheet)
                    rule = sheet.rules[0]
                    assert isinstance(rule, StyleRule)
                    style = rule.style
                    self.assertEqual(v or '', style.get_value(prefix))
                    if v is not None:
                        self.assertEqual([prefix], style.keys())

        def test_border_condensation(self) -> None:
            vals = 'red solid 5px'
            css = '; '.join(f'border-{edge}-{p}: {v}' for edge in EDGES for p, v in zip(BORDER_PROPS, vals.split()))
            self.assertEqual(self.condensed(f'p {{ {css} }}'), f'p {{\n  border: {vals};\n}}')
            css = '; '.join(f'border-top-{p}: {v}' for p, v in zip(BORDER_PROPS, vals.split()))
            self.assertEqual(self.condensed(f'p {{ {css} }}'), f'p {{\n  border-top: {vals};\n}}')
            css += ';' + '; '.join(
                f'border-{edge}-{p}: {v}' for edge in ('right', 'left', 'bottom') for p, v in zip(BORDER_PROPS, vals.replace('red', 'green').split())
            )
            sheet = parse_stylesheet(f'p {{ {css} }}')
            condense_sheet(sheet)
            rule = sheet.rules[0]
            assert isinstance(rule, StyleRule)
            style = rule.style
            self.assertEqual(len(style), 4)
            self.assertEqual(style['border-top'], vals)
            self.assertEqual(style['border-left'], vals.replace('red', 'green'))

        def test_sheet_condensation(self) -> None:
            edges = 'margin-top: 1px; margin-right: 1px; margin-bottom: 1px; margin-left: 1px'
            # Style rules at any depth are condensed
            self.assertEqual(
                self.condensed(f'@media screen {{ @supports (display: grid) {{ p {{ {edges} }} }} }}'),
                '@media screen {\n  @supports (display: grid) {\n    p {\n      margin: 1px;\n    }\n  }\n}',
            )
            # Not when that could change the meaning: !important, or an
            # overlapping shorthand
            css = f'p {{\n  {edges.replace("; ", " !important;\n  ")} !important;\n}}'
            self.assertEqual(self.condensed(css), css)
            css = f'p {{\n  margin: 0;\n  {edges.replace("; ", ";\n  ")};\n}}'
            self.assertEqual(self.condensed(css), css)

    tests = unittest.defaultTestLoader.loadTestsFromTestCase(TestNormalization)
    if return_tests:
        return tests
    unittest.TextTestRunner(verbosity=4).run(tests)
    return None


# }}}

if __name__ == '__main__':
    test_normalization()
