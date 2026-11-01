#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import numbers
from collections import Counter, defaultdict
from operator import attrgetter
from typing import TYPE_CHECKING, Self, cast

from lxml import etree
from tinycss.css21 import CSS21Parser

from calibre.ebooks import parse_css_length
from calibre.ebooks.docx.writer.utils import convert_color, int_or_zero
from calibre.utils.localization import lang_as_iso639_1

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from lxml.etree import _Element

    from calibre.ebooks.docx.names import DOCXNamespace
    from calibre.ebooks.docx.writer.from_html import Block, TextRun
    from calibre.ebooks.oeb.stylizer import Style
    from calibre.utils.logging import Log

css_parser = CSS21Parser()

border_edges = ('left', 'top', 'right', 'bottom')
border_props = ('padding_%s', 'border_%s_width', 'border_%s_style', 'border_%s_color')
ignore = object()


def parse_css_font_family(raw: str) -> Iterator[str]:
    decl, errs = css_parser.parse_style_attr('font-family:' + raw)
    if decl:
        for token in decl[0].value:
            if token.type in 'STRING IDENT':
                val = token.value
                if val == 'inherit':
                    break
                yield val


def css_font_family_to_docx(raw: str) -> str | None:
    generic = {
        'serif': 'Cambria',
        'sansserif': 'Candara',
        'sans-serif': 'Candara',
        'fantasy': 'Comic Sans',
        'cursive': 'Segoe Script',
    }
    for ff in parse_css_font_family(raw):
        return generic.get(ff.lower(), ff)
    return None


def bmap(x: object) -> str:
    return 'on' if x else 'off'


def css_value(css: Style, name: str) -> str | float:
    ans = css[name]
    assert ans is not None  # only a few computed properties, such as background-color, can be None
    return ans


def css_keyword(css: Style, name: str) -> str:
    # For properties whose values are used as str, a numeric value would have
    # caused an exception when the str was used
    ans = css[name]
    assert isinstance(ans, str)
    return ans


def css_number(css: Style, name: str) -> float:
    # For properties whose values are used in arithmetic, a str value would
    # have caused an exception when used
    ans = css[name]
    assert isinstance(ans, (int, float))
    return ans


def css_color(css: Style, name: str) -> str | None:
    ans = css[name]
    if isinstance(ans, (int, float)):
        # convert_color() returns None for a falsy value and raised TypeError for other numbers
        assert not ans
        return None
    return ans


def is_dropcaps(html_tag: _Element, tag_style: Style) -> bool:
    return len(html_tag) < 2 and len(etree.tostring(html_tag, method='text', encoding='unicode', with_tail=False)) < 5 and tag_style['float'] == 'left'


class CombinedStyle:
    def __init__(self, bs: BlockStyle, rs: TextStyle, blocks: list[Block], namespace: DOCXNamespace) -> None:
        self.bs, self.rs, self.blocks = bs, rs, blocks
        self.namespace = namespace
        self.id: str | None = None
        self.name: str | None = None
        self.seq: int | None = None
        self.outline_level: int | None = None

    def apply(self) -> None:
        for block in self.blocks:
            block.linked_style = self
            for run in block.runs:
                run.parent_style = self.rs

    def serialize(self, styles: _Element, normal_style: CombinedStyle) -> None:
        makeelement = self.namespace.makeelement

        def w(x: str) -> str:
            return '{{{}}}{}'.format(self.namespace.namespaces['w'], x)

        # id and name are assigned in StylesManager.finalize()
        block = makeelement(styles, 'w:style', w_styleId=cast('str', self.id), w_type='paragraph')
        makeelement(block, 'w:name', w_val=cast('str', self.name))
        makeelement(block, 'w:qFormat')
        if self is not normal_style:
            makeelement(block, 'w:basedOn', w_val=cast('str', normal_style.id))
        if self.seq == 0:
            block.set(w('default'), '1')
        pPr = makeelement(block, 'w:pPr')
        self.bs.serialize_properties(pPr, normal_style.bs)
        if self.outline_level is not None:
            makeelement(pPr, 'w:outlineLvl', w_val=str(self.outline_level + 1))
        rPr = makeelement(block, 'w:rPr')
        self.rs.serialize_properties(rPr, normal_style.rs)


class FloatSpec:
    def __init__(self, namespace: DOCXNamespace, html_tag: _Element, tag_style: Style) -> None:
        self.makeelement = namespace.makeelement
        self.is_dropcaps = is_dropcaps(html_tag, tag_style)
        self.blocks: list[Block] = []
        if self.is_dropcaps:
            self.dropcaps_lines = 3
        else:
            self.x_align = css_keyword(tag_style, 'float')  # FloatSpec is only created for left and right floats
            self.w: int | None = None
            self.h: int | None = None
            if tag_style._get('width') != 'auto':
                self.w = int(20 * max(css_number(tag_style, 'min-width'), css_number(tag_style, 'width')))
            if tag_style._get('height') == 'auto':
                self.h_rule = 'auto'
            else:
                min_height = css_number(tag_style, 'min-height')
                if min_height > 0:
                    self.h_rule, h = 'atLeast', min_height
                else:
                    self.h_rule, h = 'exact', css_number(tag_style, 'height')
                self.h = int(20 * h)
            self.h_space = int(20 * max(css_number(tag_style, 'margin-right'), css_number(tag_style, 'margin-left')))
            self.v_space = int(20 * max(css_number(tag_style, 'margin-top'), css_number(tag_style, 'margin-bottom')))

        read_css_block_borders(self, tag_style)

    def serialize(self, block: Block, parent: _Element) -> None:
        if self.is_dropcaps:
            attrs = dict(w_dropCap='drop', w_lines=str(self.dropcaps_lines), w_wrap='around', w_vAnchor='text', w_hAnchor='text')
        else:
            attrs = dict(
                w_wrap='around',
                w_vAnchor='text',
                w_hAnchor='text',
                w_xAlign=self.x_align,
                w_y='1',
                w_hSpace=str(self.h_space),
                w_vSpace=str(self.v_space),
                w_hRule=self.h_rule,
            )
            if self.w is not None:
                attrs['w_w'] = str(self.w)
            if self.h is not None:
                attrs['w_h'] = str(self.h)
        self.makeelement(parent, 'w:framePr', append=True, **attrs)
        # Margins are already applied by the frame style, so override them to
        # be zero on individual blocks
        self.makeelement(parent, 'w:ind', w_left='0', w_leftChars='0', w_right='0', w_rightChars='0')
        attrs = {}
        if block is self.blocks[0]:
            attrs.update(dict(w_before='0', w_beforeLines='0'))
        if block is self.blocks[-1]:
            attrs.update(dict(w_after='0', w_afterLines='0'))
        if attrs:
            self.makeelement(parent, 'w:spacing', append=True, **attrs)
        # Similarly apply the same border and padding properties to all blocks
        # in this floatspec
        bdr = self.makeelement(parent, 'w:pBdr')
        for edge in border_edges:
            padding = getattr(self, 'padding_' + edge)
            width = getattr(self, f'border_{edge}_width')
            bstyle = getattr(self, f'border_{edge}_style')
            self.makeelement(
                bdr,
                'w:' + edge,
                w_space=str(padding),
                w_val=bstyle,
                w_sz=str(width),
                w_color=getattr(self, f'border_{edge}_color'),
            )


class DOCXStyle:
    ALL_PROPS: tuple[str, ...] = ()
    TYPE = 'paragraph'
    seq: int  # set by StylesManager.finalize()

    def __init__(self, namespace: DOCXNamespace) -> None:
        self.namespace = namespace
        self.w = lambda x: '{{{}}}{}'.format(namespace.namespaces['w'], x)
        self.id: str | None = None
        self.name: str | None = None
        self.next_style: str | None = None
        self.calculate_hash()

    def calculate_hash(self) -> None:
        self._hash = hash(tuple(getattr(self, x) for x in self.ALL_PROPS))

    def makeelement(self, parent: _Element, name: str, **attrs: str) -> _Element:
        return parent.makeelement(self.w(name), {self.w(k): v for k, v in attrs.items()})

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return all(getattr(self, x) == getattr(other, x, None) for x in self.ALL_PROPS)

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __repr__(self) -> str:
        return etree.tostring(
            self.serialize(etree.Element(self.__class__.__name__, nsmap={'w': self.namespace.namespaces['w']}), self),
            pretty_print=True,
            encoding='unicode',
        )

    __str__ = __repr__

    def serialize(self, styles: _Element, normal_style: Self) -> _Element:
        makeelement = self.makeelement
        # id and name are assigned in StylesManager.finalize()
        style = makeelement(styles, 'style', styleId=cast('str', self.id), type=self.TYPE)
        style.append(makeelement(style, 'name', val=cast('str', self.name)))
        if self is not normal_style:
            style.append(makeelement(style, 'basedOn', val=cast('str', normal_style.id)))
        styles.append(style)
        return style


LINE_STYLES = {
    'none': 'none',
    'hidden': 'none',
    'dotted': 'dotted',
    'dashed': 'dashed',
    'solid': 'single',
    'double': 'double',
    'groove': 'threeDEngrave',
    'ridge': 'threeDEmboss',
    'inset': 'inset',
    'outset': 'outset',
}


def convert_underline(items: Iterable[str]) -> str:
    style = 'solid'
    has_underline = False
    color = 'auto'
    for x in items:
        if x in {'solid', 'double', 'dotted', 'dashed', 'wavy'}:
            style = {'solid': 'single', 'wavy': 'wave', 'dashed': 'dash'}.get(x, x)
        elif x in {'underline', 'overline', 'line-through', 'blink', 'none'}:
            if x == 'underline':
                has_underline = True
            elif x == 'none':
                has_underline = False
        else:
            c = convert_color(x)
            if c is not None:
                color = c
    if has_underline:
        return style + ' ' + color
    return ''


class TextStyle(DOCXStyle):
    ALL_PROPS = (
        'font_family',
        'font_size',
        'bold',
        'italic',
        'color',
        'background_color',
        'underline',
        'strike',
        'dstrike',
        'caps',
        'shadow',
        'small_caps',
        'spacing',
        'vertical_align',
        'padding',
        'border_style',
        'border_width',
        'border_color',
    )
    TYPE = 'character'

    def __init__(self, namespace: DOCXNamespace, css: Style, is_parent_style: bool = False) -> None:
        self.font_family = css_font_family_to_docx(css_keyword(css, 'font-family'))
        try:
            self.font_size = max(0, int(float(css.fontSize) * 2))  # stylizer normalizes all font sizes into pts
        except ValueError, TypeError, AttributeError:
            self.font_size = None

        fw = css_value(css, 'font-weight')
        self.bold = (fw.lower() if isinstance(fw, str) else fw) in {'bold', 'bolder'} or int_or_zero(fw) >= 700
        self.italic = css_keyword(css, 'font-style').lower() in {'italic', 'oblique'}
        self.color = convert_color(css_color(css, 'color'))
        self.background_color = None if is_parent_style else convert_color(css.backgroundColor)
        td = set((css.effective_text_decoration or '').split())
        self.underline = convert_underline(td)
        self.dstrike = 'line-through' in td and 'overline' in td
        self.strike = not self.dstrike and 'line-through' in td
        self.text_transform = css['text-transform']  # TODO: If lowercase or capitalize, transform the actual text
        self.caps = self.text_transform == 'uppercase'
        self.small_caps = css_keyword(css, 'font-variant').lower() in {'small-caps', 'smallcaps'}
        self.shadow = css['text-shadow'] not in {'none', None}
        try:
            self.spacing = int(float(css_value(css, 'letter-spacing')) * 20)
        except ValueError, TypeError, AttributeError:
            self.spacing = None
        va = css.first_vertical_align
        if isinstance(va, numbers.Number):
            self.vertical_align = str(int(va * 2))
        else:
            val = {
                'top': 'superscript',
                'text-top': 'superscript',
                'sup': 'superscript',
                'super': 'superscript',
                'bottom': 'subscript',
                'text-bottom': 'subscript',
                'sub': 'subscript',
            }.get(va)
            self.vertical_align = val or 'baseline'

        self.padding = self.border_color = self.border_width = self.border_style = None
        if not is_parent_style:
            # DOCX does not support individual borders/padding for inline content
            for edge in border_edges:
                # In DOCX padding can only be a positive integer
                try:
                    padding = max(0, int(css_value(css, 'padding-' + edge)))
                except ValueError:
                    padding = 0
                if self.padding is None:
                    self.padding = padding
                elif self.padding != padding:
                    self.padding = ignore
                val = css[f'border-{edge}-width']
                if not isinstance(val, numbers.Number):
                    val = {'thin': 0.2, 'medium': 1, 'thick': 2}.get(val, 0)
                val = min(96, max(2, int(val * 8)))
                if self.border_width is None:
                    self.border_width = val
                elif self.border_width != val:
                    self.border_width = ignore
                color = convert_color(css_color(css, f'border-{edge}-color'))
                if self.border_color is None:
                    self.border_color = color
                elif self.border_color != color:
                    self.border_color = ignore
                style = LINE_STYLES.get(css_keyword(css, f'border-{edge}-style').lower(), 'none')
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

    def serialize_borders(self, bdr: _Element, normal_style: TextStyle) -> _Element:
        w = self.w
        is_normal_style = self is normal_style
        if is_normal_style or self.padding != normal_style.padding:
            bdr.set(w('space'), str(self.padding))
        if is_normal_style or self.border_width != normal_style.border_width:
            bdr.set(w('sz'), str(self.border_width))
        if is_normal_style or self.border_style != normal_style.border_style:
            # border properties are always str after __init__()
            bdr.set(w('val'), cast('str', self.border_style))
        if is_normal_style or self.border_color != normal_style.border_color:
            bdr.set(w('color'), cast('str', self.border_color))
        return bdr

    def serialize(self, styles: _Element, normal_style: Self) -> _Element:
        makeelement = self.makeelement
        style_root = DOCXStyle.serialize(self, styles, normal_style)
        style = makeelement(style_root, 'rPr')
        self.serialize_properties(style, normal_style)
        if len(style) > 0:
            style_root.append(style)
        return style_root

    def serialize_properties(self, rPr: _Element, normal_style: TextStyle) -> None:
        makeelement = self.makeelement
        is_normal_style = self is normal_style
        if self.font_family is not None and (is_normal_style or self.font_family != normal_style.font_family):
            rPr.append(makeelement(rPr, 'rFonts', **{k: self.font_family for k in 'ascii cs eastAsia hAnsi'.split()}))

        for name, attr, vmap in (('sz', 'font_size', str), ('b', 'bold', bmap), ('i', 'italic', bmap)):
            val = getattr(self, attr)
            if is_normal_style or getattr(normal_style, attr) != val:
                for suffix in ('', 'Cs'):
                    rPr.append(makeelement(rPr, name + suffix, val=vmap(val)))

        def check_attr(attr: str) -> bool:
            val = getattr(self, attr)
            return is_normal_style or (val != getattr(normal_style, attr))

        if check_attr('color'):
            rPr.append(makeelement(rPr, 'color', val=self.color or 'auto'))
        if check_attr('background_color'):
            rPr.append(makeelement(rPr, 'shd', fill=self.background_color or 'auto'))
        if check_attr('underline'):
            style, color = self.underline.partition(' ')[::2]
            if color != 'auto':
                rPr.append(makeelement(rPr, 'u', val=style, color=color))
            else:
                rPr.append(makeelement(rPr, 'u', val=style))
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
            rPr.append(
                makeelement(
                    rPr,
                    'vertAlign',
                    val=self.vertical_align if self.vertical_align in {'superscript', 'subscript'} else 'baseline',
                )
            )
        elif self.vertical_align != normal_style.vertical_align:
            if self.vertical_align in {'superscript', 'subscript', 'baseline'}:
                rPr.append(makeelement(rPr, 'vertAlign', val=self.vertical_align))
            else:
                rPr.append(makeelement(rPr, 'position', val=self.vertical_align))

        bdr = self.serialize_borders(makeelement(rPr, 'bdr'), normal_style)
        if bdr.attrib:
            rPr.append(bdr)


class DescendantTextStyle:
    seq: int  # set by StylesManager.finalize()

    def __init__(self, parent_style: TextStyle, child_style: TextStyle) -> None:
        self.id: str | None = None
        self.name: str | None = None
        self.makeelement = child_style.makeelement

        p: list[tuple[str, frozenset[tuple[str, str]]]] = []

        def add(name: str, **props: str) -> None:
            p.append((name, frozenset(props.items())))

        def vals(attr: str) -> tuple[object, object]:
            return getattr(parent_style, attr), getattr(child_style, attr)

        def check(attr: str) -> bool:
            pval, cval = vals(attr)
            return pval != cval

        if child_style.font_family is not None and parent_style.font_family != child_style.font_family:
            add('rFonts', **{k: child_style.font_family for k in 'ascii cs eastAsia hAnsi'.split()})

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
            if not child_style.underline:
                add('u', val='none')
            else:
                style, color = child_style.underline.partition(' ')[::2]
                add('u', val=style, color=color)
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

        bdr: dict[str, str] = {}
        if check('padding'):
            bdr['space'] = str(child_style.padding)
        if check('border_width'):
            bdr['sz'] = str(child_style.border_width)
        if check('border_style'):
            # border properties are always str after TextStyle.__init__()
            bdr['val'] = cast('str', child_style.border_style)
        if check('border_color'):
            bdr['color'] = cast('str', child_style.border_color)
        if bdr:
            add('bdr', **bdr)
        self.properties = tuple(p)
        self._hash = hash(self.properties)

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return self.properties == other.properties  # ty: ignore[unresolved-attribute]  # only compared with other DescendantTextStyles

    def __ne__(self, other: object) -> bool:
        return self.properties != other.properties  # ty: ignore[unresolved-attribute]

    def serialize(self, styles: _Element) -> _Element:
        makeelement = self.makeelement
        # id and name are assigned in StylesManager.finalize()
        style = makeelement(styles, 'style', styleId=cast('str', self.id), type='character')
        style.append(makeelement(style, 'name', val=cast('str', self.name)))
        rpr = makeelement(style, 'rPr')
        style.append(rpr)
        for name, attrs in self.properties:
            rpr.append(makeelement(style, name, **dict(attrs)))
        styles.append(style)
        return style


def read_css_block_borders(self: object, css: Style | None, store_css_style: bool = False) -> None:
    for edge in border_edges:
        if css is None:
            setattr(self, 'padding_' + edge, 0)
            setattr(self, 'margin_' + edge, 0)
            setattr(self, 'css_margin_' + edge, '')
            setattr(self, f'border_{edge}_width', 2)
            setattr(self, f'border_{edge}_color', None)
            setattr(self, f'border_{edge}_style', 'none')
            if store_css_style:
                setattr(self, f'border_{edge}_css_style', 'none')
        else:
            # In DOCX padding can only be a positive integer
            try:
                setattr(self, 'padding_' + edge, max(0, int(css_value(css, 'padding-' + edge))))
            except ValueError:
                setattr(self, 'padding_' + edge, 0)  # invalid value for padding
            # In DOCX margin must be a positive integer in twips (twentieth of a point)
            try:
                setattr(self, 'margin_' + edge, max(0, int(css_value(css, 'margin-' + edge) * 20)))
            except ValueError:
                setattr(self, 'margin_' + edge, 0)  # e.g.: margin: auto
            setattr(self, 'css_margin_' + edge, css._style.get('margin-' + edge, ''))
            val = css[f'border-{edge}-width']
            if not isinstance(val, numbers.Number):
                val = {'thin': 0.2, 'medium': 1, 'thick': 2}.get(val, 0)
            val = min(96, max(2, int(val * 8)))
            setattr(self, f'border_{edge}_width', val)
            setattr(self, f'border_{edge}_color', convert_color(css_color(css, f'border-{edge}-color')) or 'auto')
            setattr(self, f'border_{edge}_style', LINE_STYLES.get(css_keyword(css, f'border-{edge}-style').lower(), 'none'))
            if store_css_style:
                setattr(self, f'border_{edge}_css_style', css_keyword(css, f'border-{edge}-style').lower())


class BlockStyle(DOCXStyle):
    ALL_PROPS = tuple(
        'text_align css_text_indent text_indent line_height background_color'.split()
        + ['margin_' + edge for edge in border_edges]
        + ['css_margin_' + edge for edge in border_edges]
        + [x % edge for edge in border_edges for x in border_props]
    )

    def __init__(self, namespace: DOCXNamespace, css: Style | None, html_block: _Element, is_table_cell: bool = False, parent_bg: str | None = None) -> None:
        read_css_block_borders(self, css)
        if is_table_cell:
            for edge in border_edges:
                setattr(self, f'border_{edge}_style', 'none')
                setattr(self, f'border_{edge}_width', 0)
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
                self.text_indent = int(css_value(css, 'text-indent') * 20)
                self.css_text_indent = css._get('text-indent')
            except TypeError, ValueError:
                self.text_indent = 0
                self.css_text_indent = None
            try:
                self.line_height = max(0, int(css.lineHeight * 20))
            except TypeError, ValueError:
                self.line_height = max(0, int(1.2 * css.fontSize * 20))
            self.background_color = None if is_table_cell else convert_color(css.backgroundColor)
            if not is_table_cell and self.background_color is None:
                self.background_color = parent_bg
            try:
                ws = css['white-space']
                # a non-str value has no lower() and so does not preserve whitespace
                preserve_whitespace = isinstance(ws, str) and ws.lower() in {'pre', 'pre-wrap'}
            except Exception:
                preserve_whitespace = False
            try:
                text_align = css['text-align']
                # a non-str value has no lower(), it used to raise AttributeError and so is mapped to left
                aval = text_align.lower() if isinstance(text_align, str) else 'left'
                if preserve_whitespace:
                    aval = 'start'
                self.text_align = {
                    'start': 'left',
                    'left': 'left',
                    'end': 'right',
                    'right': 'right',
                    'center': 'center',
                    'justify': 'both',
                    'centre': 'center',
                }.get(aval, 'left')
            except AttributeError:
                self.text_align = 'left'

        DOCXStyle.__init__(self, namespace)

    def serialize_borders(self, bdr: _Element, normal_style: BlockStyle) -> _Element:
        w = self.w
        for edge in border_edges:
            e = bdr.makeelement(w(edge))
            padding = getattr(self, 'padding_' + edge)
            if (self is normal_style and padding > 0) or (padding != getattr(normal_style, 'padding_' + edge)):
                e.set(w('space'), str(padding))
            width = getattr(self, f'border_{edge}_width')
            bstyle = getattr(self, f'border_{edge}_style')
            if (
                (self is normal_style and width > 0 and bstyle != 'none')
                or width != getattr(normal_style, f'border_{edge}_width')
                or bstyle != getattr(normal_style, f'border_{edge}_style')
            ):
                e.set(w('val'), bstyle)
                e.set(w('sz'), str(width))
                e.set(w('color'), getattr(self, f'border_{edge}_color'))
            if e.attrib:
                bdr.append(e)
        return bdr

    def serialize(self, styles: _Element, normal_style: Self) -> _Element:
        makeelement = self.makeelement
        style_root = DOCXStyle.serialize(self, styles, normal_style)
        style = makeelement(style_root, 'pPr')
        self.serialize_properties(style, normal_style)
        if len(style) > 0:
            style_root.append(style)
        return style_root

    def serialize_properties(self, pPr: _Element, normal_style: BlockStyle) -> None:
        makeelement, w = self.makeelement, self.w
        spacing = makeelement(pPr, 'spacing')
        for edge, attr in {'top': 'before', 'bottom': 'after'}.items():
            getter = attrgetter('css_margin_' + edge)
            css_val, css_unit = parse_css_length(getter(self))
            if css_unit in ('em', 'ex'):
                lines = max(0, int(cast('float', css_val) * (50 if css_unit == 'ex' else 100)))
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
                chars = max(0, int(cast('float', css_val) * (50 if css_unit == 'ex' else 100)))
                if (self is normal_style and chars > 0) or getter(self) != getter(normal_style):
                    ind.set(w(edge + 'Chars'), str(chars))
            else:
                getter = attrgetter('margin_' + edge)
                val = getter(self)
                if (self is normal_style and val > 0) or val != getter(normal_style):
                    ind.set(w(edge), str(val))
                    ind.set(w(edge + 'Chars'), '0')  # This is needed to override any declaration in the parent style
        css_val, css_unit = parse_css_length(self.css_text_indent)  # ty: ignore[invalid-argument-type]  # non-str values give (None, None)
        if css_unit in ('em', 'ex'):
            css_val = cast('float', css_val)  # parse_css_length() returns a number when it returns a unit
            chars = int(css_val * (50 if css_unit == 'ex' else 100))
            if css_val >= 0:
                if (self is normal_style and chars > 0) or self.css_text_indent != normal_style.css_text_indent:
                    ind.set(w('firstLineChars'), str(chars))
            elif (self is normal_style and chars < 0) or self.css_text_indent != normal_style.css_text_indent:
                ind.set(w('hangingChars'), str(abs(chars)))
        else:
            val = self.text_indent
            if val >= 0:
                if (self is normal_style and val > 0) or self.text_indent != normal_style.text_indent:
                    ind.set(w('firstLine'), str(val))
                    ind.set(w('firstLineChars'), '0')  # This is needed to override any declaration in the parent style
            elif (self is normal_style and val < 0) or self.text_indent != normal_style.text_indent:
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


class StylesManager:
    def __init__(self, namespace: DOCXNamespace, log: Log, document_lang: str | None) -> None:
        self.namespace = namespace
        self.document_lang = lang_as_iso639_1(document_lang) or 'en'
        self.log = log
        self.block_styles: dict[BlockStyle, BlockStyle] = {}
        self.text_styles: dict[TextStyle, TextStyle] = {}
        self.styles_for_html_blocks: dict[_Element, BlockStyle] = {}

    def create_text_style(self, css_style: Style, is_parent_style: bool = False) -> TextStyle:
        ans = TextStyle(self.namespace, css_style, is_parent_style=is_parent_style)
        existing = self.text_styles.get(ans, None)
        if existing is None:
            self.text_styles[ans] = ans
        else:
            ans = existing
        return ans

    def create_block_style(self, css_style: Style, html_block: _Element, is_table_cell: bool = False, parent_bg: str | None = None) -> BlockStyle:
        ans = BlockStyle(self.namespace, css_style, html_block, is_table_cell=is_table_cell, parent_bg=parent_bg)
        existing = self.block_styles.get(ans, None)
        if existing is None:
            self.block_styles[ans] = ans
        else:
            ans = existing
        self.styles_for_html_blocks[html_block] = ans
        return ans

    def finalize(self, all_blocks: list[Block]) -> None:
        block_counts: Counter[BlockStyle] = Counter()
        run_counts: Counter[TextStyle] = Counter()
        block_rmap: defaultdict[BlockStyle, list[Block]] = defaultdict(list)
        run_rmap: defaultdict[TextStyle, list[TextRun]] = defaultdict(list)
        used_pairs: defaultdict[tuple[BlockStyle, TextStyle], list[Block]] = defaultdict(list)
        heading_styles: defaultdict[str, list[tuple[BlockStyle, TextStyle]]] = defaultdict(list)
        headings = frozenset('h1 h2 h3 h4 h5 h6'.split())
        pure_block_styles: set[BlockStyle] = set()

        for block in all_blocks:
            bs = block.style
            block_counts[bs] += 1
            block_rmap[block.style].append(block)
            local_run_counts: Counter[TextStyle] = Counter()
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
            bs.id = bs.name = f'%0{bnum}d Block' % i
            bs.seq = i
            if i == 0:
                self.normal_pure_block_style = bs

        counts: Counter[CombinedStyle] = Counter()
        smap: dict[tuple[BlockStyle, TextStyle], CombinedStyle] = {}
        for (bs, rs), blocks in used_pairs.items():
            s = CombinedStyle(bs, rs, blocks, self.namespace)
            smap[(bs, rs)] = s
            counts[s] += sum(1 for b in blocks if not b.is_empty())
        for i, heading_tag in enumerate(sorted(heading_styles)):
            styles = sorted((smap[k] for k in heading_styles[heading_tag]), key=counts.__getitem__)
            styles = list(filter(lambda s: s.outline_level is None, styles))
            if styles:
                heading_style = styles[-1]
                heading_style.outline_level = i

        snum = len(str(max(1, len(counts) - 1)))
        heading_style_list: list[CombinedStyle] = []
        for i, (style, count) in enumerate(counts.most_common()):
            if i == 0:
                self.normal_style = style
                style.id = style.name = 'Normal'
            else:
                if style.outline_level is None:
                    val = f'Para %0{snum}d' % i
                else:
                    val = f'Heading {style.outline_level + 1}'
                    heading_style_list.append(style)
                style.id = style.name = val
            style.seq = i
        self.combined_styles = sorted(counts, key=attrgetter('seq'))
        [ls.apply() for ls in self.combined_styles]

        descendant_style_map: dict[DescendantTextStyle, DescendantTextStyle] = {}
        ds_counts: Counter[DescendantTextStyle] = Counter()
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
            text_style.id = f'Text{i}'
            text_style.name = f'%0{rnum}d Text' % i
            text_style.seq = i
        self.descendant_text_styles = sorted(descendant_style_map, key=attrgetter('seq'))

        self.log.debug(f'{len(self.descendant_text_styles)} Text Styles {len(self.combined_styles)} Combined styles')

        self.primary_heading_style: CombinedStyle | None = None
        if heading_style_list:
            heading_style_list.sort(key=attrgetter('outline_level'))
            self.primary_heading_style = heading_style_list[0]
        else:
            ms = 0
            for s in self.combined_styles:
                fs = s.rs.font_size
                if fs is not None and fs > ms:
                    self.primary_heading_style = s
                    ms = fs

    def serialize(self, styles: _Element) -> None:
        lang = styles.xpath('descendant::*[local-name()="lang"]')[0]
        for k in tuple(lang.attrib):
            lang.attrib[k] = self.document_lang
        for style in self.combined_styles:
            style.serialize(styles, self.normal_style)
        for style in self.descendant_text_styles:
            style.serialize(styles)
        for style in sorted(self.pure_block_styles, key=attrgetter('seq')):
            style.serialize(styles, self.normal_pure_block_style)
