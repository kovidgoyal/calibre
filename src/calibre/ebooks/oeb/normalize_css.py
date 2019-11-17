#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import numbers
from functools import wraps

from css_parser.css import PropertyValue
from css_parser import profile as cssprofiles, CSSParser
from tinycss.fonts3 import parse_font, serialize_font_family
from calibre.ebooks.oeb.base import css_text
from polyglot.builtins import iteritems, string_or_bytes, unicode_type, zip

DEFAULTS = {'azimuth': 'center', 'background-attachment': 'scroll',  # {{{
            'background-color': 'transparent', 'background-image': 'none',
            'background-position': '0% 0%', 'background-repeat': 'repeat',
            'border-bottom-color': 'currentColor', 'border-bottom-style':
            'none', 'border-bottom-width': 'medium', 'border-collapse':
            'separate', 'border-left-color': 'currentColor',
            'border-left-style': 'none', 'border-left-width': 'medium',
            'border-right-color': 'currentColor', 'border-right-style': 'none',
            'border-right-width': 'medium', 'border-spacing': 0,
            'border-top-color': 'currentColor', 'border-top-style': 'none',
            'border-top-width': 'medium', 'bottom': 'auto', 'caption-side':
            'top', 'clear': 'none', 'clip': 'auto', 'color': 'black',
            'content': 'normal', 'counter-increment': 'none', 'counter-reset':
            'none', 'cue-after': 'none', 'cue-before': 'none', 'cursor':
            'auto', 'direction': 'ltr', 'display': 'inline', 'elevation':
            'level', 'empty-cells': 'show', 'float': 'none', 'font-family':
            'serif', 'font-size': 'medium', 'font-stretch': 'normal', 'font-style': 'normal',
            'font-variant': 'normal', 'font-weight': 'normal', 'height':
            'auto', 'left': 'auto', 'letter-spacing': 'normal', 'line-height':
            'normal', 'list-style-image': 'none', 'list-style-position':
            'outside', 'list-style-type': 'disc', 'margin-bottom': 0,
            'margin-left': 0, 'margin-right': 0, 'margin-top': 0, 'max-height':
            'none', 'max-width': 'none', 'min-height': 0, 'min-width': 0,
            'orphans': '2', 'outline-color': 'invert', 'outline-style': 'none',
            'outline-width': 'medium', 'overflow': 'visible', 'padding-bottom':
            0, 'padding-left': 0, 'padding-right': 0, 'padding-top': 0,
            'page-break-after': 'auto', 'page-break-before': 'auto',
            'page-break-inside': 'auto', 'pause-after': 0, 'pause-before': 0,
            'pitch': 'medium', 'pitch-range': '50', 'play-during': 'auto',
            'position': 'static', 'quotes': u"'“' '”' '‘' '’'", 'richness':
            '50', 'right': 'auto', 'speak': 'normal', 'speak-header': 'once',
            'speak-numeral': 'continuous', 'speak-punctuation': 'none',
            'speech-rate': 'medium', 'stress': '50', 'table-layout': 'auto',
            'text-align': 'auto', 'text-decoration': 'none', 'text-indent': 0,
            'text-shadow': 'none', 'text-transform': 'none', 'top': 'auto',
            'unicode-bidi': 'normal', 'vertical-align': 'baseline',
            'visibility': 'visible', 'voice-family': 'default', 'volume':
            'medium', 'white-space': 'normal', 'widows': '2', 'width': 'auto',
            'word-spacing': 'normal', 'z-index': 'auto'}
# }}}

EDGES = ('top', 'right', 'bottom', 'left')
BORDER_PROPS = ('color', 'style', 'width')


def normalize_edge(name, cssvalue):
    style = {}
    if isinstance(cssvalue, PropertyValue):
        primitives = [css_text(v) for v in cssvalue]
    else:
        primitives = [css_text(cssvalue)]
    if len(primitives) == 1:
        value, = primitives
        values = (value, value, value, value)
    elif len(primitives) == 2:
        vert, horiz = primitives
        values = (vert, horiz, vert, horiz)
    elif len(primitives) == 3:
        top, horiz, bottom = primitives
        values = (top, horiz, bottom, horiz)
    else:
        values = primitives[:4]
    if '-' in name:
        l, _, r = name.partition('-')
        for edge, value in zip(EDGES, values):
            style['%s-%s-%s' % (l, edge, r)] = value
    else:
        for edge, value in zip(EDGES, values):
            style['%s-%s' % (name, edge)] = value
    return style


def simple_normalizer(prefix, names, check_inherit=True):
    composition = tuple('%s-%s' %(prefix, n) for n in names)

    @wraps(normalize_simple_composition)
    def wrapper(name, cssvalue):
        return normalize_simple_composition(name, cssvalue, composition, check_inherit=check_inherit)
    return wrapper


def normalize_simple_composition(name, cssvalue, composition, check_inherit=True):
    if check_inherit and css_text(cssvalue) == 'inherit':
        style = {k:'inherit' for k in composition}
    else:
        style = {k:DEFAULTS[k] for k in composition}
        try:
            primitives = [css_text(v) for v in cssvalue]
        except TypeError:
            primitives = [css_text(cssvalue)]
        while primitives:
            value = primitives.pop()
            for key in composition:
                if cssprofiles.validate(key, value):
                    style[key] = value
                    break
    return style


font_composition = ('font-style', 'font-variant', 'font-weight', 'font-size', 'line-height', 'font-family')


def normalize_font(cssvalue, font_family_as_list=False):
    # See https://developer.mozilla.org/en-US/docs/Web/CSS/font
    composition = font_composition
    val = css_text(cssvalue)
    if val == 'inherit':
        ans = {k:'inherit' for k in composition}
    elif val in {'caption', 'icon', 'menu', 'message-box', 'small-caption', 'status-bar'}:
        ans = {k:DEFAULTS[k] for k in composition}
    else:
        ans = {k:DEFAULTS[k] for k in composition}
        ans.update(parse_font(val))
    if font_family_as_list:
        if isinstance(ans['font-family'], string_or_bytes):
            ans['font-family'] = [x.strip() for x in ans['font-family'].split(',')]
    else:
        if not isinstance(ans['font-family'], string_or_bytes):
            ans['font-family'] = serialize_font_family(ans['font-family'])
    return ans


def normalize_border(name, cssvalue):
    style = normalizers['border-' + EDGES[0]]('border-' + EDGES[0], cssvalue)
    vals = style.copy()
    for edge in EDGES[1:]:
        style.update({k.replace(EDGES[0], edge):v for k, v in iteritems(vals)})
    return style


normalizers = {
    'list-style': simple_normalizer('list-style', ('type', 'position', 'image')),
    'font': lambda prop, v: normalize_font(v),
    'border': normalize_border,
}

for x in ('margin', 'padding', 'border-style', 'border-width', 'border-color'):
    normalizers[x] = normalize_edge

for x in EDGES:
    name = 'border-' + x
    normalizers[name] = simple_normalizer(name, BORDER_PROPS, check_inherit=False)

SHORTHAND_DEFAULTS = {
    'margin': '0', 'padding': '0', 'border-style': 'none', 'border-width': '0', 'border-color': 'currentColor',
    'border':'none', 'border-left': 'none', 'border-right':'none', 'border-top': 'none', 'border-bottom': 'none',
    'list-style': 'inherit', 'font': 'inherit',
}

_safe_parser = None


def safe_parser():
    global _safe_parser
    if _safe_parser is None:
        import logging
        _safe_parser = CSSParser(loglevel=logging.CRITICAL, validate=False)
    return _safe_parser


def normalize_filter_css(props):
    ans = set()
    p = safe_parser()
    for prop in props:
        n = normalizers.get(prop, None)
        ans.add(prop)
        if n is not None and prop in SHORTHAND_DEFAULTS:
            dec = p.parseStyle('%s: %s' % (prop, SHORTHAND_DEFAULTS[prop]))
            cssvalue = dec.getPropertyCSSValue(dec.item(0))
            ans |= set(n(prop, cssvalue))
    return ans


def condense_edge(vals):
    edges = {x.name.rpartition('-')[-1]:x.value for x in vals}
    if len(edges) != 4 or set(edges) != {'left', 'top', 'right', 'bottom'}:
        return
    ce = {}
    for (x, y) in [('left', 'right'), ('top', 'bottom')]:
        if edges[x] == edges[y]:
            ce[x] = edges[x]
        else:
            ce[x], ce[y] = edges[x], edges[y]
    if len(ce) == 4:
        return ' '.join(ce[x] for x in ('top', 'right', 'bottom', 'left'))
    if len(ce) == 3:
        if 'right' in ce:
            return ' '.join(ce[x] for x in ('top', 'right', 'top', 'left'))
        return ' '.join(ce[x] for x in ('top', 'left', 'bottom'))
    if len(ce) == 2:
        if ce['top'] == ce['left']:
            return ce['top']
        return ' '.join(ce[x] for x in ('top', 'left'))


def simple_condenser(prefix, func):
    @wraps(func)
    def condense_simple(style, props):
        cp = func(props)
        if cp is not None:
            for prop in props:
                style.removeProperty(prop.name)
            style.setProperty(prefix, cp)
    return condense_simple


def condense_border(style, props):
    prop_map = {p.name:p for p in props}
    edge_vals = []
    for edge in EDGES:
        name = 'border-%s' % edge
        vals = []
        for prop in BORDER_PROPS:
            x = prop_map.get('%s-%s' % (name, prop), None)
            if x is not None:
                vals.append(x)
        if len(vals) == 3:
            for prop in vals:
                style.removeProperty(prop.name)
            style.setProperty(name, ' '.join(x.value for x in vals))
            prop_map[name] = style.getProperty(name)
        x = prop_map.get(name, None)
        if x is not None:
            edge_vals.append(x)
    if len(edge_vals) == 4 and len({x.value for x in edge_vals}) == 1:
        for prop in edge_vals:
            style.removeProperty(prop.name)
        style.setProperty('border', edge_vals[0].value)


condensers = {'margin': simple_condenser('margin', condense_edge), 'padding': simple_condenser('padding', condense_edge), 'border': condense_border}


def condense_rule(style):
    expanded = {'margin-':[], 'padding-':[], 'border-':[]}
    for prop in style.getProperties():
        for x in expanded:
            if prop.name and prop.name.startswith(x):
                expanded[x].append(prop)
                break
    for prefix, vals in iteritems(expanded):
        if len(vals) > 1 and {x.priority for x in vals} == {''}:
            condensers[prefix[:-1]](style, vals)


def condense_sheet(sheet):
    for rule in sheet.cssRules:
        if rule.type == rule.STYLE_RULE:
            condense_rule(rule.style)


def test_normalization(return_tests=False):  # {{{
    import unittest
    from css_parser import parseStyle
    from itertools import product

    class TestNormalization(unittest.TestCase):
        longMessage = True
        maxDiff = None

        def test_font_normalization(self):
            def font_dict(expected):
                ans = {k:DEFAULTS[k] for k in font_composition} if expected else {}
                ans.update(expected)
                return ans

            for raw, expected in iteritems({
                'some_font': {'font-family':'some_font'}, 'inherit':{k:'inherit' for k in font_composition},
                '1.2pt/1.4 A_Font': {'font-family':'A_Font', 'font-size':'1.2pt', 'line-height':'1.4'},
                'bad font': {'font-family':'"bad font"'}, '10% serif': {'font-family':'serif', 'font-size':'10%'},
                '12px "My Font", serif': {'font-family':'"My Font", serif', 'font-size': '12px'},
                'normal 0.6em/135% arial,sans-serif': {'font-family': 'arial, sans-serif', 'font-size': '0.6em', 'line-height':'135%', 'font-style':'normal'},
                'bold italic large serif': {'font-family':'serif', 'font-weight':'bold', 'font-style':'italic', 'font-size':'large'},
                'bold italic small-caps larger/normal serif':
                {'font-family':'serif', 'font-weight':'bold', 'font-style':'italic', 'font-size':'larger',
                 'line-height':'normal', 'font-variant':'small-caps'},
                '2em A B': {'font-family': '"A B"', 'font-size': '2em'},
            }):
                val = tuple(parseStyle('font: %s' % raw, validate=False))[0].cssValue
                style = normalizers['font']('font', val)
                self.assertDictEqual(font_dict(expected), style, raw)

        def test_border_normalization(self):
            def border_edge_dict(expected, edge='right'):
                ans = {'border-%s-%s' % (edge, x): DEFAULTS['border-%s-%s' % (edge, x)] for x in ('style', 'width', 'color')}
                for x, v in iteritems(expected):
                    ans['border-%s-%s' % (edge, x)] = v
                return ans

            def border_dict(expected):
                ans = {}
                for edge in EDGES:
                    ans.update(border_edge_dict(expected, edge))
                return ans

            def border_val_dict(expected, val='color'):
                ans = {'border-%s-%s' % (edge, val): DEFAULTS['border-%s-%s' % (edge, val)] for edge in EDGES}
                for edge in EDGES:
                    ans['border-%s-%s' % (edge, val)] = expected
                return ans

            for raw, expected in iteritems({
                'solid 1px red': {'color':'red', 'width':'1px', 'style':'solid'},
                '1px': {'width': '1px'}, '#aaa': {'color': '#aaa'},
                '2em groove': {'width':'2em', 'style':'groove'},
            }):
                for edge in EDGES:
                    br = 'border-%s' % edge
                    val = tuple(parseStyle('%s: %s' % (br, raw), validate=False))[0].cssValue
                    self.assertDictEqual(border_edge_dict(expected, edge), normalizers[br](br, val))

            for raw, expected in iteritems({
                'solid 1px red': {'color':'red', 'width':'1px', 'style':'solid'},
                '1px': {'width': '1px'}, '#aaa': {'color': '#aaa'},
                'thin groove': {'width':'thin', 'style':'groove'},
            }):
                val = tuple(parseStyle('%s: %s' % ('border', raw), validate=False))[0].cssValue
                self.assertDictEqual(border_dict(expected), normalizers['border']('border', val))

            for name, val in iteritems({
                'width': '10%', 'color': 'rgb(0, 1, 1)', 'style': 'double',
            }):
                cval = tuple(parseStyle('border-%s: %s' % (name, val), validate=False))[0].cssValue
                self.assertDictEqual(border_val_dict(val, name), normalizers['border-'+name]('border-'+name, cval))

        def test_edge_normalization(self):
            def edge_dict(prefix, expected):
                return {'%s-%s' % (prefix, edge) : x for edge, x in zip(EDGES, expected)}
            for raw, expected in iteritems({
                '2px': ('2px', '2px', '2px', '2px'),
                '1em 2em': ('1em', '2em', '1em', '2em'),
                '1em 2em 3em': ('1em', '2em', '3em', '2em'),
                '1 2 3 4': ('1', '2', '3', '4'),
            }):
                for prefix in ('margin', 'padding'):
                    cval = tuple(parseStyle('%s: %s' % (prefix, raw), validate=False))[0].cssValue
                    self.assertDictEqual(edge_dict(prefix, expected), normalizers[prefix](prefix, cval))

        def test_list_style_normalization(self):
            def ls_dict(expected):
                ans = {'list-style-%s' % x : DEFAULTS['list-style-%s' % x] for x in ('type', 'image', 'position')}
                for k, v in iteritems(expected):
                    ans['list-style-%s' % k] = v
                return ans
            for raw, expected in iteritems({
                'url(http://www.example.com/images/list.png)': {'image': 'url(http://www.example.com/images/list.png)'},
                'inside square': {'position':'inside', 'type':'square'},
                'upper-roman url(img) outside': {'position':'outside', 'type':'upper-roman', 'image':'url(img)'},
            }):
                cval = tuple(parseStyle('list-style: %s' % raw, validate=False))[0].cssValue
                self.assertDictEqual(ls_dict(expected), normalizers['list-style']('list-style', cval))

        def test_filter_css_normalization(self):
            ae = self.assertEqual
            ae({'font'} | set(font_composition), normalize_filter_css({'font'}))
            for p in ('margin', 'padding'):
                ae({p} | {p + '-' + x for x in EDGES}, normalize_filter_css({p}))
            bvals = {'border-%s-%s' % (edge, x) for edge in EDGES for x in BORDER_PROPS}
            ae(bvals | {'border'}, normalize_filter_css({'border'}))
            for x in BORDER_PROPS:
                sbvals = {'border-%s-%s' % (e, x) for e in EDGES}
                ae(sbvals | {'border-%s' % x}, normalize_filter_css({'border-%s' % x}))
            for e in EDGES:
                sbvals = {'border-%s-%s' % (e, x) for x in BORDER_PROPS}
                ae(sbvals | {'border-%s' % e}, normalize_filter_css({'border-%s' % e}))
            ae({'list-style', 'list-style-image', 'list-style-type', 'list-style-position'}, normalize_filter_css({'list-style'}))

        def test_edge_condensation(self):
            for s, v in iteritems({
                (1, 1, 3) : None,
                (1, 2, 3, 4) : '2pt 3pt 4pt 1pt',
                (1, 2, 3, 2) : '2pt 3pt 2pt 1pt',
                (1, 2, 1, 3) : '2pt 1pt 3pt',
                (1, 2, 1, 2) : '2pt 1pt',
                (1, 1, 1, 1) : '1pt',
                ('2%', '2%', '2%', '2%') : '2%',
                tuple('0 0 0 0'.split()) : '0',
            }):
                for prefix in ('margin', 'padding'):
                    css = {'%s-%s' % (prefix, x) : unicode_type(y)+'pt' if isinstance(y, numbers.Number) else y
                            for x, y in zip(('left', 'top', 'right', 'bottom'), s)}
                    css = '; '.join(('%s:%s' % (k, v) for k, v in iteritems(css)))
                    style = parseStyle(css)
                    condense_rule(style)
                    val = getattr(style.getProperty(prefix), 'value', None)
                    self.assertEqual(v, val)
                    if val is not None:
                        for edge in EDGES:
                            self.assertFalse(getattr(style.getProperty('%s-%s' % (prefix, edge)), 'value', None))

        def test_border_condensation(self):
            vals = 'red solid 5px'
            css = '; '.join('border-%s-%s: %s' % (edge, p, v) for edge in EDGES for p, v in zip(BORDER_PROPS, vals.split()))
            style = parseStyle(css)
            condense_rule(style)
            for e, p in product(EDGES, BORDER_PROPS):
                self.assertFalse(style.getProperty('border-%s-%s' % (e, p)))
                self.assertFalse(style.getProperty('border-%s' % e))
                self.assertFalse(style.getProperty('border-%s' % p))
            self.assertEqual(style.getProperty('border').value, vals)
            css = '; '.join('border-%s-%s: %s' % (edge, p, v) for edge in ('top',) for p, v in zip(BORDER_PROPS, vals.split()))
            style = parseStyle(css)
            condense_rule(style)
            self.assertEqual(css_text(style), 'border-top: %s' % vals)
            css += ';' + '; '.join('border-%s-%s: %s' % (edge, p, v) for edge in ('right', 'left', 'bottom') for p, v in
                             zip(BORDER_PROPS, vals.replace('red', 'green').split()))
            style = parseStyle(css)
            condense_rule(style)
            self.assertEqual(len(style.getProperties()), 4)
            self.assertEqual(style.getProperty('border-top').value, vals)
            self.assertEqual(style.getProperty('border-left').value, vals.replace('red', 'green'))

    tests = unittest.defaultTestLoader.loadTestsFromTestCase(TestNormalization)
    if return_tests:
        return tests
    unittest.TextTestRunner(verbosity=4).run(tests)
# }}}


if __name__ == '__main__':
    test_normalization()
