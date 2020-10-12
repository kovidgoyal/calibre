#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import numbers
from collections import OrderedDict
from polyglot.builtins import iteritems


class Inherit(object):

    def __eq__(self, other):
        return other is self

    def __hash__(self):
        return id(self)

    def __lt__(self, other):
        return False

    def __gt__(self, other):
        return other is not self

    def __ge__(self, other):
        if self is other:
            return True
        return True

    def __le__(self, other):
        if self is other:
            return True
        return False


inherit = Inherit()


def binary_property(parent, name, XPath, get):
    vals = XPath('./w:%s' % name)(parent)
    if not vals:
        return inherit
    val = get(vals[0], 'w:val', 'on')
    return True if val in {'on', '1', 'true'} else False


def simple_color(col, auto='currentColor'):
    if not col or col == 'auto' or len(col) != 6:
        return auto
    return '#'+col


def simple_float(val, mult=1.0):
    try:
        return float(val) * mult
    except (ValueError, TypeError, AttributeError, KeyError):
        pass


def twips(val, mult=0.05):
    ''' Parse val as either a pure number representing twentieths of a point or a number followed by the suffix pt, representing pts.'''
    try:
        return float(val) * mult
    except (ValueError, TypeError, AttributeError, KeyError):
        if val and val.endswith('pt') and mult == 0.05:
            return twips(val[:-2], mult=1.0)


LINE_STYLES = {  # {{{
    'basicBlackDashes': 'dashed',
    'basicBlackDots': 'dotted',
    'basicBlackSquares': 'dashed',
    'basicThinLines': 'solid',
    'dashDotStroked': 'groove',
    'dashed': 'dashed',
    'dashSmallGap': 'dashed',
    'dotDash': 'dashed',
    'dotDotDash': 'dashed',
    'dotted': 'dotted',
    'double': 'double',
    'inset': 'inset',
    'nil': 'none',
    'none': 'none',
    'outset': 'outset',
    'single': 'solid',
    'thick': 'solid',
    'thickThinLargeGap': 'double',
    'thickThinMediumGap': 'double',
    'thickThinSmallGap' : 'double',
    'thinThickLargeGap': 'double',
    'thinThickMediumGap': 'double',
    'thinThickSmallGap': 'double',
    'thinThickThinLargeGap': 'double',
    'thinThickThinMediumGap': 'double',
    'thinThickThinSmallGap': 'double',
    'threeDEmboss': 'ridge',
    'threeDEngrave': 'groove',
    'triple': 'double',
}  # }}}

# Read from XML {{{

border_props = ('padding_%s', 'border_%s_width', 'border_%s_style', 'border_%s_color')
border_edges = ('left', 'top', 'right', 'bottom', 'between')


def read_single_border(parent, edge, XPath, get):
    color = style = width = padding = None
    for elem in XPath('./w:%s' % edge)(parent):
        c = get(elem, 'w:color')
        if c is not None:
            color = simple_color(c)
        s = get(elem, 'w:val')
        if s is not None:
            style = LINE_STYLES.get(s, 'solid')
        space = get(elem, 'w:space')
        if space is not None:
            try:
                padding = float(space)
            except (ValueError, TypeError):
                pass
        sz = get(elem, 'w:sz')
        if sz is not None:
            # we dont care about art borders (they are only used for page borders)
            try:
                width = min(96, max(2, float(sz))) / 8
            except (ValueError, TypeError):
                pass
    return {p:v for p, v in zip(border_props, (padding, width, style, color))}


def read_border(parent, dest, XPath, get, border_edges=border_edges, name='pBdr'):
    vals = {k % edge:inherit for edge in border_edges for k in border_props}

    for border in XPath('./w:' + name)(parent):
        for edge in border_edges:
            for prop, val in iteritems(read_single_border(border, edge, XPath, get)):
                if val is not None:
                    vals[prop % edge] = val

    for key, val in iteritems(vals):
        setattr(dest, key, val)


def border_to_css(edge, style, css):
    bs = getattr(style, 'border_%s_style' % edge)
    bc = getattr(style, 'border_%s_color' % edge)
    bw = getattr(style, 'border_%s_width' % edge)
    if isinstance(bw, numbers.Number):
        # WebKit needs at least 1pt to render borders and 3pt to render double borders
        bw = max(bw, (3 if bs == 'double' else 1))
    if bs is not inherit and bs is not None:
        css['border-%s-style' % edge] = bs
    if bc is not inherit and bc is not None:
        css['border-%s-color' % edge] = bc
    if bw is not inherit and bw is not None:
        if isinstance(bw, numbers.Number):
            bw = '%.3gpt' % bw
        css['border-%s-width' % edge] = bw


def read_indent(parent, dest, XPath, get):
    padding_left = padding_right = text_indent = inherit
    for indent in XPath('./w:ind')(parent):
        l, lc = get(indent, 'w:left'), get(indent, 'w:leftChars')
        pl = simple_float(lc, 0.01) if lc is not None else simple_float(l, 0.05) if l is not None else None
        if pl is not None:
            padding_left = '%.3g%s' % (pl, 'em' if lc is not None else 'pt')

        r, rc = get(indent, 'w:right'), get(indent, 'w:rightChars')
        pr = simple_float(rc, 0.01) if rc is not None else simple_float(r, 0.05) if r is not None else None
        if pr is not None:
            padding_right = '%.3g%s' % (pr, 'em' if rc is not None else 'pt')

        h, hc = get(indent, 'w:hanging'), get(indent, 'w:hangingChars')
        fl, flc = get(indent, 'w:firstLine'), get(indent, 'w:firstLineChars')
        h = h if h is None else '-'+h
        hc = hc if hc is None else '-'+hc
        ti = (simple_float(hc, 0.01) if hc is not None else simple_float(h, 0.05) if h is not None else
              simple_float(flc, 0.01) if flc is not None else simple_float(fl, 0.05) if fl is not None else None)
        if ti is not None:
            text_indent = '%.3g%s' % (ti, 'em' if hc is not None or (h is None and flc is not None) else 'pt')

    setattr(dest, 'margin_left', padding_left)
    setattr(dest, 'margin_right', padding_right)
    setattr(dest, 'text_indent', text_indent)


def read_justification(parent, dest, XPath, get):
    ans = inherit
    for jc in XPath('./w:jc[@w:val]')(parent):
        val = get(jc, 'w:val')
        if not val:
            continue
        if val in {'both', 'distribute'} or 'thai' in val or 'kashida' in val:
            ans = 'justify'
        elif val in {'left', 'center', 'right', 'start', 'end'}:
            ans = val
        elif val in {'start', 'end'}:
            ans = {'start':'left'}.get(val, 'right')
    setattr(dest, 'text_align', ans)


def read_spacing(parent, dest, XPath, get):
    padding_top = padding_bottom = line_height = inherit
    for s in XPath('./w:spacing')(parent):
        a, al, aa = get(s, 'w:after'), get(s, 'w:afterLines'), get(s, 'w:afterAutospacing')
        pb = None if aa in {'on', '1', 'true'} else simple_float(al, 0.02) if al is not None else simple_float(a, 0.05) if a is not None else None
        if pb is not None:
            padding_bottom = '%.3g%s' % (pb, 'ex' if al is not None else 'pt')

        b, bl, bb = get(s, 'w:before'), get(s, 'w:beforeLines'), get(s, 'w:beforeAutospacing')
        pt = None if bb in {'on', '1', 'true'} else simple_float(bl, 0.02) if bl is not None else simple_float(b, 0.05) if b is not None else None
        if pt is not None:
            padding_top = '%.3g%s' % (pt, 'ex' if bl is not None else 'pt')

        l, lr = get(s, 'w:line'), get(s, 'w:lineRule', 'auto')
        if l is not None:
            lh = simple_float(l, 0.05) if lr in {'exact', 'atLeast'} else simple_float(l, 1/240.0)
            if lh is not None:
                line_height = '%.3g%s' % (lh, 'pt' if lr in {'exact', 'atLeast'} else '')

    setattr(dest, 'margin_top', padding_top)
    setattr(dest, 'margin_bottom', padding_bottom)
    setattr(dest, 'line_height', line_height)


def read_shd(parent, dest, XPath, get):
    ans = inherit
    for shd in XPath('./w:shd[@w:fill]')(parent):
        val = get(shd, 'w:fill')
        if val:
            ans = simple_color(val, auto='transparent')
    setattr(dest, 'background_color', ans)


def read_numbering(parent, dest, XPath, get):
    lvl = num_id = inherit
    for np in XPath('./w:numPr')(parent):
        for ilvl in XPath('./w:ilvl[@w:val]')(np):
            try:
                lvl = int(get(ilvl, 'w:val'))
            except (ValueError, TypeError):
                pass
        for num in XPath('./w:numId[@w:val]')(np):
            num_id = get(num, 'w:val')
    setattr(dest, 'numbering_id', num_id)
    setattr(dest, 'numbering_level', lvl)


class Frame(object):

    all_attributes = ('drop_cap', 'h', 'w', 'h_anchor', 'h_rule', 'v_anchor', 'wrap',
                      'h_space', 'v_space', 'lines', 'x_align', 'y_align', 'x', 'y')

    def __init__(self, fp, XPath, get):
        self.drop_cap = get(fp, 'w:dropCap', 'none')
        try:
            self.h = int(get(fp, 'w:h'))/20
        except (ValueError, TypeError):
            self.h = 0
        try:
            self.w = int(get(fp, 'w:w'))/20
        except (ValueError, TypeError):
            self.w = None
        try:
            self.x = int(get(fp, 'w:x'))/20
        except (ValueError, TypeError):
            self.x = 0
        try:
            self.y = int(get(fp, 'w:y'))/20
        except (ValueError, TypeError):
            self.y = 0

        self.h_anchor = get(fp, 'w:hAnchor', 'page')
        self.h_rule = get(fp, 'w:hRule', 'auto')
        self.v_anchor = get(fp, 'w:vAnchor', 'page')
        self.wrap = get(fp, 'w:wrap', 'around')
        self.x_align = get(fp, 'w:xAlign')
        self.y_align = get(fp, 'w:yAlign')

        try:
            self.h_space = int(get(fp, 'w:hSpace'))/20
        except (ValueError, TypeError):
            self.h_space = 0
        try:
            self.v_space = int(get(fp, 'w:vSpace'))/20
        except (ValueError, TypeError):
            self.v_space = 0
        try:
            self.lines = int(get(fp, 'w:lines'))
        except (ValueError, TypeError):
            self.lines = 1

    def css(self, page):
        is_dropcap = self.drop_cap in {'drop', 'margin'}
        ans = {'overflow': 'hidden'}

        if is_dropcap:
            ans['float'] = 'left'
            ans['margin'] = '0'
            ans['padding-right'] = '0.2em'
        else:
            if self.h_rule != 'auto':
                t = 'min-height' if self.h_rule == 'atLeast' else 'height'
                ans[t] = '%.3gpt' % self.h
            if self.w is not None:
                ans['width'] = '%.3gpt' % self.w
            ans['padding-top'] = ans['padding-bottom'] = '%.3gpt' % self.v_space
            if self.wrap not in {None, 'none'}:
                ans['padding-left'] = ans['padding-right'] = '%.3gpt' % self.h_space
                if self.x_align is None:
                    fl = 'left' if self.x/page.width < 0.5 else 'right'
                else:
                    fl = 'right' if self.x_align == 'right' else 'left'
                ans['float'] = fl
        return ans

    def __eq__(self, other):
        for x in self.all_attributes:
            if getattr(other, x, inherit) != getattr(self, x):
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)


def read_frame(parent, dest, XPath, get):
    ans = inherit
    for fp in XPath('./w:framePr')(parent):
        ans = Frame(fp, XPath, get)
    setattr(dest, 'frame', ans)

# }}}


class ParagraphStyle(object):

    all_properties = (
        'adjustRightInd', 'autoSpaceDE', 'autoSpaceDN', 'bidi',
        'contextualSpacing', 'keepLines', 'keepNext', 'mirrorIndents',
        'pageBreakBefore', 'snapToGrid', 'suppressLineNumbers',
        'suppressOverlap', 'topLinePunct', 'widowControl', 'wordWrap',

        # Border margins padding
        'border_left_width', 'border_left_style', 'border_left_color', 'padding_left',
        'border_top_width', 'border_top_style', 'border_top_color', 'padding_top',
        'border_right_width', 'border_right_style', 'border_right_color', 'padding_right',
        'border_bottom_width', 'border_bottom_style', 'border_bottom_color', 'padding_bottom',
        'border_between_width', 'border_between_style', 'border_between_color', 'padding_between',
        'margin_left', 'margin_top', 'margin_right', 'margin_bottom',

        # Misc.
        'text_indent', 'text_align', 'line_height', 'background_color',
        'numbering_id', 'numbering_level', 'font_family', 'font_size', 'color', 'frame',
        'cs_font_size', 'cs_font_family',
    )

    def __init__(self, namespace, pPr=None):
        self.namespace = namespace
        self.linked_style = None
        if pPr is None:
            for p in self.all_properties:
                setattr(self, p, inherit)
        else:
            for p in (
                'adjustRightInd', 'autoSpaceDE', 'autoSpaceDN', 'bidi',
                'contextualSpacing', 'keepLines', 'keepNext', 'mirrorIndents',
                'pageBreakBefore', 'snapToGrid', 'suppressLineNumbers',
                'suppressOverlap', 'topLinePunct', 'widowControl', 'wordWrap',
            ):
                setattr(self, p, binary_property(pPr, p, namespace.XPath, namespace.get))

            for x in ('border', 'indent', 'justification', 'spacing', 'shd', 'numbering', 'frame'):
                f = read_funcs[x]
                f(pPr, self, namespace.XPath, namespace.get)

            for s in namespace.XPath('./w:pStyle[@w:val]')(pPr):
                self.linked_style = namespace.get(s, 'w:val')

            self.font_family = self.font_size = self.color = self.cs_font_size = self.cs_font_family = inherit

        self._css = None
        self._border_key = None

    def update(self, other):
        for prop in self.all_properties:
            nval = getattr(other, prop)
            if nval is not inherit:
                setattr(self, prop, nval)
        if other.linked_style is not None:
            self.linked_style = other.linked_style

    def resolve_based_on(self, parent):
        for p in self.all_properties:
            val = getattr(self, p)
            if val is inherit:
                setattr(self, p, getattr(parent, p))

    @property
    def css(self):
        if self._css is None:
            self._css = c = OrderedDict()
            if self.keepLines is True:
                c['page-break-inside'] = 'avoid'
            if self.pageBreakBefore is True:
                c['page-break-before'] = 'always'
            if self.keepNext is True:
                c['page-break-after'] = 'avoid'
            for edge in ('left', 'top', 'right', 'bottom'):
                border_to_css(edge, self, c)
                val = getattr(self, 'padding_%s' % edge)
                if val is not inherit:
                    c['padding-%s' % edge] = '%.3gpt' % val
                val = getattr(self, 'margin_%s' % edge)
                if val is not inherit:
                    c['margin-%s' % edge] = val

            if self.line_height not in {inherit, '1'}:
                c['line-height'] = self.line_height

            for x in ('text_indent', 'background_color', 'font_family', 'font_size', 'color'):
                val = getattr(self, x)
                if val is not inherit:
                    if x == 'font_size':
                        val = '%.3gpt' % val
                    c[x.replace('_', '-')] = val
            ta = self.text_align
            if ta is not inherit:
                if self.bidi is True:
                    ta = {'left':'right', 'right':'left'}.get(ta, ta)
                c['text-align'] = ta

        return self._css

    @property
    def border_key(self):
        if self._border_key is None:
            k = []
            for edge in border_edges:
                for prop in border_props:
                    prop = prop % edge
                    k.append(getattr(self, prop))
            self._border_key = tuple(k)
        return self._border_key

    def has_identical_borders(self, other_style):
        return self.border_key == getattr(other_style, 'border_key', None)

    def clear_borders(self):
        for edge in border_edges[:-1]:
            for prop in ('width', 'color', 'style'):
                setattr(self, 'border_%s_%s' % (edge, prop), inherit)

    def clone_border_styles(self):
        style = ParagraphStyle(self.namespace)
        for edge in border_edges[:-1]:
            for prop in ('width', 'color', 'style'):
                attr = 'border_%s_%s' % (edge, prop)
                setattr(style, attr, getattr(self, attr))
        return style

    def apply_between_border(self):
        for prop in ('width', 'color', 'style'):
            setattr(self, 'border_bottom_%s' % prop, getattr(self, 'border_between_%s' % prop))

    def has_visible_border(self):
        for edge in border_edges[:-1]:
            bw, bs = getattr(self, 'border_%s_width' % edge), getattr(self, 'border_%s_style' % edge)
            if bw is not inherit and bw and bs is not inherit and bs != 'none':
                return True
        return False


read_funcs = {k[5:]:v for k, v in iteritems(globals()) if k.startswith('read_')}
