'''
CSS flattening transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys
import os
import re
import operator
import math
from itertools import chain
from collections import defaultdict
from lxml import etree
from calibre.ebooks.oeb.base import XHTML, XHTML_NS
from calibre.ebooks.oeb.base import CSS_MIME, OEB_STYLES
from calibre.ebooks.oeb.base import namespace, barename
from calibre.ebooks.oeb.base import OEBBook
from calibre.ebooks.oeb.stylizer import Stylizer

COLLAPSE = re.compile(r'[ \t\r\n\v]+')
STRIPNUM = re.compile(r'[-0-9]+$')

class KeyMapper(object):
    def __init__(self, sbase, dbase, dkey):
        self.sbase = float(sbase)
        self.dprop = [(self.relate(x, dbase), float(x)) for x in dkey]
        self.cache = {}

    @staticmethod
    def relate(size, base):
        size = float(size)
        base = float(base)
        if abs(size - base) < 0.1: return 0
        sign = -1 if size < base else 1
        endp = 0 if size < base else 36
        diff = (abs(base - size) * 3) + ((36 - size) / 100)
        logb = abs(base - endp) 
        result = sign * math.log(diff, logb)
        return result
        
    def __getitem__(self, ssize):
        if ssize in self.cache:
            return self.cache[ssize]
        dsize = self.map(ssize)
        self.cache[ssize] = dsize
        return dsize

    def map(self, ssize):
        sbase = self.sbase
        prop = self.relate(ssize, sbase)
        diff = [(abs(prop - p), s) for p, s in self.dprop]
        dsize = min(diff)[1]
        return dsize

class ScaleMapper(object):
    def __init__(self, sbase, dbase):
        self.dscale = float(dbase) / float(sbase)

    def __getitem__(self, ssize):
        dsize = ssize * self.dscale
        return dsize

class NullMapper(object):
    def __init__(self):
        pass

    def __getitem__(self, ssize):
        return ssize
    
def FontMapper(sbase=None, dbase=None, dkey=None):
    if sbase and dbase and dkey:
        return KeyMapper(sbase, dbase, dkey)
    elif sbase and dbase:
        return ScaleMapper(sbase, dbase)
    else:
        return NullMapper()


class CSSFlattener(object):
    def __init__(self, fbase=None, fkey=None, lineh=None, unfloat=False,
                 untable=False):
        self.fbase = fbase
        self.fkey = fkey
        self.lineh = lineh
        self.unfloat = unfloat
        self.untable = untable

    def transform(self, oeb, context):
        oeb.logger.info('Flattening CSS and remapping font sizes...')
        self.oeb = oeb
        self.context = context
        self.stylize_spine()
        self.sbase = self.baseline_spine() if self.fbase else None
        self.fmap = FontMapper(self.sbase, self.fbase, self.fkey)
        self.flatten_spine()

    def stylize_spine(self):
        self.stylizers = {}
        profile = self.context.source
        for item in self.oeb.spine:
            html = item.data
            stylizer = Stylizer(html, item.href, self.oeb, profile)
            self.stylizers[item] = stylizer

    def baseline_node(self, node, stylizer, sizes, csize):
        csize = stylizer.style(node)['font-size']
        if node.text:
            sizes[csize] += len(COLLAPSE.sub(' ', node.text))
        for child in node:
            self.baseline_node(child, stylizer, sizes, csize)
            if child.tail:
                sizes[csize] += len(COLLAPSE.sub(' ', child.tail))
    
    def baseline_spine(self):
        sizes = defaultdict(float)
        for item in self.oeb.spine:
            html = item.data
            stylizer = self.stylizers[item]
            body = html.find(XHTML('body'))
            fsize = self.context.source.fbase
            self.baseline_node(body, stylizer, sizes, fsize)
        sbase = max(sizes.items(), key=operator.itemgetter(1))[0]
        self.oeb.logger.info(
            "Source base font size is %0.05fpt" % sbase)
        return sbase

    def clean_edges(self, cssdict, style, fsize):
        slineh = self.sbase * 1.26
        dlineh = self.lineh
        for kind in ('margin', 'padding'):
            for edge in ('bottom', 'top'):
                property = "%s-%s" % (kind, edge)
                if property not in cssdict: continue
                if '%' in cssdict[property]: continue
                value = style[property]
                if value == 0:
                    continue
                elif value <= slineh:
                    cssdict[property] = "%0.5fem" % (dlineh / fsize)
                else:
                    value = round(value / slineh) * dlineh
                    cssdict[property] = "%0.5fem" % (value / fsize)
    
    def flatten_node(self, node, stylizer, names, styles, psize, left=0):
        if not isinstance(node.tag, basestring) \
           or namespace(node.tag) != XHTML_NS:
            return
        tag = barename(node.tag)
        style = stylizer.style(node)
        cssdict = style.cssdict()
        if 'align' in node.attrib:
            cssdict['text-align'] = node.attrib['align']
            del node.attrib['align']
        if node.tag == XHTML('font'):
            node.tag = XHTML('span')
            if 'size' in node.attrib:
                size = node.attrib['size'].strip()
                if size:
                    fnums = self.context.source.fnums
                    if size[0] in ('+', '-'):
                        # Oh, the warcrimes
                        cssdict['font-size'] = fnums[3+int(size)]
                    else:
                        cssdict['font-size'] = fnums[int(size)]
                del node.attrib['size']
        if 'color' in node.attrib:
            cssdict['color'] = node.attrib['color']
            del node.attrib['color']
        if 'bgcolor' in node.attrib:
            cssdict['background-color'] = node.attrib['bgcolor']
            del node.attrib['bgcolor']
        if 'font-size' in cssdict or tag == 'body':
            fsize = self.fmap[style['font-size']]
            cssdict['font-size'] = "%0.5fem" % (fsize / psize)
            psize = fsize
        if cssdict:
            if self.lineh and self.fbase and tag != 'body':
                self.clean_edges(cssdict, style, psize)
            margin = style['margin-left']
            left += margin if isinstance(margin, float) else 0
            if (left + style['text-indent']) < 0:
                percent = (margin - style['text-indent']) / style['width']
                cssdict['margin-left'] = "%d%%" % (percent * 100)
                left -= style['text-indent']
            if 'display' in cssdict and cssdict['display'] == 'in-line':
                cssdict['display'] = 'inline'
            if self.unfloat and 'float' in cssdict \
               and cssdict.get('display', 'none') != 'none':
                del cssdict['display']
            if self.untable and 'display' in cssdict \
               and cssdict['display'].startswith('table'):
                display = cssdict['display']
                if display == 'table-cell':
                    cssdict['display'] = 'inline'
                else:
                    cssdict['display'] = 'block'
            if 'vertical-align' in cssdict \
               and cssdict['vertical-align'] == 'sup':
                cssdict['vertical-align'] = 'super'
        if self.lineh and 'line-height' not in cssdict:
            lineh = self.lineh / psize
            cssdict['line-height'] = "%0.5fem" % lineh
        if cssdict:
            items = cssdict.items()
            items.sort()
            css = u';\n'.join(u'%s: %s' % (key, val) for key, val in items)
            klass = STRIPNUM.sub('', node.get('class', 'calibre').split()[0])
            if css in styles:
                match = styles[css]
            else:
                match = klass + str(names[klass] or '')
                styles[css] = match
                names[klass] += 1
            node.attrib['class'] = match
        elif 'class' in node.attrib:
            del node.attrib['class']
        if 'style' in node.attrib:
            del node.attrib['style']
        for child in node:
            self.flatten_node(child, stylizer, names, styles, psize, left)

    def flatten_head(self, item, stylizer, href):
        html = item.data
        head = html.find(XHTML('head'))
        for node in head:
            if node.tag == XHTML('link') \
               and node.get('rel', 'stylesheet') == 'stylesheet' \
               and node.get('type', CSS_MIME) in OEB_STYLES:
                head.remove(node)
            elif node.tag == XHTML('style') \
                 and node.get('type', CSS_MIME) in OEB_STYLES:
                head.remove(node)
        href = item.relhref(href)
        etree.SubElement(head, XHTML('link'),
            rel='stylesheet', type=CSS_MIME, href=href)
        if stylizer.page_rule:
            items = stylizer.page_rule.items()
            items.sort()
            css = '; '.join("%s: %s" % (key, val) for key, val in items)
            style = etree.SubElement(head, XHTML('style'), type=CSS_MIME)
            style.text = "@page { %s; }" % css

    def replace_css(self, css):
        manifest = self.oeb.manifest
        id, href = manifest.generate('css', 'stylesheet.css')
        for item in manifest.values():
            if item.media_type in OEB_STYLES:
                manifest.remove(item)
        item = manifest.add(id, href, CSS_MIME, data=css)
        return href
            
    def flatten_spine(self):
        names = defaultdict(int)
        styles = {}
        for item in self.oeb.spine:
            html = item.data
            stylizer = self.stylizers[item]
            body = html.find(XHTML('body'))
            fsize = self.context.dest.fbase
            self.flatten_node(body, stylizer, names, styles, fsize)
        items = [(key, val) for (val, key) in styles.items()]
        items.sort()
        css = ''.join(".%s {\n%s;\n}\n\n" % (key, val) for key, val in items)
        href = self.replace_css(css)
        for item in self.oeb.spine:
            stylizer = self.stylizers[item]
            self.flatten_head(item, stylizer, href)
