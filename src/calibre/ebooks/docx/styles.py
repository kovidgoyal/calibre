#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import textwrap
from collections import Counter, OrderedDict
from typing import TYPE_CHECKING, cast

from calibre.ebooks.docx.block_styles import ParagraphStyle, inherit, twips
from calibre.ebooks.docx.char_styles import RunStyle

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence

    from lxml.etree import _Element

    from calibre.ebooks.docx.container import DOCX
    from calibre.ebooks.docx.fonts import Fonts
    from calibre.ebooks.docx.names import DOCXNamespace
    from calibre.ebooks.docx.numbering import Numbering
    from calibre.ebooks.docx.tables import Tables, TableStyle
    from calibre.ebooks.docx.theme import Theme


class PageProperties:
    """
    Class representing page level properties (page size/margins) read from
    sectPr elements.
    """

    def __init__(self, namespace: DOCXNamespace, elems: Iterable[_Element] = ()) -> None:
        self.width, self.height = 595.28, 841.89  # pts, A4
        self.margin_left = self.margin_right = 72  # pts

        def setval(attr: str, val: str | None) -> None:
            pts = twips(val)
            if pts is not None:
                setattr(self, attr, pts)

        for sectPr in elems:
            for pgSz in namespace.XPath('./w:pgSz')(sectPr):
                w, h = namespace.get(pgSz, 'w:w'), namespace.get(pgSz, 'w:h')
                setval('width', w), setval('height', h)
            for pgMar in namespace.XPath('./w:pgMar')(sectPr):
                l, r = namespace.get(pgMar, 'w:left'), namespace.get(pgMar, 'w:right')
                setval('margin_left', l), setval('margin_right', r)


class Style:
    """
    Class representing a <w:style> element. Can contain block, character, etc. styles.
    """

    def __init__(self, namespace: DOCXNamespace, elem: _Element) -> None:
        self.namespace = namespace
        self.name_path = namespace.XPath('./w:name[@w:val]')
        self.based_on_path = namespace.XPath('./w:basedOn[@w:val]')
        self.resolved = False
        self.style_id = namespace.get(elem, 'w:styleId')
        self.style_type = namespace.get(elem, 'w:type')
        names = self.name_path(elem)
        self.name = namespace.get(names[-1], 'w:val') if names else None
        based_on = self.based_on_path(elem)
        self.based_on = namespace.get(based_on[0], 'w:val') if based_on else None
        if self.style_type == 'numbering':
            self.based_on = None
        self.is_default = namespace.get(elem, 'w:default') in {'1', 'on', 'true'}

        self.paragraph_style: ParagraphStyle | None = None
        self.character_style: RunStyle | None = None
        self.table_style: TableStyle | None = None

        if self.style_type in {'paragraph', 'character', 'table'}:
            if self.style_type == 'table':
                from calibre.ebooks.docx.tables import TableStyle

                for tblPr in namespace.XPath('./w:tblPr')(elem):
                    ts = TableStyle(namespace, tblPr)
                    if self.table_style is None:
                        self.table_style = ts
                    else:
                        self.table_style.update(ts)
            if self.style_type in {'paragraph', 'table'}:
                for pPr in namespace.XPath('./w:pPr')(elem):
                    ps = ParagraphStyle(namespace, pPr)
                    if self.paragraph_style is None:
                        self.paragraph_style = ps
                    else:
                        self.paragraph_style.update(ps)

            for rPr in namespace.XPath('./w:rPr')(elem):
                rs = RunStyle(namespace, rPr)
                if self.character_style is None:
                    self.character_style = rs
                else:
                    self.character_style.update(rs)

        if self.style_type in {'numbering', 'paragraph'}:
            self.numbering_style_link: str | None = None
            for x in namespace.XPath('./w:pPr/w:numPr/w:numId[@w:val]')(elem):
                self.numbering_style_link = namespace.get(x, 'w:val')

    def resolve_based_on(self, parent: Style) -> None:
        if parent.table_style is not None:
            if self.table_style is None:
                from calibre.ebooks.docx.tables import TableStyle

                self.table_style = TableStyle(self.namespace)
            self.table_style.resolve_based_on(parent.table_style)
        if parent.paragraph_style is not None:
            if self.paragraph_style is None:
                self.paragraph_style = ParagraphStyle(self.namespace)
            self.paragraph_style.resolve_based_on(parent.paragraph_style)
        if parent.character_style is not None:
            if self.character_style is None:
                self.character_style = RunStyle(self.namespace)
            self.character_style.resolve_based_on(parent.character_style)


class Styles:
    """
    Collection of all styles defined in the document. Used to get the final styles applicable to elements in the document markup.
    """

    def __init__(self, namespace: DOCXNamespace, tables: Tables) -> None:
        self.namespace = namespace
        self.id_map: OrderedDict[str, Style] = OrderedDict()
        self.para_cache: dict[_Element, ParagraphStyle] = {}
        self.para_char_cache: dict[_Element, RunStyle] = {}
        self.run_cache: dict[_Element, RunStyle] = {}
        self.classes: dict[int, tuple[str, Mapping[str, str]]] = {}
        self.counter: Counter[str] = Counter()
        self.default_styles: dict[str | None, Style] = {}
        self.tables = tables
        self.numbering_style_links: dict[str | None, str | None] = {}
        self.default_paragraph_style: ParagraphStyle | None = None
        self.default_character_style: RunStyle | None = None

    def __iter__(self) -> Iterator[Style]:
        yield from self.id_map.values()

    def __getitem__(self, key: str) -> Style:
        return self.id_map[key]

    def __len__(self) -> int:
        return len(self.id_map)

    def get(self, key: str | None, default: Style | None = None) -> Style | None:
        return self.id_map.get(key, default)

    def __call__(self, root: _Element | None, fonts: Fonts, theme: Theme) -> None:
        self.fonts, self.theme = fonts, theme
        self.default_paragraph_style = self.default_character_style = None
        if root is not None:
            for s in self.namespace.XPath('//w:style')(root):
                s = Style(self.namespace, s)
                if s.style_id:
                    self.id_map[s.style_id] = s
                if s.is_default:
                    self.default_styles[s.style_type] = s
                if getattr(s, 'numbering_style_link', None) is not None:
                    self.numbering_style_links[s.style_id] = s.numbering_style_link

            for dd in self.namespace.XPath('./w:docDefaults')(root):
                for pd in self.namespace.XPath('./w:pPrDefault')(dd):
                    for pPr in self.namespace.XPath('./w:pPr')(pd):
                        ps = ParagraphStyle(self.namespace, pPr)
                        if self.default_paragraph_style is None:
                            self.default_paragraph_style = ps
                        else:
                            self.default_paragraph_style.update(ps)
                for pd in self.namespace.XPath('./w:rPrDefault')(dd):
                    for pPr in self.namespace.XPath('./w:rPr')(pd):
                        ps = RunStyle(self.namespace, pPr)
                        if self.default_character_style is None:
                            self.default_character_style = ps
                        else:
                            self.default_character_style.update(ps)

        def resolve(s: Style, p: Style | None) -> None:
            if p is not None:
                if not p.resolved:
                    resolve(p, self.get(p.based_on))
                s.resolve_based_on(p)
            s.resolved = True

        for s in self:
            if not s.resolved:
                resolve(s, self.get(s.based_on))

    def para_val(self, parent_styles: Sequence[ParagraphStyle], direct_formatting: ParagraphStyle, attr: str) -> object:
        val = getattr(direct_formatting, attr)
        if val is inherit:
            for ps in reversed(parent_styles):
                pval = getattr(ps, attr)
                if pval is not inherit:
                    val = pval
                    break
        return val

    def run_val(self, parent_styles: Sequence[RunStyle], direct_formatting: RunStyle, attr: str) -> object:
        val = getattr(direct_formatting, attr)
        if val is not inherit:
            return val
        if attr in direct_formatting.toggle_properties:
            # The spec (section 17.7.3) does not make sense, so we follow the behavior
            # of Word, which seems to only consider the document default if the
            # property has not been defined in any styles.
            vals = [int(getattr(rs, attr)) for rs in parent_styles if rs is not self.default_character_style and getattr(rs, attr) is not inherit]
            if vals:
                return sum(vals) % 2 == 1
            if self.default_character_style is not None:
                return getattr(self.default_character_style, attr) is True
            return False
        for rs in reversed(parent_styles):
            rval = getattr(rs, attr)
            if rval is not inherit:
                return rval
        return val

    def resolve_paragraph(self, p: _Element) -> ParagraphStyle:
        ans = self.para_cache.get(p, None)
        if ans is None:
            linked_style = None
            ans = self.para_cache[p] = ParagraphStyle(self.namespace)
            ans.style_name = None
            direct_formatting = None
            is_section_break = False
            for pPr in self.namespace.XPath('./w:pPr')(p):
                ps = ParagraphStyle(self.namespace, pPr)
                if direct_formatting is None:
                    direct_formatting = ps
                else:
                    direct_formatting.update(ps)
                if self.namespace.XPath('./w:sectPr')(pPr):
                    is_section_break = True

            if direct_formatting is None:
                direct_formatting = ParagraphStyle(self.namespace)
            parent_styles: list[ParagraphStyle] = []
            if self.default_paragraph_style is not None:
                parent_styles.append(self.default_paragraph_style)
            ts = self.tables.para_style(p)
            if ts is not None:
                parent_styles.append(ts)

            default_para = self.default_styles.get('paragraph', None)
            if direct_formatting.linked_style is not None:
                ls = linked_style = self.get(direct_formatting.linked_style)
                if ls is not None:
                    ans.style_name = ls.name
                    ps = ls.paragraph_style
                    if ps is not None:
                        parent_styles.append(ps)
                    if ls.character_style is not None:
                        self.para_char_cache[p] = ls.character_style
            elif default_para is not None:
                if default_para.paragraph_style is not None:
                    parent_styles.append(default_para.paragraph_style)
                if default_para.character_style is not None:
                    self.para_char_cache[p] = default_para.character_style

            def has_numbering(block_style: ParagraphStyle | None) -> bool:
                num_id, lvl = (
                    getattr(block_style, 'numbering_id', inherit),
                    getattr(block_style, 'numbering_level', inherit),
                )
                return num_id is not None and num_id is not inherit and lvl is not None and lvl is not inherit

            is_numbering = has_numbering(direct_formatting)
            is_section_break = is_section_break and not self.namespace.XPath('./w:r')(p)

            if is_numbering and not is_section_break:
                num_id, lvl = direct_formatting.numbering_id, direct_formatting.numbering_level
                p.set('calibre_num_id', f'{lvl}:{num_id}')
                # has_numbering() guarantees these are not inherit
                ps = self.numbering.get_para_style(cast('str | None', num_id), cast('int', lvl))
                if ps is not None:
                    parent_styles.append(ps)
            if not is_numbering and not is_section_break and linked_style is not None and has_numbering(linked_style.paragraph_style):
                assert linked_style.paragraph_style is not None  # has_numbering() is False for None
                num_id, lvl = linked_style.paragraph_style.numbering_id, linked_style.paragraph_style.numbering_level
                p.set('calibre_num_id', f'{lvl}:{num_id}')
                is_numbering = True
                ps = self.numbering.get_para_style(cast('str | None', num_id), cast('int', lvl))  # has_numbering() is True
                if ps is not None:
                    parent_styles.append(ps)

            for attr in ans.all_properties:
                if not (is_numbering and attr == 'text_indent'):  # skip text-indent for lists
                    setattr(ans, attr, self.para_val(parent_styles, direct_formatting, attr))
            ans.linked_style = direct_formatting.linked_style
        return ans

    def resolve_run(self, r: _Element) -> RunStyle:
        ans = self.run_cache.get(r, None)
        if ans is None:
            p = self.namespace.XPath('ancestor::w:p[1]')(r)
            p = p[0] if p else None
            ans = self.run_cache[r] = RunStyle(self.namespace)
            direct_formatting = None
            for rPr in self.namespace.XPath('./w:rPr')(r):
                rs = RunStyle(self.namespace, rPr)
                if direct_formatting is None:
                    direct_formatting = rs
                else:
                    direct_formatting.update(rs)

            if direct_formatting is None:
                direct_formatting = RunStyle(self.namespace)

            parent_styles: list[RunStyle] = []
            default_char = self.default_styles.get('character', None)
            if self.default_character_style is not None:
                parent_styles.append(self.default_character_style)
            pstyle = self.para_char_cache.get(p, None)
            if pstyle is not None:
                parent_styles.append(pstyle)
            # As best as I can understand the spec, table overrides should be
            # applied before paragraph overrides, but word does it
            # this way, see the December 2007 table header in the demo
            # document.
            ts = self.tables.run_style(p)
            if ts is not None:
                parent_styles.append(ts)
            if direct_formatting.linked_style is not None:
                ls = getattr(self.get(direct_formatting.linked_style), 'character_style', None)
                if ls is not None:
                    parent_styles.append(ls)
            elif default_char is not None and default_char.character_style is not None:
                parent_styles.append(default_char.character_style)

            for attr in ans.all_properties:
                setattr(ans, attr, self.run_val(parent_styles, direct_formatting, attr))

            if ans.font_family is not inherit:
                ff = self.theme.resolve_font_family(cast('str', ans.font_family))  # not inherit, so str
                # toggle properties are always resolved to bool by run_val()
                ans.font_family = self.fonts.family_for(ff, cast('bool', ans.b), cast('bool', ans.i))

        return ans

    def resolve(self, obj: _Element) -> ParagraphStyle | RunStyle | None:
        tag = obj.tag
        assert isinstance(tag, str)  # obj is a w:p or w:r element
        if tag.endswith('}p'):
            return self.resolve_paragraph(obj)
        if tag.endswith('}r'):
            return self.resolve_run(obj)

    def cascade(self, layers: Mapping[_Element, Sequence[_Element]]) -> None:
        self.body_font_family = 'serif'
        self.body_font_size = '10pt'
        self.body_color = 'currentColor'

        def promote_property(char_styles: Sequence[RunStyle], block_style: ParagraphStyle, prop: str) -> None:
            vals = {getattr(s, prop) for s in char_styles}
            if len(vals) == 1:
                # All the character styles have the same value
                for s in char_styles:
                    setattr(s, prop, inherit)
                setattr(block_style, prop, next(iter(vals)))

        for p, runs in layers.items():
            has_links = '1' in {r.get('is-link', None) for r in runs}
            char_styles = [self.resolve_run(r) for r in runs]
            block_style = self.resolve_paragraph(p)
            for prop in ('font_family', 'font_size', 'cs_font_family', 'cs_font_size', 'color'):
                if has_links and prop == 'color':
                    # We cannot promote color as browser rendering engines will
                    # override the link color setting it to blue, unless the
                    # color is specified on the link element itself
                    continue
                promote_property(char_styles, block_style, prop)
            for s in char_styles:
                if s.text_decoration == 'none':
                    # The default text decoration is 'none'
                    s.text_decoration = inherit

        def promote_most_common[T](block_styles: Sequence[ParagraphStyle], prop: str, default: T, inherit_means: T | None = None) -> T | None:
            c: Counter[T] = Counter()
            for s in block_styles:
                val = getattr(s, prop)
                if val is inherit and inherit_means is not None:
                    val = inherit_means
                if val is not inherit:
                    c[val] += 1
            val = None
            if c:
                val = c.most_common(1)[0][0]
                for s in block_styles:
                    oval = getattr(s, prop)
                    if oval is inherit and inherit_means is not None:
                        oval = inherit_means
                    if oval is inherit:
                        if default != val:
                            setattr(s, prop, default)
                    elif oval == val:
                        setattr(s, prop, inherit)
            return val

        block_styles = tuple(self.resolve_paragraph(p) for p in layers)

        ff = promote_most_common(block_styles, 'font_family', self.body_font_family)
        if ff is not None:
            self.body_font_family = ff

        fs = promote_most_common(block_styles, 'font_size', int(self.body_font_size[:2]))
        if fs is not None:
            self.body_font_size = f'{fs:.3g}pt'

        color = promote_most_common(block_styles, 'color', self.body_color, inherit_means='currentColor')
        if color is not None:
            self.body_color = color

    def resolve_numbering(self, numbering: Numbering) -> None:
        # When a numPr element appears inside a paragraph style, the lvl info
        # must be discarded and pStyle used instead.
        self.numbering = numbering
        for style in self:
            ps = style.paragraph_style
            if ps is not None and ps.numbering_id is not inherit:
                lvl = numbering.get_pstyle(cast('str | None', ps.numbering_id), style.style_id)  # not inherit
                if lvl is None:
                    ps.numbering_id = ps.numbering_level = inherit
                else:
                    ps.numbering_level = lvl

    def apply_contextual_spacing(self, paras: Iterable[_Element]) -> None:
        last_para = None
        for p in paras:
            if last_para is not None:
                ls = self.resolve_paragraph(last_para)
                ps = self.resolve_paragraph(p)
                if ls.linked_style is not None and ls.linked_style == ps.linked_style:
                    if ls.contextualSpacing is True:
                        ls.margin_bottom = 0
                    if ps.contextualSpacing is True:
                        ps.margin_top = 0
            last_para = p

    def apply_section_page_breaks(self, paras: Iterable[_Element]) -> None:
        for p in paras:
            ps = self.resolve_paragraph(p)
            ps.pageBreakBefore = True

    def register(self, css: Mapping[str, str], prefix: str) -> str:
        h = hash(frozenset(css.items()))
        ans, _ = self.classes.get(h, (None, None))
        if ans is None:
            self.counter[prefix] += 1
            ans = f'{prefix}_{self.counter[prefix]}'
            self.classes[h] = (ans, css)
        return ans

    def generate_classes(self) -> None:
        for bs in self.para_cache.values():
            css = bs.css
            if css:
                self.register(css, 'block')
        for bs in self.run_cache.values():
            css = bs.css
            if css:
                self.register(css, 'text')

    def class_name(self, css: Mapping[str, str]) -> str | None:
        h = hash(frozenset(css.items()))
        return self.classes.get(h, (None, None))[0]

    def generate_css(self, dest_dir: str, docx: DOCX, notes_nopb: bool, nosupsub: bool) -> str:
        ef = self.fonts.embed_fonts(dest_dir, docx)

        s = '''\
            body { font-family: %s; font-size: %s; %s }

            /* In word all paragraphs have zero margins unless explicitly specified in a style */
            p, h1, h2, h3, h4, h5, h6, div { margin: 0; padding: 0 }
            /* In word headings only have bold font if explicitly specified,
                similarly the font size is the body font size, unless explicitly set. */
            h1, h2, h3, h4, h5, h6 { font-weight: normal; font-size: 1rem }
            ul, ol { margin: 0; padding: 0; padding-inline-start: 0; padding-inline-end: 0; margin-block-start: 0; margin-block-end: 0 }

            /* The word hyperlink styling will set text-decoration to underline if needed */
            a { text-decoration: none }

            sup.noteref a { text-decoration: none }

            h1.notes-header { page-break-before: always }

            dl.footnote dt { font-size: large }

            dl.footnote dt a { text-decoration: none }

            '''

        if not notes_nopb:
            s += '''\
            dl.footnote { page-break-after: always }
            dl.footnote:last-of-type { page-break-after: avoid }
            '''

        s = (
            s
            + '''\
            span.tab { white-space: pre }

            p.index-entry { text-indent: 0pt; }
            p.index-entry a:visited { color: blue }
            p.index-entry a:hover { color: red }
            '''
        )

        if nosupsub:
            s = (
                s
                + '''\
               sup { vertical-align: top }
               sub { vertical-align: bottom }
               '''
            )

        body_color = ''
        if self.body_color.lower() not in ('currentcolor', 'inherit'):
            body_color = f'color: {self.body_color};'
        prefix = textwrap.dedent(s) % (self.body_font_family, self.body_font_size, body_color)
        if ef:
            prefix = ef + '\n' + prefix

        ans = []
        for cls, css in sorted(self.classes.values(), key=lambda x: x[0]):
            b = (f'\t{k}: {v};' for k, v in css.items())
            b = '\n'.join(b)
            ans.append('.{} {{\n{}\n}}\n'.format(cls, b.rstrip(';')))
        return prefix + '\n' + '\n'.join(ans)
