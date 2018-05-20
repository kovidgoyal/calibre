#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import Counter, defaultdict
from operator import attrgetter

from lxml import etree

from calibre.ebooks import parse_css_length
from calibre.ebooks.docx.writer.utils import convert_color, int_or_zero
from calibre.utils.localization import lang_as_iso639_1
from tinycss.css21 import CSS21Parser

css_parser = CSS21Parser()

border_edges = ('left', 'top', 'right', 'bottom')
border_props = ('padding_%s', 'border_%s_width', 'border_%s_style', 'border_%s_color')
ignore = object()


def parse_css_font_family(raw):
    decl, errs = css_parser.parse_style_attr('font-family:' + raw)
    if decl:
        for token in decl[0].value:
            if token.type in 'STRING IDENT':
                val = token.value
                if val == 'inherit':
                    break
                yield val


def css_font_family_to_docx(raw):
    generic = {'serif':'Cambria', 'sansserif':'Candara', 'sans-serif':'Candara', 'fantasy':'Comic Sans', 'cursive':'Segoe Script'}
    for ff in parse_css_font_family(raw):
        return generic.get(ff.lower(), ff)


def bmap(x):
    return 'on' if x else 'off'


def is_dropcaps(html_tag, tag_style):
    return len(html_tag) < 2 and len(etree.tostring(html_tag, method='text', encoding=unicode, with_tail=False)) < 5 and tag_style['float'] == 'left'


class CombinedStyle(object):

    def __init__(self, bs, rs, blocks, namespace):
        self.bs, self.rs, self.blocks = bs, rs, blocks
        self.namespace = namespace
        self.id = self.name = self.seq = None
        self.outline_level = None

    def apply(self):
        for block in self.blocks:
            block.linked_style = self
            for run in block.runs:
                run.parent_style = self.rs

    def serialize(self, styles, normal_style):
        makeelement = self.namespace.makeelement
        w = lambda x: '{%s}%s' % (self.namespace.namespaces['w'], x)
        block = makeelement(styles, 'w:style', w_styleId=self.id, w_type='paragraph')
        makeelement(block, 'w:name', w_val=self.name)
        makeelement(block, 'w:qFormat')
        if self is not normal_style:
            makeelement(block, 'w:basedOn', w_val=normal_style.id)
        if self.seq == 0:
            block.set(w('default'), '1')
        pPr = makeelement(block, 'w:pPr')
        self.bs.serialize_properties(pPr, normal_style.bs)
        if self.outline_level is not None:
            makeelement(pPr, 'w:outlineLvl', w_val=str(self.outline_level + 1))
        rPr = makeelement(block, 'w:rPr')
        self.rs.serialize_properties(rPr, normal_style.rs)


class FloatSpec(object):

    def __init__(self, namespace, html_tag, tag_style):
        self.makeelement = namespace.makeelement
        self.is_dropcaps = is_dropcaps(html_tag, tag_style)
        self.blocks = []
        if self.is_dropcaps:
            self.dropcaps_lines = 3
        else:
            self.x_align = tag_style['float']
            self.w = self.h = None
            if tag_style._get('width') != 'auto':
                self.w = int(20 * max(tag_style['min-width'], tag_style['width']))
            if tag_style._get('height') == 'auto':
                self.h_rule = 'auto'
            else:
                if tag_style['min-height'] > 0:
                    self.h_rule, self.h = 'atLeast', tag_style['min-height']
                else:
                    self.h_rule, self.h = 'exact', tag_style['height']
                self.h = int(20 * self.h)
            self.h_space = int(20 * max(tag_style['margin-right'], tag_style['margin-left']))
            self.v_space = int(20 * max(tag_style['margin-top'], tag_style['margin-bottom']))

        read_css_block_borders(self, tag_style)

    def serialize(self, block, parent):
        if self.is_dropcaps:
            attrs = dict(w_dropCap='drop', w_lines=str(self.dropcaps_lines), w_wrap='around', w_vAnchor='text', w_hAnchor='text')
        else:
            attrs = dict(
                w_wrap='around', w_vAnchor='text', w_hAnchor='text', w_xAlign=self.x_align, w_y='1',
                w_hSpace=str(self.h_space), w_vSpace=str(self.v_space), w_hRule=self.h_rule
            )
            if self.w is not None:
                attrs['w_w'] = str(self.w)
            if self.h is not None:
                attrs['w_h'] = str(self.h)
        self.makeelement(parent, 'w:framePr', **attrs)
        # Margins are already applied by the frame style, so override them to
        # be zero on individual blocks
        self.makeelement(parent, 'w:ind', w_left='0', w_leftChars='0', w_right='0', w_rightChars='0')
        attrs = {}
        if block is self.blocks[0]:
            attrs.update(dict(w_before='0', w_beforeLines='0'))
        if block is self.blocks[-1]:
            attrs.update(dict(w_after='0', w_afterLines='0'))
        if attrs:
            self.makeelement(parent, 'w:spacing', **attrs)
        # Similarly apply the same border and padding properties to all blocks
        # in this floatspec
        bdr = self.makeelement(parent, 'w:pBdr')
        for edge in border_edges:
            padding = getattr(self, 'padding_' + edge)
            width = getattr(self, 'border_%s_width' % edge)
            bstyle = getattr(self, 'border_%s_style' % edge)
            self.makeelement(bdr, 'w:'+edge, w_space=str(padding), w_val=bstyle, w_sz=str(width), w_color=getattr(self, 'border_%s_color' % edge))


class DOCXStyle(object):

    ALL_PROPS = ()
    TYPE = 'paragraph'

    def __init__(self, namespace):
        self.namespace = namespace
        self.w = lambda x: '{%s}%s' % (namespace.namespaces['w'], x)
        self.id = self.name = None
        self.next_style = None
        self.calculate_hash()

    def calculate_hash(self):
        self._hash = hash(tuple(
            getattr(self, x) for x in self.ALL_PROPS))

    def makeelement(self, parent, name, **attrs):
        return parent.makeelement(self.w(name), **{self.w(k):v for k, v in attrs.iteritems()})

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        for x in self.ALL_PROPS:
            if getattr(self, x) != getattr(other, x, None):
                return False
        return True

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return etree.tostring(self.serialize(etree.Element(self.__class__.__name__, nsmap={'w':self.namespace.namespaces['w']})), pretty_print=True)
    __str__ = __repr__

    def serialize(self, styles, normal_style):
        makeelement = self.makeelement
        style = makeelement(styles, 'style', styleId=self.id, type=self.TYPE)
        style.append(makeelement(style, 'name', val=self.name))
        if self is not normal_style:
            style.append(makeelement(style, 'basedOn', val=normal_style.id))
        styles.append(style)
        return style


LINE_STYLES = {
    'none'  : 'none',
    'hidden': 'none',
    'dotted': 'dotted',
    'dashed': 'dashed',
    'solid' : 'single',
    'double': 'double',
    'groove': 'threeDEngrave',
    'ridge' : 'threeDEmboss',
    'inset' : 'inset',
    'outset': 'outset',
}


class TextStyle(DOCXStyle):

    ALL_PROPS = ('font_family', 'font_size', 'bold', 'italic', 'color',
                 'background_color', 'underline', 'strike', 'dstrike', 'caps',
                 'shadow', 'small_caps', 'spacing', 'vertical_align', 'padding',
                 'border_style', 'border_width', 'border_color')
    TYPE = 'character'

    def __init__(self, namespace, css, is_parent_style=False):
        self.font_family = css_font_family_to_docx(css['font-family'])
        try:
            self.font_size = max(0, int(float(css['font-size']) * 2))  # stylizer normalizes all font sizes into pts
        except (ValueError, TypeError, AttributeError):
            self.font_size = None

        fw = css['font-weight']
        self.bold = (fw.lower() if hasattr(fw, 'lower') else fw) in {'bold', 'bolder'} or int_or_zero(fw) >= 700
        self.italic = css['font-style'].lower() in {'italic', 'oblique'}
        self.color = convert_color(css['color'])
        self.background_color = None if is_parent_style else convert_color(css.backgroundColor)
        td = set((css.effective_text_decoration or '').split())
        self.underline = 'underline' in td
        self.dstrike = 'line-through' in td and 'overline' in td
        self.strike = not self.dstrike and 'line-through' in td
        self.text_transform = css['text-transform']  # TODO: If lowercase or capitalize, transform the actual text
        self.caps = self.text_transform == 'uppercase'
        self.small_caps = css['font-variant'].lower() in {'small-caps', 'smallcaps'}
        self.shadow = css['text-shadow'] not in {'none', None}
        try:
            self.spacing = int(float(css['letter-spacing']) * 20)
        except (ValueError, TypeError, AttributeError):
            self.spacing = None
        va = css.first_vertical_align
        if isinstance(va, (int, float)):
            self.vertical_align = str(int(va * 2))
        else:
            val = {
                'top':'superscript', 'text-top':'superscript', 'sup':'superscript', 'super':'superscript',
                'bottom':'subscript', 'text-bottom':'subscript', 'sub':'subscript'}.get(va)
            self.vertical_align = val or 'baseline'

        self.padding = self.border_color = self.border_width = self.border_style = None
        if not is_parent_style:
            # DOCX does not support individual borders/padding for inline content
            for edge in border_edges:
                # In DOCX padding can only be a positive integer
                try:
                    padding = max(0, int(css['padding-' + edge]))
                except ValueError:
                    padding = 0
                if self.padding is None:
                    self.padding = padding
                elif self.padding != padding:
                    self.padding = ignore
                val = css['border-%s-width' % edge]
                if not isinstance(val, (float, int, long)):
                    val = {'thin':0.2, 'medium':1, 'thick':2}.get(val, 0)
                val = min(96, max(2, int(val * 8)))
                if self.border_width is None:
                    self.border_width = val
                elif self.border_width != val:
                    self.border_width = ignore
                color = convert_color(css['border-%s-color' % edge])
                if self.border_color is None:
                    self.border_color = color
                elif self.border_color != color:
                    self.border_color = ignore
                style = LINE_STYLES.get(css['border-%s-style' % edge].lower(), 'none')
                if self.border_style is None:
                    self.border_style = style
                elif self.border_style != style:
                    self.border_style = ignore

        if self.padding in (None, ignore):
            self.padding = 0
        if self.border_width in (None, ignore):
            self.border_width = 0
        if self.border_style in (None, ignore):
            self.border_style = 'none'
        if self.border_color in (None, ignore):
            self.border_color = 'auto'
        if self.border_style == 'none':
            self.border_width, self.border_color = 0, 'auto'

        DOCXStyle.__init__(self, namespace)

    def serialize_borders(self, bdr, normal_style):
        w = self.w
        is_normal_style = self is normal_style
        if is_normal_style or self.padding != normal_style.padding:
            bdr.set(w('space'), str(self.padding))
        if is_normal_style or self.border_width != normal_style.border_width:
            bdr.set(w('sz'), str(self.border_width))
        if is_normal_style or self.border_style != normal_style.border_style:
            bdr.set(w('val'), self.border_style)
        if is_normal_style or self.border_color != normal_style.border_color:
            bdr.set(w('color'), self.border_color)
        return bdr

    def serialize(self, styles, normal_style):
        makeelement = self.makeelement
        style_root = DOCXStyle.serialize(self, styles, normal_style)
        style = makeelement(style_root, 'rPr')
        self.serialize_properties(style, normal_style)
        if len(style) > 0:
            style_root.append(style)
        return style_root

    def serialize_properties(self, rPr, normal_style):
        makeelement = self.makeelement
        is_normal_style = self is normal_style
        if is_normal_style or self.font_family != normal_style.font_family:
            rPr.append(makeelement(
                rPr, 'rFonts', **{k:self.font_family for k in 'ascii cs eastAsia hAnsi'.split()}))

        for name, attr, vmap in (('sz', 'font_size', str), ('b', 'bold', bmap), ('i', 'italic', bmap)):
            val = getattr(self, attr)
            if is_normal_style or getattr(normal_style, attr) != val:
                for suffix in ('', 'Cs'):
                    rPr.append(makeelement(rPr, name + suffix, val=vmap(val)))

        def check_attr(attr):
            val = getattr(self, attr)
            return is_normal_style or (val != getattr(normal_style, attr))

        if check_attr('color'):
            rPr.append(makeelement(rPr, 'color', val=self.color or 'auto'))
        if check_attr('background_color'):
            rPr.append(makeelement(rPr, 'shd', fill=self.background_color or 'auto'))
        if check_attr('underline'):
            rPr.append(makeelement(rPr, 'u', val='single' if self.underline else 'none'))
        if check_attr('dstrike'):
            rPr.append(makeelement(rPr, 'dstrike', val=bmap(self.dstrike)))
        if check_attr('strike'):
            rPr.append(makeelement(rPr, 'strike', val=bmap(self.strike)))
        if check_attr('caps'):
            rPr.append(makeelement(rPr, 'caps', val=bmap(self.caps)))
        if check_attr('small_caps'):
            rPr.append(makeelement(rPr, 'smallCaps', val=bmap(self.small_caps)))
        if check_attr('shadow'):
            rPr.append(makeelement(rPr, 'shadow', val=bmap(self.shadow)))
        if check_attr('spacing'):
            rPr.append(makeelement(rPr, 'spacing', val=str(self.spacing or 0)))
        if is_normal_style:
            rPr.append(makeelement(rPr, 'vertAlign', val=self.vertical_align if self.vertical_align in {'superscript', 'subscript'} else 'baseline'))
        elif self.vertical_align != normal_style.vertical_align:
            if self.vertical_align in {'superscript', 'subscript', 'baseline'}:
                rPr.append(makeelement(rPr, 'vertAlign', val=self.vertical_align))
            else:
                rPr.append(makeelement(rPr, 'position', val=self.vertical_align))

        bdr = self.serialize_borders(makeelement(rPr, 'bdr'), normal_style)
        if bdr.attrib:
            rPr.append(bdr)


class DescendantTextStyle(object):

    def __init__(self, parent_style, child_style):
        self.id = self.name = None
        self.makeelement = child_style.makeelement

        p = []

        def add(name, **props):
            p.append((name, frozenset(props.iteritems())))

        def vals(attr):
            return getattr(parent_style, attr), getattr(child_style, attr)

        def check(attr):
            pval, cval = vals(attr)
            return pval != cval

        if parent_style.font_family != child_style.font_family:
            add('rFonts', **{k:child_style.font_family for k in 'ascii cs eastAsia hAnsi'.split()})

        for name, attr in (('sz', 'font_size'), ('b', 'bold'), ('i', 'italic')):
            pval, cval = vals(attr)
            if pval != cval:
                val = 'on' if attr in {'bold', 'italic'} else str(cval)  # bold, italic are toggle properties
                for suffix in ('', 'Cs'):
                    add(name + suffix, val=val)

        if check('color'):
            add('color', val=child_style.color or 'auto')
        if check('background_color'):
            add('shd', fill=child_style.background_color or 'auto')
        if check('underline'):
            add('u', val='single' if child_style.underline else 'none')
        if check('dstrike'):
            add('dstrike', val=bmap(child_style.dstrike))
        if check('strike'):
            add('strike', val='on')  # toggle property
        if check('caps'):
            add('caps', val='on')  # toggle property
        if check('small_caps'):
            add('smallCaps', val='on')  # toggle property
        if check('shadow'):
            add('shadow', val='on')  # toggle property
        if check('spacing'):
            add('spacing', val=str(child_style.spacing or 0))
        if check('vertical_align'):
            val = child_style.vertical_align
            if val in {'superscript', 'subscript', 'baseline'}:
                add('vertAlign', val=val)
            else:
                add('position', val=val)

        bdr = {}
        if check('padding'):
            bdr['space'] = str(child_style.padding)
        if check('border_width'):
            bdr['sz'] = str(child_style.border_width)
        if check('border_style'):
            bdr['val'] = child_style.border_style
        if check('border_color'):
            bdr['color'] = child_style.border_color
        if bdr:
            add('bdr', **bdr)
        self.properties = tuple(p)
        self._hash = hash(self.properties)

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        return self.properties == other.properties

    def __ne__(self, other):
        return self.properties != other.properties

    def serialize(self, styles):
        makeelement = self.makeelement
        style = makeelement(styles, 'style', styleId=self.id, type='character')
        style.append(makeelement(style, 'name', val=self.name))
        rpr = makeelement(style, 'rPr')
        style.append(rpr)
        for name, attrs in self.properties:
            rpr.append(makeelement(style, name, **dict(attrs)))
        styles.append(style)
        return style


def read_css_block_borders(self, css, store_css_style=False):
    for edge in border_edges:
        if css is None:
            setattr(self, 'padding_' + edge, 0)
            setattr(self, 'margin_' + edge, 0)
            setattr(self, 'css_margin_' + edge, '')
            setattr(self, 'border_%s_width' % edge, 2)
            setattr(self, 'border_%s_color' % edge, None)
            setattr(self, 'border_%s_style' %  edge, 'none')
            if store_css_style:
                setattr(self, 'border_%s_css_style' %  edge, 'none')
        else:
            # In DOCX padding can only be a positive integer
            try:
                setattr(self, 'padding_' + edge, max(0, int(css['padding-' + edge])))
            except ValueError:
                setattr(self, 'padding_' + edge, 0)  # invalid value for padding
            # In DOCX margin must be a positive integer in twips (twentieth of a point)
            try:
                setattr(self, 'margin_' + edge, max(0, int(css['margin-' + edge] * 20)))
            except ValueError:
                setattr(self, 'margin_' + edge, 0)  # for e.g.: margin: auto
            setattr(self, 'css_margin_' + edge, css._style.get('margin-' + edge, ''))
            val = css['border-%s-width' % edge]
            if not isinstance(val, (float, int, long)):
                val = {'thin':0.2, 'medium':1, 'thick':2}.get(val, 0)
            val = min(96, max(2, int(val * 8)))
            setattr(self, 'border_%s_width' % edge, val)
            setattr(self, 'border_%s_color' % edge, convert_color(css['border-%s-color' % edge]) or 'auto')
            setattr(self, 'border_%s_style' %  edge, LINE_STYLES.get(css['border-%s-style' % edge].lower(), 'none'))
            if store_css_style:
                setattr(self, 'border_%s_css_style' %  edge, css['border-%s-style' % edge].lower())


class BlockStyle(DOCXStyle):

    ALL_PROPS = tuple(
        'text_align css_text_indent text_indent line_height background_color'.split(
        ) + ['margin_' + edge for edge in border_edges
        ] + ['css_margin_' + edge for edge in border_edges
        ] + [x%edge for edge in border_edges for x in border_props]
    )

    def __init__(self, namespace, css, html_block, is_table_cell=False, parent_bg=None):
        read_css_block_borders(self, css)
        if is_table_cell:
            for edge in border_edges:
                setattr(self, 'border_%s_style' % edge, 'none')
                setattr(self, 'border_%s_width' % edge, 0)
                setattr(self, 'padding_' + edge, 0)
                setattr(self, 'margin_' + edge, 0)
        if css is None:
            self.text_indent = 0
            self.css_text_indent = None
            self.line_height = 280
            self.background_color = None
            self.text_align = 'left'
        else:
            try:
                self.text_indent = int(css['text-indent'] * 20)
                self.css_text_indent = css._get('text-indent')
            except (TypeError, ValueError):
                self.text_indent = 0
                self.css_text_indent = None
            try:
                self.line_height = max(0, int(css.lineHeight * 20))
            except (TypeError, ValueError):
                self.line_height = max(0, int(1.2 * css.fontSize * 20))
            self.background_color = None if is_table_cell else convert_color(css['background-color'])
            if not is_table_cell and self.background_color is None:
                self.background_color = parent_bg
            try:
                ws = css['white-space'].lower()
                preserve_whitespace = ws in {'pre', 'pre-wrap'}
            except Exception:
                preserve_whitespace = False
            try:
                aval = css['text-align'].lower()
                if preserve_whitespace:
                    aval = 'start'
                self.text_align = {'start':'left', 'left':'left', 'end':'right', 'right':'right', 'center':'center', 'justify':'both', 'centre':'center'}.get(
                    aval, 'left')
            except AttributeError:
                self.text_align = 'left'

        DOCXStyle.__init__(self, namespace)

    def serialize_borders(self, bdr, normal_style):
        w = self.w
        for edge in border_edges:
            e = bdr.makeelement(w(edge))
            padding = getattr(self, 'padding_' + edge)
            if (self is normal_style and padding > 0) or (padding != getattr(normal_style, 'padding_' + edge)):
                e.set(w('space'), str(padding))
            width = getattr(self, 'border_%s_width' % edge)
            bstyle = getattr(self, 'border_%s_style' % edge)
            if (self is normal_style and width > 0 and bstyle != 'none'
                    ) or width != getattr(normal_style, 'border_%s_width' % edge
                    ) or bstyle != getattr(normal_style, 'border_%s_style' % edge):
                e.set(w('val'), bstyle)
                e.set(w('sz'), str(width))
                e.set(w('color'), getattr(self, 'border_%s_color' % edge))
            if e.attrib:
                bdr.append(e)
        return bdr

    def serialize(self, styles, normal_style):
        makeelement = self.makeelement
        style_root = DOCXStyle.serialize(self, styles, normal_style)
        style = makeelement(style_root, 'pPr')
        self.serialize_properties(style, normal_style)
        if len(style) > 0:
            style_root.append(style)
        return style_root

    def serialize_properties(self, pPr, normal_style):
        makeelement, w = self.makeelement, self.w
        spacing = makeelement(pPr, 'spacing')
        for edge, attr in {'top':'before', 'bottom':'after'}.iteritems():
            getter = attrgetter('css_margin_' + edge)
            css_val, css_unit = parse_css_length(getter(self))
            if css_unit in ('em', 'ex'):
                lines = max(0, int(css_val * (50 if css_unit == 'ex' else 100)))
                if (self is normal_style and lines > 0) or getter(self) != getter(normal_style):
                    spacing.set(w(attr + 'Lines'), str(lines))
            else:
                getter = attrgetter('margin_' + edge)
                val = getter(self)
                if (self is normal_style and val > 0) or val != getter(normal_style):
                    spacing.set(w(attr), str(val))

        if self is normal_style or self.line_height != normal_style.line_height:
            spacing.set(w('line'), str(self.line_height))
            spacing.set(w('lineRule'), 'atLeast')

        if spacing.attrib:
            pPr.append(spacing)

        ind = makeelement(pPr, 'ind')
        for edge in ('left', 'right'):
            getter = attrgetter('css_margin_' + edge)
            css_val, css_unit = parse_css_length(getter(self))
            if css_unit in ('em', 'ex'):
                chars = max(0, int(css_val * (50 if css_unit == 'ex' else 100)))
                if (self is normal_style and chars > 0) or getter(self) != getter(normal_style):
                    ind.set(w(edge + 'Chars'), str(chars))
            else:
                getter = attrgetter('margin_' + edge)
                val = getter(self)
                if (self is normal_style and val > 0) or val != getter(normal_style):
                    ind.set(w(edge), str(val))
                    ind.set(w(edge + 'Chars'), '0')  # This is needed to override any declaration in the parent style
        css_val, css_unit = parse_css_length(self.css_text_indent)
        if css_unit in ('em', 'ex'):
            chars = int(css_val * (50 if css_unit == 'ex' else 100))
            if css_val >= 0:
                if (self is normal_style and chars > 0) or self.css_text_indent != normal_style.css_text_indent:
                    ind.set(w('firstLineChars'), str(chars))
            else:
                if (self is normal_style and chars < 0) or self.css_text_indent != normal_style.css_text_indent:
                    ind.set(w('hangingChars'), str(abs(chars)))
        else:
            val = self.text_indent
            if val >= 0:
                if (self is normal_style and val > 0) or self.text_indent != normal_style.text_indent:
                    ind.set(w('firstLine'), str(val))
                    ind.set(w('firstLineChars'), '0')  # This is needed to override any declaration in the parent style
            else:
                if (self is normal_style and val < 0) or self.text_indent != normal_style.text_indent:
                    ind.set(w('hanging'), str(abs(val)))
                    ind.set(w('hangingChars'), '0')
        if ind.attrib:
            pPr.append(ind)

        if (self is normal_style and self.background_color) or self.background_color != normal_style.background_color:
            pPr.append(makeelement(pPr, 'shd', val='clear', color='auto', fill=self.background_color or 'auto'))

        pbdr = self.serialize_borders(pPr.makeelement(w('pBdr')), normal_style)
        if len(pbdr):
            pPr.append(pbdr)

        if self is normal_style or self.text_align != normal_style.text_align:
            pPr.append(makeelement(pPr, 'jc', val=self.text_align))

        if self is not normal_style and self.next_style is not None:
            pPr.append(makeelement(pPr, 'next', val=self.next_style))


class StylesManager(object):

    def __init__(self, namespace, log, document_lang):
        self.namespace = namespace
        self.document_lang = lang_as_iso639_1(document_lang) or 'en'
        self.log = log
        self.block_styles, self.text_styles = {}, {}
        self.styles_for_html_blocks = {}

    def create_text_style(self, css_style, is_parent_style=False):
        ans = TextStyle(self.namespace, css_style, is_parent_style=is_parent_style)
        existing = self.text_styles.get(ans, None)
        if existing is None:
            self.text_styles[ans] = ans
        else:
            ans = existing
        return ans

    def create_block_style(self, css_style, html_block, is_table_cell=False, parent_bg=None):
        ans = BlockStyle(self.namespace, css_style, html_block, is_table_cell=is_table_cell, parent_bg=parent_bg)
        existing = self.block_styles.get(ans, None)
        if existing is None:
            self.block_styles[ans] = ans
        else:
            ans = existing
        self.styles_for_html_blocks[html_block] = ans
        return ans

    def finalize(self, all_blocks):
        block_counts, run_counts = Counter(), Counter()
        block_rmap, run_rmap = defaultdict(list), defaultdict(list)
        used_pairs = defaultdict(list)
        heading_styles = defaultdict(list)
        headings = frozenset('h1 h2 h3 h4 h5 h6'.split())
        pure_block_styles = set()

        for block in all_blocks:
            bs = block.style
            block_counts[bs] += 1
            block_rmap[block.style].append(block)
            local_run_counts = Counter()
            for run in block.runs:
                count = run.style_weight
                run_counts[run.style] += count
                local_run_counts[run.style] += count
                run_rmap[run.style].append(run)
            if local_run_counts:
                rs = local_run_counts.most_common(1)[0][0]
                used_pairs[(bs, rs)].append(block)
                if block.html_tag in headings:
                    heading_styles[block.html_tag].append((bs, rs))
            else:
                pure_block_styles.add(bs)

        self.pure_block_styles = sorted(pure_block_styles, key=block_counts.__getitem__)
        bnum = len(str(max(1, len(pure_block_styles) - 1)))
        for i, bs in enumerate(self.pure_block_styles):
            bs.id = bs.name = '%0{}d Block'.format(bnum) % i
            bs.seq = i
            if i == 0:
                self.normal_pure_block_style = bs

        counts = Counter()
        smap = {}
        for (bs, rs), blocks in used_pairs.iteritems():
            s = CombinedStyle(bs, rs, blocks, self.namespace)
            smap[(bs, rs)] = s
            counts[s] += sum(1 for b in blocks if not b.is_empty())
        for i, heading_tag in enumerate(sorted(heading_styles)):
            styles = sorted((smap[k] for k in heading_styles[heading_tag]), key=counts.__getitem__)
            styles = filter(lambda s:s.outline_level is None, styles)
            if styles:
                heading_style = styles[-1]
                heading_style.outline_level = i

        snum = len(str(max(1, len(counts) - 1)))
        heading_styles = []
        for i, (style, count) in enumerate(counts.most_common()):
            if i == 0:
                self.normal_style = style
                style.id = style.name = 'Normal'
            else:
                if style.outline_level is None:
                    val = 'Para %0{}d'.format(snum) % i
                else:
                    val = 'Heading %d' % (style.outline_level + 1)
                    heading_styles.append(style)
                style.id = style.name = val
            style.seq = i
        self.combined_styles = sorted(counts.iterkeys(), key=attrgetter('seq'))
        [ls.apply() for ls in self.combined_styles]

        descendant_style_map = {}
        ds_counts = Counter()
        for block in all_blocks:
            for run in block.runs:
                if run.parent_style is not run.style and run.parent_style and run.style:
                    ds = DescendantTextStyle(run.parent_style, run.style)
                    if ds.properties:
                        run.descendant_style = descendant_style_map.get(ds)
                        if run.descendant_style is None:
                            run.descendant_style = descendant_style_map[ds] = ds
                        ds_counts[run.descendant_style] += run.style_weight
        rnum = len(str(max(1, len(ds_counts) - 1)))
        for i, (text_style, count) in enumerate(ds_counts.most_common()):
            text_style.id = 'Text%d' % i
            text_style.name = '%0{}d Text'.format(rnum) % i
            text_style.seq = i
        self.descendant_text_styles = sorted(descendant_style_map, key=attrgetter('seq'))

        self.log.debug('%d Text Styles %d Combined styles' % tuple(map(len, (
            self.descendant_text_styles, self.combined_styles))))

        self.primary_heading_style = None
        if heading_styles:
            heading_styles.sort(key=attrgetter('outline_level'))
            self.primary_heading_style = heading_styles[0]
        else:
            ms = 0
            for s in self.combined_styles:
                if s.rs.font_size > ms:
                    self.primary_heading_style = s
                    ms = s.rs.font_size

    def serialize(self, styles):
        lang = styles.xpath('descendant::*[local-name()="lang"]')[0]
        for k in tuple(lang.attrib):
            lang.attrib[k] = self.document_lang
        for style in self.combined_styles:
            style.serialize(styles, self.normal_style)
        for style in self.descendant_text_styles:
            style.serialize(styles)
        for style in sorted(self.pure_block_styles, key=attrgetter('seq')):
            style.serialize(styles, self.normal_pure_block_style)
