#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, operator
from copy import deepcopy, copy

from lxml import etree

from calibre import guess_type
from polyglot.builtins import as_bytes, map, unicode_type


class Canvas(etree.XSLTExtension):

    def __init__(self, doc, styles, text_block, log):
        self.doc = doc
        self.styles = styles
        self.text_block = text_block
        self.log = log
        self.processed = set()

    def execute(self, context, self_node, input_node, output_parent):
        cid = input_node.get('objid', None)
        if cid is None or cid in self.processed:
            return
        self.processed.add(cid)
        input_node = self.doc.xpath('//Canvas[@objid="%s"]'%cid)[0]

        objects = list(self.get_objects(input_node))
        if len(objects) == 1 and objects[0][0].tag == 'ImageBlock':
            self.image_page(input_node, objects[0][0], output_parent)
        else:
            canvases = [input_node]
            for x in input_node.itersiblings():
                if x.tag == 'Canvas':
                    oid = x.get('objid', None)
                    if oid is not None:
                        canvases.append(x)
                        self.processed.add(oid)
                else:
                    break

            table = etree.Element('table')
            table.text = '\n\t'
            for canvas in canvases:
                oid = canvas.get('objid')
                tr = table.makeelement('tr')
                tr.set('id', oid)
                tr.tail = '\n\t'
                table.append(tr)
                for obj, x, y in self.get_objects(canvas):
                    if obj.tag != 'TextBlock':
                        self.log.warn(obj.tag, 'elements in Canvas not supported')
                        continue
                    td = table.makeelement('td')
                    self.text_block.render_block(obj, td)
                    tr.append(td)
            output_parent.append(table)

    def image_page(self, input_node, block, output_parent):
        div = etree.Element('div')
        div.set('id', input_node.get('objid', 'scuzzy'))
        div.set('class', 'image_page')
        width = self.styles.to_num(block.get("xsize", None))
        height = self.styles.to_num(block.get("ysize", None))
        img = div.makeelement('img')
        if width is not None:
            img.set('width', unicode_type(int(width)))
        if height is not None:
            img.set('height', unicode_type(int(height)))
        ref = block.get('refstream', None)
        if ref is not None:
            imstr = self.doc.xpath('//ImageStream[@objid="%s"]'%ref)
            if imstr:
                src = imstr[0].get('file', None)
                if src:
                    img.set('src', src)
        div.append(img)
        output_parent.append(div)

    def get_objects(self, node):
        for x in node.xpath('descendant::PutObj[@refobj and @x1 and @y1]'):
            objs = node.xpath('//*[@objid="%s"]'%x.get('refobj'))
            x, y = map(self.styles.to_num, (x.get('x1'), x.get('y1')))
            if objs and x is not None and y is not None:
                yield objs[0], int(x), int(y)


class MediaType(etree.XSLTExtension):

    def execute(self, context, self_node, input_node, output_parent):
        name = input_node.get('file', None)
        typ = guess_type(name)[0]
        if not typ:
            typ = 'application/octet-stream'
        output_parent.text = typ


class ImageBlock(etree.XSLTExtension):

    def __init__(self, canvas):
        etree.XSLTExtension.__init__(self)
        self.canvas = canvas

    def execute(self, context, self_node, input_node, output_parent):
        self.canvas.image_page(input_node, input_node, output_parent)


class RuledLine(etree.XSLTExtension):

    def execute(self, context, self_node, input_node, output_parent):
        hr = etree.Element('hr')
        output_parent.append(hr)


class TextBlock(etree.XSLTExtension):

    def __init__(self, styles, char_button_map, plot_map, log):
        etree.XSLTExtension.__init__(self)
        self.styles = styles
        self.log = log
        self.char_button_map = char_button_map
        self.plot_map = plot_map

    def execute(self, context, self_node, input_node, output_parent):
        input_node = deepcopy(input_node)
        div = etree.Element('div')
        self.render_block(input_node, div)
        output_parent.append(div)

    def render_block(self, node, root):
        ts = node.get('textstyle', None)
        classes = []
        bs = node.get('blockstyle')
        if bs in self.styles.block_style_map:
            classes.append('bs%d'%self.styles.block_style_map[bs])
        if ts in self.styles.text_style_map:
            classes.append('ts%d'%self.styles.text_style_map[ts])
        if classes:
            root.set('class', ' '.join(classes))
        objid = node.get('objid', None)
        if objid:
            root.set('id', objid)
        root.text = node.text
        self.root = root
        self.parent = root
        self.add_text_to = (self.parent, 'text')
        self.fix_deep_nesting(node)
        for child in node:
            self.process_child(child)

    def fix_deep_nesting(self, node):
        deepest = 1

        def depth(node):
            parent = node.getparent()
            ans = 1
            while parent is not None:
                ans += 1
                parent = parent.getparent()
            return ans

        for span in node.xpath('descendant::Span'):
            d = depth(span)
            if d > deepest:
                deepest = d
                if d > 500:
                    break

        if deepest < 500:
            return

        self.log.warn('Found deeply nested spans. Flattening.')
        # with open('/t/before.xml', 'wb') as f:
        #    f.write(etree.tostring(node, method='xml'))

        spans = [(depth(span), span) for span in node.xpath('descendant::Span')]
        spans.sort(key=operator.itemgetter(0), reverse=True)

        for depth, span in spans:
            if depth < 3:
                continue
            p = span.getparent()
            gp = p.getparent()
            idx = p.index(span)
            pidx = gp.index(p)
            children = list(p)[idx:]
            t = children[-1].tail
            t = t if t else ''
            children[-1].tail = t + (p.tail if p.tail else '')
            p.tail = ''
            pattrib = dict(**p.attrib) if p.tag == 'Span' else {}
            for child in children:
                p.remove(child)
                if pattrib and child.tag == "Span":
                    attrib = copy(pattrib)
                    attrib.update(child.attrib)
                    child.attrib.update(attrib)

            for child in reversed(children):
                gp.insert(pidx+1, child)

        # with open('/t/after.xml', 'wb') as f:
        #    f.write(etree.tostring(node, method='xml'))

    def add_text(self, text):
        if text:
            if getattr(self.add_text_to[0], self.add_text_to[1]) is None:
                setattr(self.add_text_to[0], self.add_text_to[1], '')
            setattr(self.add_text_to[0], self.add_text_to[1],
                    getattr(self.add_text_to[0], self.add_text_to[1])+ text)

    def process_container(self, child, tgt):
        idx = self.styles.get_text_styles(child)
        if idx is not None:
            tgt.set('class', 'ts%d'%idx)
        self.parent.append(tgt)
        orig_parent = self.parent
        self.parent = tgt
        self.add_text_to = (self.parent, 'text')
        self.add_text(child.text)
        for gchild in child:
            self.process_child(gchild)
        self.parent = orig_parent
        self.add_text_to = (tgt, 'tail')
        self.add_text(child.tail)

    def process_child(self, child):
        if child.tag == 'CR':
            if self.parent == self.root or self.parent.tag == 'p':
                self.parent = self.root.makeelement('p')
                self.root.append(self.parent)
                self.add_text_to = (self.parent, 'text')
            else:
                br = self.parent.makeelement('br')
                self.parent.append(br)
                self.add_text_to = (br, 'tail')
            self.add_text(child.tail)
        elif child.tag in ('P', 'Span', 'EmpLine', 'NoBR'):
            span = self.root.makeelement('span')
            if child.tag == 'EmpLine':
                td = 'underline' if child.get('emplineposition', 'before') == 'before' else 'overline'
                span.set('style', 'text-decoration: '+td)
            self.process_container(child, span)
        elif child.tag == 'Sup':
            sup = self.root.makeelement('sup')
            self.process_container(child, sup)
        elif child.tag == 'Sub':
            sub = self.root.makeelement('sub')
            self.process_container(child, sub)
        elif child.tag == 'Italic':
            sup = self.root.makeelement('i')
            self.process_container(child, sup)
        elif child.tag == 'CharButton':
            a = self.root.makeelement('a')
            oid = child.get('refobj', None)
            if oid in self.char_button_map:
                a.set('href', self.char_button_map[oid])
            self.process_container(child, a)
        elif child.tag == 'Plot':
            xsize = self.styles.to_num(child.get('xsize', None), 166/720)
            ysize = self.styles.to_num(child.get('ysize', None), 166/720)
            img = self.root.makeelement('img')
            if xsize is not None:
                img.set('width', unicode_type(int(xsize)))
            if ysize is not None:
                img.set('height', unicode_type(int(ysize)))
            ro = child.get('refobj', None)
            if ro in self.plot_map:
                img.set('src', self.plot_map[ro])
            self.parent.append(img)
            self.add_text_to = (img, 'tail')
            self.add_text(child.tail)
        else:
            self.log.warn('Unhandled Text element:', child.tag)


class Styles(etree.XSLTExtension):

    def __init__(self):
        etree.XSLTExtension.__init__(self)
        self.text_styles, self.block_styles = [], []
        self.text_style_map, self.block_style_map = {}, {}
        self.CSS = textwrap.dedent('''
        .image_page { text-align:center }
        ''')

    def write(self, name='styles.css'):

        def join(style):
            ans = ['%s : %s;'%(k, v) for k, v in style.items()]
            if ans:
                ans[-1] = ans[-1][:-1]
            return '\n\t'.join(ans)

        with open(name, 'wb') as f:
            f.write(as_bytes(self.CSS))
            for (w, sel) in [(self.text_styles, 'ts'), (self.block_styles,
                'bs')]:
                for i, s in enumerate(w):
                    if not s:
                        continue
                    rsel = '.%s%d'%(sel, i)
                    s = join(s)
                    f.write(as_bytes(rsel + ' {\n\t' + s + '\n}\n\n'))

    def execute(self, context, self_node, input_node, output_parent):
        if input_node.tag == 'TextStyle':
            idx = self.get_text_styles(input_node)
            if idx is not None:
                self.text_style_map[input_node.get('objid')] = idx
        else:
            idx = self.get_block_styles(input_node)
            self.block_style_map[input_node.get('objid')] = idx

    def px_to_pt(self, px):
        try:
            return px * 72/166
        except:
            return None

    def color(self, val):
        try:
            val = int(val, 16)
            r, g, b, a = val & 0xFF, (val>>8)&0xFF, (val>>16)&0xFF, (val>>24)&0xFF
            if a == 255:
                return None
            if a == 0:
                return 'rgb(%d,%d,%d)'%(r,g,b)
            return 'rgba(%d,%d,%d,%f)'%(r,g,b,1.-a/255.)
        except:
            return None

    def get_block_styles(self, node):
        ans = {}
        sm = self.px_to_pt(node.get('sidemargin', None))
        if sm is not None:
            ans['margin-left'] = ans['margin-right'] = '%fpt'%sm
        ts = self.px_to_pt(node.get('topskip', None))
        if ts is not None:
            ans['margin-top'] = '%fpt'%ts
        fs = self.px_to_pt(node.get('footskip', None))
        if fs is not None:
            ans['margin-bottom'] = '%fpt'%fs
        fw = self.px_to_pt(node.get('framewidth', None))
        if fw is not None:
            ans['border-width'] = '%fpt'%fw
            ans['border-style'] = 'solid'
        fc = self.color(node.get('framecolor', None))
        if fc is not None:
            ans['border-color'] = fc
        bc = self.color(node.get('bgcolor', None))
        if bc is not None:
            ans['background-color'] = bc
        if ans not in self.block_styles:
            self.block_styles.append(ans)
        return self.block_styles.index(ans)

    def to_num(self, val, factor=1.):
        try:
            return float(val)*factor
        except:
            return None

    def get_text_styles(self, node):
        ans = {}
        fs = self.to_num(node.get('fontsize', None), 0.1)
        if fs is not None:
            ans['font-size'] = '%fpt'%fs
        fw = self.to_num(node.get('fontweight', None))
        if fw is not None:
            ans['font-weight'] = ('bold' if fw >= 700 else 'normal')
        # fn = getattr(obj, 'fontfacename', None)
        # if fn is not None:
        #    fn = cls.FONT_MAP[fn]
        #    item('font-family: %s;'%fn)
        fg = self.color(node.get('textcolor', None))
        if fg is not None:
            ans['color'] = fg
        bg = self.color(node.get('textbgcolor', None))
        if bg is not None:
            ans['background-color'] = bg
        al = node.get('align', None)
        if al is not None:
            all = dict(head='left', center='center', foot='right')
            ans['text-align'] = all.get(al, 'left')
        # lh = self.to_num(node.get('linespace', None), 0.1)
        # if lh is not None:
        #    ans['line-height'] = '%fpt'%lh
        pi = self.to_num(node.get('parindent', None), 0.1)
        if pi is not None:
            ans['text-indent'] = '%fpt'%pi
        if not ans:
            return None
        if ans not in self.text_styles:
            self.text_styles.append(ans)
        return self.text_styles.index(ans)
