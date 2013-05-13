#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap
from collections import OrderedDict, Counter

from calibre.ebooks.docx.block_styles import ParagraphStyle, inherit
from calibre.ebooks.docx.char_styles import RunStyle
from calibre.ebooks.docx.names import XPath, get


class Style(object):
    '''
    Class representing a <w:style> element. Can contain block, character, etc. styles.
    '''

    name_path = XPath('./w:name[@w:val]')
    based_on_path = XPath('./w:basedOn[@w:val]')

    def __init__(self, elem):
        self.resolved = False
        self.style_id = get(elem, 'w:styleId')
        self.style_type = get(elem, 'w:type')
        names = self.name_path(elem)
        self.name = get(names[-1], 'w:val') if names else None
        based_on = self.based_on_path(elem)
        self.based_on = get(based_on[0], 'w:val') if based_on else None
        if self.style_type == 'numbering':
            self.based_on = None
        self.is_default = get(elem, 'w:default') in {'1', 'on', 'true'}

        self.paragraph_style = self.character_style = None

        if self.style_type in {'paragraph', 'character'}:
            if self.style_type == 'paragraph':
                for pPr in XPath('./w:pPr')(elem):
                    ps = ParagraphStyle(pPr)
                    if self.paragraph_style is None:
                        self.paragraph_style = ps
                    else:
                        self.paragraph_style.update(ps)

            for rPr in XPath('./w:rPr')(elem):
                rs = RunStyle(rPr)
                if self.character_style is None:
                    self.character_style = rs
                else:
                    self.character_style.update(rs)

        if self.style_type == 'numbering':
            self.numbering_style_link = None
            for x in XPath('./w:pPr/w:numPr/w:numId[@w:val]')(elem):
                self.numbering_style_link = get(x, 'w:val')

    def resolve_based_on(self, parent):
        if parent.paragraph_style is not None:
            if self.paragraph_style is None:
                self.paragraph_style = ParagraphStyle()
            self.paragraph_style.resolve_based_on(parent.paragraph_style)
        if parent.character_style is not None:
            if self.character_style is None:
                self.character_style = RunStyle()
            self.character_style.resolve_based_on(parent.character_style)


class Styles(object):

    '''
    Collection of all styles defined in the document. Used to get the final styles applicable to elements in the document markup.
    '''

    def __init__(self):
        self.id_map = OrderedDict()
        self.para_cache = {}
        self.para_char_cache = {}
        self.run_cache = {}
        self.classes = {}
        self.counter = Counter()
        self.default_styles = {}
        self.numbering_style_links = {}

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
            if s.is_default:
                self.default_styles[s.style_type] = s
            if s.style_type == 'numbering' and s.numbering_style_link:
                self.numbering_style_links[s.style_id] = s.numbering_style_link

        self.default_paragraph_style = self.default_character_style = None

        for dd in XPath('./w:docDefaults')(root):
            for pd in XPath('./w:pPrDefault')(dd):
                for pPr in XPath('./w:pPr')(pd):
                    ps = ParagraphStyle(pPr)
                    if self.default_paragraph_style is None:
                        self.default_paragraph_style = ps
                    else:
                        self.default_paragraph_style.update(ps)
            for pd in XPath('./w:rPrDefault')(dd):
                for pPr in XPath('./w:rPr')(pd):
                    ps = RunStyle(pPr)
                    if self.default_character_style is None:
                        self.default_character_style = ps
                    else:
                        self.default_character_style.update(ps)

        def resolve(s, p):
            if p is not None:
                if not p.resolved:
                    resolve(p, self.get(p.based_on))
                s.resolve_based_on(p)
            s.resolved = True

        for s in self:
            if not s.resolved:
                resolve(s, self.get(s.based_on))

    def para_val(self, parent_styles, direct_formatting, attr):
        val = getattr(direct_formatting, attr)
        if val is inherit:
            for ps in reversed(parent_styles):
                pval = getattr(ps, attr)
                if pval is not inherit:
                    val = pval
                    break
        return val

    def run_val(self, parent_styles, direct_formatting, attr):
        val = getattr(direct_formatting, attr)
        if val is not inherit:
            return val
        if attr in direct_formatting.toggle_properties:
            val = False
            for rs in parent_styles:
                pval = getattr(rs, attr)
                if pval is True:
                    val ^= True
            return val
        for rs in reversed(parent_styles):
            rval = getattr(rs, attr)
            if rval is not inherit:
                return rval
        return val

    def resolve_paragraph(self, p):
        ans = self.para_cache.get(p, None)
        if ans is None:
            ans = self.para_cache[p] = ParagraphStyle()
            ans.style_name = None
            direct_formatting = None
            for pPr in XPath('./w:pPr')(p):
                ps = ParagraphStyle(pPr)
                if direct_formatting is None:
                    direct_formatting = ps
                else:
                    direct_formatting.update(ps)

            if direct_formatting is None:
                direct_formatting = ParagraphStyle()
            parent_styles = []
            if self.default_paragraph_style is not None:
                parent_styles.append(self.default_paragraph_style)

            default_para = self.default_styles.get('paragraph', None)
            if direct_formatting.linked_style is not None:
                ls = self.get(direct_formatting.linked_style)
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

            is_numbering = direct_formatting.numbering is not inherit
            if is_numbering:
                num_id, lvl = direct_formatting.numbering
                if num_id is not None:
                    p.set('calibre_num_id', '%s:%s' % (lvl, num_id))
                if num_id is not None and lvl is not None:
                    ps = self.numbering.get_para_style(num_id, lvl)
                    if ps is not None:
                        parent_styles.append(ps)

            for attr in ans.all_properties:
                if not (is_numbering and attr == 'text_indent'):  # skip text-indent for lists
                    setattr(ans, attr, self.para_val(parent_styles, direct_formatting, attr))
        return ans

    def resolve_run(self, r):
        ans = self.run_cache.get(r, None)
        if ans is None:
            p = r.getparent()
            ans = self.run_cache[r] = RunStyle()
            direct_formatting = None
            for rPr in XPath('./w:rPr')(r):
                rs = RunStyle(rPr)
                if direct_formatting is None:
                    direct_formatting = rs
                else:
                    direct_formatting.update(rs)

            if direct_formatting is None:
                direct_formatting = RunStyle()

            parent_styles = []
            default_char = self.default_styles.get('character', None)
            if self.default_character_style is not None:
                parent_styles.append(self.default_character_style)
            pstyle = self.para_char_cache.get(p, None)
            if pstyle is not None:
                parent_styles.append(pstyle)
            if direct_formatting.linked_style is not None:
                ls = self.get(direct_formatting.linked_style).character_style
                if ls is not None:
                    parent_styles.append(ls)
            elif default_char is not None and default_char.character_style is not None:
                parent_styles.append(default_char.character_style)

            for attr in ans.all_properties:
                setattr(ans, attr, self.run_val(parent_styles, direct_formatting, attr))

        return ans

    def resolve(self, obj):
        if obj.tag.endswith('}p'):
            return self.resolve_paragraph(obj)
        if obj.tag.endswith('}r'):
            return self.resolve_run(obj)

    def resolve_numbering(self, numbering):
        # When a numPr element appears inside a paragraph style, the lvl info
        # must be discarder and pStyle used instead.
        self.numbering = numbering
        for style in self:
            ps = style.paragraph_style
            if ps is not None and ps.numbering is not inherit:
                lvl = numbering.get_pstyle(ps.numbering[0], style.style_id)
                if lvl is None:
                    ps.numbering = inherit
                else:
                    ps.numbering = (ps.numbering[0], lvl)

    def register(self, css, prefix):
        h = hash(frozenset(css.iteritems()))
        ans, _ = self.classes.get(h, (None, None))
        if ans is None:
            self.counter[prefix] += 1
            ans = '%s_%d' % (prefix, self.counter[prefix])
            self.classes[h] = (ans, css)
        return ans

    def generate_classes(self):
        for bs in self.para_cache.itervalues():
            css = bs.css
            if css:
                self.register(css, 'block')
        for bs in self.run_cache.itervalues():
            css = bs.css
            if css:
                self.register(css, 'text')

    def class_name(self, css):
        h = hash(frozenset(css.iteritems()))
        return self.classes.get(h, (None, None))[0]

    def generate_css(self):
        prefix = textwrap.dedent(
            '''\
            p { text-indent: 1.5em }

            ul, ol, p { margin: 0; padding: 0 }
            ''')

        ans = []
        for (cls, css) in sorted(self.classes.itervalues(), key=lambda x:x[0]):
            b = ('\t%s: %s;' % (k, v) for k, v in css.iteritems())
            b = '\n'.join(b)
            ans.append('.%s {\n%s\n}\n' % (cls, b.rstrip(';')))
        return prefix + '\n' + '\n'.join(ans)

