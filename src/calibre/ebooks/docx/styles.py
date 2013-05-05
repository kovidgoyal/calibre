#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict

from calibre.ebooks.docx.names import XPath, get

class Inherit:
    pass
inherit = Inherit()

def binary_property(parent, name):
    vals = XPath('./w:%s')
    if not vals:
        return inherit
    val = get(vals[0], 'w:val', 'on')
    return True if val in {'on', '1', 'true'} else False

def simple_color(col):
    if not col or col == 'auto' or len(col) != 6:
        return 'black'
    return '#'+col

def simple_float(val, mult=1.0):
    try:
        return float(val) * mult
    except (ValueError, TypeError, AttributeError, KeyError):
        return None

# Block styles {{{

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

def read_border(border, dest):
    all_attrs = set()
    for edge in ('left', 'top', 'right', 'bottom'):
        vals = {'padding_%s':inherit, 'border_%s_width':inherit,
                'border_%s_style':inherit, 'border_%s_color':inherit}
        all_attrs |= {key % edge for key in vals}
        for elem in XPath('./w:%s' % edge):
            color = get(elem, 'w:color')
            if color is not None:
                vals['border_%s_color'] = simple_color(color)
            style = get(elem, 'w:val')
            if style is not None:
                vals['border_%s_style'] = LINE_STYLES.get(style, 'solid')
            space = get(elem, 'w:space')
            if space is not None:
                try:
                    vals['padding_%s'] = float(space)
                except (ValueError, TypeError):
                    pass
            sz = get(elem, 'w:space')
            if sz is not None:
                # we dont care about art borders (they are only used for page borders)
                try:
                    vals['border_%s_width'] = min(96, max(2, float(sz))) * 8
                except (ValueError, TypeError):
                    pass

        for key, val in vals.iteritems():
            setattr(dest, key % edge, val)

    return all_attrs

def read_indent(parent, dest):
    padding_left = padding_right = text_indent = inherit
    for indent in XPath('./w:ind')(parent):
        l, lc = get(indent, 'w:left'), get(indent, 'w:leftChars')
        pl = simple_float(lc, 0.01) if lc is not None else simple_float(l, 0.05) if l is not None else None
        if pl is not None:
            padding_left = '%.3f%s' % (pl, 'em' if lc is not None else 'pt')

        r, rc = get(indent, 'w:right'), get(indent, 'w:rightChars')
        pr = simple_float(rc, 0.01) if rc is not None else simple_float(r, 0.05) if r is not None else None
        if pr is not None:
            padding_right = '%.3f%s' % (pr, 'em' if rc is not None else 'pt')

        h, hc = get(indent, 'w:hanging'), get(indent, 'w:hangingChars')
        fl, flc = get(indent, 'w:firstLine'), get(indent, 'w:firstLineChars')
        ti = (simple_float(hc, 0.01) if hc is not None else simple_float(h, 0.05) if h is not None else
              simple_float(flc, 0.01) if flc is not None else simple_float(fl, 0.05) if fl is not None else None)
        if ti is not None:
            text_indent = '%.3f' % (ti, 'em' if hc is not None or (h is None and flc is not None) else 'pt')

    setattr(dest, 'padding_left', padding_left)
    setattr(dest, 'padding_right', padding_right)
    setattr(dest, 'text_indent', text_indent)
    return {'padding_left', 'padding_right', 'text_indent'}

def read_justification(parent, dest):
    ans = inherit
    for jc in XPath('./w:jc[@w:val]')(parent):
        val = get(jc, 'w:val')
        if not val:
            continue
        if val in {'both', 'distribute'} or 'thai' in val or 'kashida' in val:
            ans = 'justify'
        if val in {'left', 'center', 'right',}:
            ans = val
    setattr(dest, 'text_align', ans)
    return {'text_align'}

def read_spacing(parent, dest):
    padding_top = padding_bottom = line_height = inherit
    for s in XPath('./w:spacing')(parent):
        a, al, aa = get(s, 'w:after'), get(s, 'w:afterLines'), get(s, 'w:afterAutospacing')
        pb = None if aa in {'on', '1', 'true'} else simple_float(al, 0.02) if al is not None else simple_float(a, 0.05) if a is not None else None
        if pb is not None:
            padding_bottom = '%.3f%s' % (pb, 'ex' if al is not None else 'pt')

        b, bl, bb = get(s, 'w:before'), get(s, 'w:beforeLines'), get(s, 'w:beforeAutospacing')
        pt = None if bb in {'on', '1', 'true'} else simple_float(bl, 0.02) if bl is not None else simple_float(b, 0.05) if b is not None else None
        if pt is not None:
            padding_top = '%.3f%s' % (pt, 'ex' if bl is not None else 'pt')

        l, lr = get(s, 'w:line'), get(s, 'w:lineRule', 'auto')
        if l is not None:
            lh = simple_float(l, 0.05) if lr in {'exactly', 'atLeast'} else simple_float(l, 1/240.0)
            line_height = '%.3f%s' % (lh, 'pt' if lr in {'exactly', 'atLeast'} else '')

    setattr(dest, 'padding_top', padding_top)
    setattr(dest, 'padding_bottom', padding_bottom)
    setattr(dest, 'line_height', line_height)
    return {'padding_top', 'padding_bottom', 'line_height'}

def read_direction(parent, dest):
    ans = inherit
    for jc in XPath('./w:textFlow[@w:val]')(parent):
        val = get(jc, 'w:val')
        if not val:
            continue
        if 'rl' in val.lower():
            ans = 'rtl'
    setattr(dest, 'direction', ans)
    return {'direction'}


class ParagraphStyle(object):

    border_path = XPath('./w:pBdr')

    def __init__(self, pPr):
        self.all_properties = set()
        for p in (
            'adjustRightInd', 'autoSpaceDE', 'autoSpaceDN',
            'bidi', 'contextualSpacing', 'keepLines', 'keepNext',
            'mirrorIndents', 'pageBreakBefore', 'snapToGrid',
            'suppressLineNumbers', 'suppressOverlap', 'topLinePunct',
            'widowControl', 'wordWrap',
        ):
            self.all_properties.add(p)
            setattr(p, binary_property(pPr, p))

        for border in self.border_path(pPr):
            self.all_properties |= read_border(border, self)

        self.all_properties |= read_indent(pPr, self)
        self.all_properties |= read_justification(pPr, self)
        self.all_properties |= read_spacing(pPr, self)
        self.all_properties |= read_direction(pPr, self)

        # TODO: numPr and outlineLvl
# }}}

class Style(object):

    name_path = XPath('./w:name[@w:val]')
    based_on_path = XPath('./w:basedOn[@w:val]')
    link_path = XPath('./w:link[@w:val]')

    def __init__(self, elem):
        self.style_id = get(elem, 'w:styleId')
        self.style_type = get(elem, 'w:type')
        names = self.name_path(elem)
        self.name = get(names[-1], 'w:val') if names else None
        based_on = self.based_on_path(elem)
        self.based_on = get(based_on[0], 'w:val') if based_on else None
        if self.style_type == 'numbering':
            self.based_on = None
        link = self.link_path(elem)
        self.link = get(link[0], 'w:val') if link else None
        if self.style_type not in {'paragraph', 'character'}:
            self.link = None


class Styles(object):

    def __init__(self):
        self.id_map = OrderedDict()

    def __iter__(self):
        for s in self.id_map.itervalues():
            yield s

    def __getitem__(self, key):
        return self.id_map[key]

    def __len__(self):
        return len(self.id_map)

    def get(self, key, default=None):
        return self.id_map.get(key, default)

    def __call__(self, root):
        for s in XPath('//w:style')(root):
            s = Style(s)
            if s.style_id:
                self.id_map[s.style_id] = s

        # Nuke based_on, link attributes that refer to non-existing/incompatible
        # parents
        for s in self:
            bo = s.based_on
            if bo is not None:
                p = self.get(bo)
                if p is None or p.style_type != s.style_type:
                    s.based_on = None
            link = s.link
            if link is not None:
                p = self.get(link)
                if p is None or (s.style_type, p.style_type) not in {('paragraph', 'character'), ('character', 'paragraph')}:
                    s.link = None

        # TODO: Document defaults (docDefaults)



